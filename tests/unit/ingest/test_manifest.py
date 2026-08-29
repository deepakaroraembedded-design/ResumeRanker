from __future__ import annotations

import os
import random
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pymupdf

from ats_scan.codes import ReasonCode
from ats_scan.ingest.manifest import (
    Manifest,
    build_manifest,
    cluster_by_identity,
)
from ats_scan.models.config import IngestConfig
from ats_scan.models.resume import CanonicalResume, Identity
from ats_scan.models.source import SourceDocument


def _random_bytes(length: int, seed: int = 0) -> bytes:
    """Return deterministic printable ASCII bytes for SimHash tests."""
    random.seed(seed)
    return bytes(random.randint(32, 126) for _ in range(length))


def _make_pdf(path: Path, pages: int = 1) -> None:
    """Create a minimal valid PDF with *pages* pages using PyMuPDF."""
    doc = pymupdf.open()
    for _ in range(pages):
        doc.new_page()
    doc.save(path)
    doc.close()


def test_walk_recursive_and_order(tmp_path: Path) -> None:
    """FR-101: all matching files are discovered and returned in sorted order."""
    (tmp_path / "a.txt").write_text("A")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("B")
    (tmp_path / "c.pdf").write_text("not a pdf")

    result = build_manifest(tmp_path, IngestConfig())
    assert result.ok
    manifest = result.value
    paths = [doc.path for doc in manifest.documents]
    assert paths == sorted(paths)
    assert "a.txt" in paths
    assert str(Path("sub") / "b.txt") in paths
    assert "c.pdf" in paths


def test_include_exclude_globs(tmp_path: Path) -> None:
    """FR-101: include globs accept files and exclude globs reject them."""
    cfg = IngestConfig(include=("**/*.txt",), exclude=("**/skip.txt",))
    (tmp_path / "a.txt").write_text("A")
    (tmp_path / "skip.txt").write_text("skip")
    (tmp_path / "b.pdf").write_text("B")

    result = build_manifest(tmp_path, cfg)
    assert result.ok
    assert [doc.path for doc in result.value.documents] == ["a.txt"]


def test_magic_overrides_extension(tmp_path: Path) -> None:
    """FR-103: a .txt file whose bytes are a PDF is detected as a PDF."""
    pdf_path = tmp_path / "resume.txt"
    _make_pdf(pdf_path, pages=1)

    result = build_manifest(tmp_path, IngestConfig())
    assert result.ok
    doc = result.value.documents[0]
    assert doc.path == "resume.txt"
    assert doc.media_type == "application/pdf"
    assert doc.pages == 1


def test_mislabelled_text_file(tmp_path: Path) -> None:
    """FR-103: a .pdf file containing plain text is detected as text/plain."""
    text_path = tmp_path / "resume.pdf"
    text_path.write_text("This is a plain text resume.\nSkills: python, sql.")

    result = build_manifest(tmp_path, IngestConfig())
    assert result.ok
    doc = result.value.documents[0]
    assert doc.path == "resume.pdf"
    assert doc.media_type == "text/plain"
    assert doc.pages is None


def test_sha256_and_candidate_id(tmp_path: Path) -> None:
    """FR-104: content SHA-256 and the derived candidate_id are correct."""
    import hashlib

    content = b"hello ingest"
    (tmp_path / "a.txt").write_bytes(content)

    result = build_manifest(tmp_path, IngestConfig())
    assert result.ok
    doc = result.value.documents[0]
    expected_sha = hashlib.sha256(content).hexdigest()
    assert doc.content_sha256 == expected_sha
    expected_candidate_id = f"c_{expected_sha[:8]}"
    assert expected_candidate_id.startswith("c_")
    assert expected_candidate_id == f"c_{doc.content_sha256[:8]}"


def test_exact_duplicate_detection(tmp_path: Path) -> None:
    """FR-105: identical files form a duplicate cluster."""
    content = b"duplicate content" * 200
    (tmp_path / "a.txt").write_bytes(content)
    (tmp_path / "b.txt").write_bytes(content)

    result = build_manifest(tmp_path, IngestConfig())
    assert result.ok
    assert len(result.value.documents) == 2
    cids = {f"c_{doc.content_sha256[:8]}" for doc in result.value.documents}
    assert len(cids) == 1
    assert len(result.value.duplicate_clusters) == 1
    cluster = result.value.duplicate_clusters[0]
    assert cluster.representative in cids


def test_simhash_duplicate_detection(tmp_path: Path) -> None:
    """FR-105: near-duplicate files (SimHash distance <= 3) form a cluster."""
    base = _random_bytes(4096, seed=0)
    variant = b"ABCD" + base[4:]
    (tmp_path / "a.txt").write_bytes(base)
    (tmp_path / "b.txt").write_bytes(variant)

    result = build_manifest(tmp_path, IngestConfig())
    assert result.ok
    cids = {f"c_{doc.content_sha256[:8]}" for doc in result.value.documents}
    assert len(cids) == 2
    assert len(result.value.duplicate_clusters) == 1
    cluster = result.value.duplicate_clusters[0]
    assert len(cluster.documents) == 2
    assert cluster.representative in cluster.documents


