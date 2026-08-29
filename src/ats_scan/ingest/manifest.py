from __future__ import annotations

import hashlib
import os
import re
import zipfile
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from ats_scan.codes import ReasonCode
from ats_scan.models.common import Diagnostic, StageResult
from ats_scan.models.config import IngestConfig
from ats_scan.models.resume import CanonicalResume
from ats_scan.models.source import SourceDocument

#: Number of bits in a SimHash fingerprint (FR-105).
_FINGERPRINT_BITS = 64

#: Byte chunk size used as a SimHash feature (FR-105).
_SIMHASH_CHUNK_SIZE = 4

#: Maximum bytes fed to SimHash to keep ingest fast (FR-105).
_SIMHASH_MAX_BYTES = 128 * 1024

#: How many bytes are read when sniffing magic numbers (FR-103).
_SNIFF_SIZE = 8192

#: Media types that the ingest stage recognises and hands to extractors.
_MEDIA_TYPES = frozenset(
    [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
        "application/rtf",
        "text/plain",
        "text/markdown",
        "text/html",
    ]
)

#: Extension-to-media-type fallback table (FR-103).
_MEDIA_BY_EXTENSION = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".rtf": "application/rtf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".html": "text/html",
    ".htm": "text/html",
}


class DuplicateCluster(BaseModel):
    """A group of duplicate or near-duplicate candidate documents.

    Attributes:
        representative: The candidate_id selected to represent the cluster
            (FR-106: highest parse_completeness, tie-break most recent mtime).
        documents: All candidate_ids in the cluster.
    """

    representative: str
    documents: tuple[str, ...] = Field(default_factory=tuple)


class Manifest(BaseModel):
    """Ingest output: discovered documents, duplicates, and skip records.

    Attributes:
        documents: Source documents accepted for further processing (FR-101).
        duplicate_clusters: Clusters of exact or near-duplicate documents
            (FR-105).
        skipped: Diagnostics for files that were rejected.
    """

    documents: tuple[SourceDocument, ...] = Field(default_factory=tuple)
    duplicate_clusters: tuple[DuplicateCluster, ...] = Field(default_factory=tuple)
    skipped: tuple[Diagnostic, ...] = Field(default_factory=tuple)


def build_manifest(root: Path, cfg: IngestConfig) -> StageResult[Manifest]:
    """Walk *root* and produce a stable ingest manifest.

    Implements FR-101 (recursive walk), FR-103 (magic-byte detection),
    FR-104 (content hash), FR-105 (hash and SimHash duplicate detection),
    FR-106 (cluster representative), FR-107 (size/page guards) and FR-108
    (symlink containment).

    Args:
        root: Directory to ingest.
        cfg: Ingest configuration.

    Returns:
        A StageResult containing the manifest or a diagnostic on failure.
    """
    try:
        root_resolved = root.resolve()
        paths = _walk_paths(root_resolved, cfg)
    except Exception as exc:  # pragma: no cover - programmer error path
        return StageResult(
            value=None,
            diagnostics=(
                Diagnostic(
                    stage="S1",
                    code=ReasonCode.ING_UNSUPPORTED_TYPE,
                    fatal=False,
                    message=f"cannot walk ingest root {root}: {exc}",
                ),
            ),
        )

    documents: list[SourceDocument] = []
    simhashes: list[int] = []
    skipped: list[Diagnostic] = []

    for path in paths:
        result = _process_file(path, root_resolved, cfg)
        if isinstance(result, Diagnostic):
            skipped.append(result)
            continue
        doc, simhash = result
        documents.append(doc)
        simhashes.append(simhash)

    duplicate_clusters = _build_duplicate_clusters(documents, simhashes, cfg)

    return StageResult(
        value=Manifest(
            documents=tuple(documents),
            duplicate_clusters=duplicate_clusters,
            skipped=tuple(skipped),
        )
    )


def cluster_by_identity(
    resumes: Mapping[str, CanonicalResume],
) -> tuple[DuplicateCluster, ...]:
    """Group candidates by normalised contact identity.

    This is exposed for the pipeline stage (C-15) to call *after* structuring,
    as contact-identity de-duplication cannot run before the resume is parsed
    (FR-105).  The cluster representative is chosen per FR-106.

    Args:
        resumes: Mapping from candidate_id to the structured resume.

    Returns:
        Duplicate clusters keyed by normalised identity.
    """
    groups: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for candidate_id, resume in resumes.items():
        key = _identity_key(resume)
        if key is not None:
            groups[key].append(candidate_id)

    docs_by_id: dict[str, SourceDocument] = {}
    completeness: dict[str, float] = {}
    for candidate_id, resume in resumes.items():
        if resume.source is not None:
            docs_by_id[candidate_id] = resume.source
        completeness[candidate_id] = resume.parse_completeness or 0.0

    clusters: list[DuplicateCluster] = []
    for members in groups.values():
        if len(members) > 1:
            representative = _choose_representative(members, docs_by_id, completeness)
            sorted_members = tuple(sorted(members))
            clusters.append(
                DuplicateCluster(representative=representative, documents=sorted_members)
            )

    return tuple(sorted(clusters, key=lambda cluster: cluster.representative))


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Translate a glob pattern with ``**`` support into a regex (FR-101)."""
    regex_parts: list[str] = []
    i = 0
    length = len(pattern)
    while i < length:
        if pattern[i : i + 2] == "**":
            if i + 2 < length and pattern[i + 2] == "/":
                regex_parts.append("(?:.*/)?")
                i += 3
            else:
                regex_parts.append(".*")
                i += 2
        elif pattern[i] == "*":
            regex_parts.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            regex_parts.append("[^/]")
            i += 1
        else:
            regex_parts.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(regex_parts) + "$")


def _match_glob(path: Path, compiled: re.Pattern[str]) -> bool:
    """Return True if *path* (relative to the ingest root) matches *compiled*."""
    return compiled.match(path.as_posix()) is not None


def _walk_paths(root: Path, cfg: IngestConfig) -> list[Path]:
    """Return a sorted, de-duplicated list of files under *root* (FR-101/108).

    Symlinks are followed only when their resolved target lies inside *root*.
    Globs from *cfg* are applied to paths relative to *root*; ``**`` matches
    zero or more directories so root-level files are included.
    """
    include = [_glob_to_regex(pattern) for pattern in cfg.include]
    exclude = [_glob_to_regex(pattern) for pattern in cfg.exclude]
    files: list[Path] = []
    seen: set[Path] = set()

    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current_dir = Path(dirpath)

        # Exclude directories matching an exclude pattern before descending.
        dirnames[:] = [
            dirname
            for dirname in dirnames
            if not any(_match_glob((current_dir / dirname).relative_to(root), rx) for rx in exclude)
        ]

        for filename in filenames:
            file_path = current_dir / filename
            try:
                resolved = file_path.resolve()
            except OSError:
                continue
            if not resolved.is_relative_to(root):
                continue
            rel_path = file_path.relative_to(root)
            if any(_match_glob(rel_path, rx) for rx in exclude):
                continue
            if not any(_match_glob(rel_path, rx) for rx in include):
                continue
            if resolved in seen:
                continue
            seen.add(resolved)
            files.append(file_path)

    return sorted(files)


def _process_file(
    path: Path, root: Path, cfg: IngestConfig
) -> tuple[SourceDocument, int] | Diagnostic:
    """Inspect a single file and return a SourceDocument plus SimHash, or a skip."""
    max_bytes = cfg.max_file_mb * 1024 * 1024

    try:
        size = path.stat().st_size
        if size == 0:
            return Diagnostic(
                stage="S1",
                code=ReasonCode.ING_EMPTY,
                fatal=False,
                message=f"empty file skipped: {path}",
            )
        if size > max_bytes:
            return Diagnostic(
                stage="S1",
                code=ReasonCode.ING_OVERSIZE,
                fatal=False,
                message=f"file exceeds {cfg.max_file_mb} MB: {path}",
            )

        media_type = _sniff_media_type(path)
        if media_type is None or media_type not in _MEDIA_TYPES:
            return Diagnostic(
                stage="S1",
                code=ReasonCode.ING_UNSUPPORTED_TYPE,
                fatal=False,
                message=f"unsupported media type: {path}",
            )

        if (
            media_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            and _is_zip_bomb(path, max_bytes)
        ):
            return Diagnostic(
                stage="S1",
                code=ReasonCode.ING_OVERSIZE,
                fatal=False,
                message=f"zip-bomb detected: {path}",
            )

        pages: int | None = None
        if media_type == "application/pdf":
            try:
                pages = _count_pdf_pages(path)
            except Exception as exc:
                return Diagnostic(
                    stage="S1",
                    code=ReasonCode.ING_UNSUPPORTED_TYPE,
                    fatal=False,
                    message=f"cannot read PDF page tree: {path}: {exc}",
                )
            if pages is not None and pages > cfg.max_pages:
                return Diagnostic(
                    stage="S1",
                    code=ReasonCode.ING_OVERSIZE,
                    fatal=False,
                    message=f"PDF exceeds {cfg.max_pages} pages: {path}",
                )

        content_sha256, simhash = _hash_and_fingerprint(path)
        mtime = _make_mtime(path)
    except Exception as exc:
        return Diagnostic(
            stage="S1",
            code=ReasonCode.ING_UNSUPPORTED_TYPE,
            fatal=False,
            message=f"cannot process {path}: {exc}",
        )

    return (
        SourceDocument(
            path=str(path.relative_to(root)),
            content_sha256=content_sha256,
            bytes=size,
            pages=pages,
            mtime=mtime,
            media_type=media_type,
        ),
        simhash,
    )


def _sniff_media_type(path: Path) -> str | None:
    """Detect media type from magic bytes; extension is only a fallback (FR-103)."""
    try:
        data = path.read_bytes()[:_SNIFF_SIZE]
    except OSError:
        return None

    if data.startswith(b"%PDF"):
        return "application/pdf"

    if data.startswith(b"PK\x03\x04"):
        docx = _docx_media_type(path)
        if docx is not None:
            return docx
        ext = path.suffix.lower()
        if ext == ".docx":
            return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        return None

    if data.startswith(b"\xd0\xcf\x11\xe0"):
        return "application/msword"

    if data.startswith(b"{\\rtf"):
        return "application/rtf"

    if data.startswith((b"<!DOCTYPE", b"<!doctype", b"<html", b"<HTML", b"<!--", b"<?xml")):
        return "text/html"

    if _is_text_content(data):
        ext = path.suffix.lower()
        if ext in {".md", ".html", ".htm"}:
            return _MEDIA_BY_EXTENSION[ext]
        return "text/plain"

    return _MEDIA_BY_EXTENSION.get(path.suffix.lower())


def _is_text_content(data: bytes) -> bool:
    """Return True if *data* appears to be plain text."""
    if not data:
        return True
    if b"\x00" in data:
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _docx_media_type(path: Path) -> str | None:
    """Return DOCX media type if *path* is a ZIP containing a Word document."""
    try:
        with zipfile.ZipFile(path) as zf:
            if _zip_contains_path_traversal(zf):
                return None
            if "[Content_Types].xml" in zf.namelist():
                content = zf.read("[Content_Types].xml")
                if b"wordprocessingml" in content:
                    return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    except (zipfile.BadZipFile, OSError):
        return None
    return None


def _is_zip_bomb(path: Path, max_bytes: int) -> bool:
    """Detect zip-bombs by central-directory sizes without decompressing (TRD §10.4)."""
    try:
        with zipfile.ZipFile(path) as zf:
            if _zip_contains_path_traversal(zf):
                return True
            total_uncompressed = 0
            total_compressed = 0
            for info in zf.infolist():
                total_uncompressed += info.file_size
                total_compressed += info.compress_size
                if info.file_size > max_bytes * 10:
                    return True
            if total_uncompressed > max_bytes:
                return True
            return total_compressed > 0 and total_uncompressed > total_compressed * 100
    except (zipfile.BadZipFile, OSError):
        return False


def _zip_contains_path_traversal(zf: zipfile.ZipFile) -> bool:
    """Return True if any ZIP entry tries to escape its target directory."""
    return any(name.startswith("/") or ".." in name.split("/") for name in zf.namelist())


def _count_pdf_pages(path: Path) -> int | None:
    """Read the PDF page tree only; no full parse (FR-107)."""
    import pymupdf as fitz

    doc = fitz.open(path)  # type: ignore[no-untyped-call]
    try:
        return int(doc.page_count)
    finally:
        doc.close()  # type: ignore[no-untyped-call]


def _hash_and_fingerprint(path: Path) -> tuple[str, int]:
    """Return SHA-256 hex digest and SimHash fingerprint for *path* (FR-104/105)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        data = f.read()
    h.update(data)
    return h.hexdigest(), _simhash(data)