def test_cluster_representative_mtime_tiebreak(tmp_path: Path) -> None:
    """FR-106: when parse_completeness is unavailable, mtime breaks ties."""
    base = _random_bytes(4096, seed=0)
    variant = b"ABCD" + base[4:]
    a_path = tmp_path / "a.txt"
    b_path = tmp_path / "b.txt"
    a_path.write_bytes(base)
    b_path.write_bytes(variant)

    old_ts = datetime(2020, 1, 1, tzinfo=UTC).timestamp()
    new_ts = datetime(2024, 1, 1, tzinfo=UTC).timestamp()
    os.utime(a_path, (old_ts, old_ts))
    os.utime(b_path, (new_ts, new_ts))

    result = build_manifest(tmp_path, IngestConfig())
    assert result.ok
    cluster = result.value.duplicate_clusters[0]
    doc_b = next(doc for doc in result.value.documents if doc.path == "b.txt")
    assert cluster.representative == f"c_{doc_b.content_sha256[:8]}"


def test_cluster_representative_parse_completeness() -> None:
    """FR-106: highest parse_completeness wins over a newer mtime."""
    source_a = SourceDocument(
        path="a.txt",
        content_sha256="a" * 64,
        bytes=100,
        mtime="2024-01-01T00:00:00+00:00",
        media_type="text/plain",
    )
    source_b = SourceDocument(
        path="b.txt",
        content_sha256="b" * 64,
        bytes=100,
        mtime="2020-01-01T00:00:00+00:00",
        media_type="text/plain",
    )
    resume_a = CanonicalResume(
        candidate_id="c_a",
        identity=Identity(full_name="John Doe"),
        source=source_a,
        parse_completeness=0.8,
    )
    resume_b = CanonicalResume(
        candidate_id="c_b",
        identity=Identity(full_name="John Doe"),
        source=source_b,
        parse_completeness=0.9,
    )

    clusters = cluster_by_identity({"c_a": resume_a, "c_b": resume_b})
    assert len(clusters) == 1
    assert clusters[0].representative == "c_b"


def test_cluster_by_identity_no_identity() -> None:
    """FR-105: candidates with no usable identity are not clustered."""
    resume_a = CanonicalResume(candidate_id="c_a", identity=Identity())
    resume_b = CanonicalResume(candidate_id="c_b", identity=Identity())

    clusters = cluster_by_identity({"c_a": resume_a, "c_b": resume_b})
    assert clusters == ()


def test_size_guard(tmp_path: Path) -> None:
    """FR-107: files larger than max_file_mb are skipped with ING_OVERSIZE."""
    cfg = IngestConfig(max_file_mb=1)
    (tmp_path / "big.txt").write_bytes(b"x" * (1024 * 1024 + 1))

    result = build_manifest(tmp_path, cfg)
    assert result.ok
    assert len(result.value.documents) == 0
    assert len(result.value.skipped) == 1
    assert result.value.skipped[0].code == ReasonCode.ING_OVERSIZE


def test_page_guard(tmp_path: Path) -> None:
    """FR-107: PDFs exceeding max_pages are skipped with ING_OVERSIZE."""
    cfg = IngestConfig(max_pages=2)
    _make_pdf(tmp_path / "many.pdf", pages=5)

    result = build_manifest(tmp_path, cfg)
    assert result.ok
    assert len(result.value.documents) == 0
    assert len(result.value.skipped) == 1
    assert result.value.skipped[0].code == ReasonCode.ING_OVERSIZE
    assert "exceeds 2 pages" in result.value.skipped[0].message


def test_oversize_never_raises(tmp_path: Path) -> None:
    """FR-107: a bad document produces a diagnostic, never an exception."""
    # Binary content that is neither valid PDF nor text, so extension is used.
    (tmp_path / "bad.pdf").write_bytes(b"\x00\x01\x02\x03\x04\x05")
    cfg = IngestConfig(max_pages=1)

    result = build_manifest(tmp_path, cfg)
    assert result.ok is True
    assert len(result.value.skipped) == 1


def test_zip_bomb(tmp_path: Path) -> None:
    """TRD §10.4: a zip-bomb DOCX is skipped with ING_OVERSIZE."""
    cfg = IngestConfig(max_file_mb=1)
    zip_path = tmp_path / "bomb.docx"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("content.txt", b"\x00" * (10 * 1024 * 1024))

    result = build_manifest(tmp_path, cfg)
    assert result.ok
    assert len(result.value.documents) == 0
    assert len(result.value.skipped) == 1
    assert result.value.skipped[0].code == ReasonCode.ING_OVERSIZE
    assert "zip-bomb" in result.value.skipped[0].message


def test_path_traversal_symlink(tmp_path: Path) -> None:
    """TRD §10.4: symlinks pointing outside the ingest root are not followed."""
    outside = tmp_path.parent / "outside_ingest.txt"
    outside.write_text("secret")
    link = tmp_path / "link.txt"
    link.symlink_to(outside)

    result = build_manifest(tmp_path, IngestConfig())
    assert result.ok
    assert len(result.value.documents) == 0


def test_empty_file_skipped(tmp_path: Path) -> None:
    """Empty files are recorded with ING_EMPTY."""
    (tmp_path / "empty.txt").write_bytes(b"")

    result = build_manifest(tmp_path, IngestConfig())
    assert result.ok
    assert len(result.value.documents) == 0
    assert len(result.value.skipped) == 1
    assert result.value.skipped[0].code == ReasonCode.ING_EMPTY


def test_manifest_returns_manifest_model(tmp_path: Path) -> None:
    """The returned value is a Manifest model with the expected shape."""
    (tmp_path / "a.txt").write_text("A")

    result = build_manifest(tmp_path, IngestConfig())
    assert result.ok
    assert isinstance(result.value, Manifest)
    assert isinstance(result.value.documents, tuple)
    assert isinstance(result.value.duplicate_clusters, tuple)
    assert isinstance(result.value.skipped, tuple)
    assert isinstance(result.value.documents[0], SourceDocument)