def _simhash(data: bytes) -> int:
    """Return a 64-bit SimHash fingerprint for *data* (FR-105)."""
    if not data:
        return 0
    if len(data) > _SIMHASH_MAX_BYTES:
        data = data[:_SIMHASH_MAX_BYTES]

    weights = [0] * _FINGERPRINT_BITS
    for i in range(0, len(data) - _SIMHASH_CHUNK_SIZE + 1, _SIMHASH_CHUNK_SIZE):
        chunk = data[i : i + _SIMHASH_CHUNK_SIZE]
        h = _hash_chunk(chunk)
        for bit in range(_FINGERPRINT_BITS):
            if h & (1 << bit):
                weights[bit] += 1
            else:
                weights[bit] -= 1

    fingerprint = 0
    for bit, weight in enumerate(weights):
        if weight > 0:
            fingerprint |= 1 << bit
    return fingerprint


def _hash_chunk(chunk: bytes) -> int:
    """Deterministic 64-bit hash of a small byte chunk for SimHash."""
    digest = hashlib.blake2b(chunk, digest_size=8).digest()
    return int.from_bytes(digest, "big")


def _hamming_distance(a: int, b: int) -> int:
    """Return the Hamming distance between two 64-bit fingerprints."""
    return (a ^ b).bit_count()


def _build_duplicate_clusters(
    documents: Sequence[SourceDocument],
    simhashes: Sequence[int],
    cfg: IngestConfig,
) -> tuple[DuplicateCluster, ...]:
    """Group documents by exact hash or SimHash proximity (FR-105)."""
    n = len(documents)
    if n != len(simhashes):
        raise ValueError("documents and simhashes must have the same length")

    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        root_x, root_y = find(x), find(y)
        if root_x != root_y:
            parent[root_x] = root_y

    for i in range(n):
        for j in range(i + 1, n):
            if (
                documents[i].content_sha256 == documents[j].content_sha256
                or _hamming_distance(simhashes[i], simhashes[j]) <= cfg.simhash_hamming_max
            ):
                union(i, j)

    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)

    docs_by_id = {f"c_{doc.content_sha256[:8]}": doc for doc in documents}
    clusters: list[DuplicateCluster] = []

    for members in groups.values():
        if len(members) > 1:
            cids = sorted({f"c_{documents[i].content_sha256[:8]}" for i in members})
            representative = _choose_representative(cids, docs_by_id)
            clusters.append(DuplicateCluster(representative=representative, documents=tuple(cids)))

    return tuple(sorted(clusters, key=lambda cluster: cluster.representative))


def _choose_representative(
    candidate_ids: Sequence[str],
    docs_by_id: Mapping[str, SourceDocument],
    parse_completeness: Mapping[str, float] | None = None,
) -> str:
    """Return the cluster representative per FR-106.

    Highest parse_completeness wins; ties are broken by the most recent mtime.
    When parse_completeness is unavailable the score is treated as 0.0 and the
    mtime tie-break decides.
    """
    completeness = parse_completeness or {}

    def sort_key(candidate_id: str) -> tuple[float, str]:
        doc = docs_by_id.get(candidate_id)
        comp = completeness.get(candidate_id)
        if comp is None:
            comp = 0.0
        mtime = doc.mtime if doc is not None else ""
        return (comp, mtime)

    return max(candidate_ids, key=sort_key)


def _make_mtime(path: Path) -> str:
    """Return the file mtime as an ISO-8601 UTC string."""
    ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts, tz=UTC).replace(microsecond=0).isoformat()


def _identity_key(resume: CanonicalResume) -> tuple[str, ...] | None:
    """Build a normalised identity key for contact de-duplication (FR-105)."""
    if resume.identity is None:
        return None
    identity = resume.identity
    name = (identity.full_name or "").lower().strip()
    emails = tuple(sorted(email.lower().strip() for email in identity.emails))
    phones = tuple(sorted(re.sub(r"\D", "", phone) for phone in identity.phones))
    if not name and not emails and not phones:
        return None
    return (name,) + emails + phones
