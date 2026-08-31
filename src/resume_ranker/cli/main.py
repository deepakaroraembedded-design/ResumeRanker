from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml  # type: ignore[import-untyped]

from resume_ranker import __version__
from resume_ranker.config import ConfigResolver
from resume_ranker.errors import ConfigurationError
from resume_ranker.models.run import RunContext, RunResult
from resume_ranker.models.scoring import ScoreCard
from resume_ranker.models.source import SourceDocument
from resume_ranker.pipeline import RunSettings, audit_run, build_pipeline, explain_scorecard

app = typer.Typer(
    name="resume-ranker",
    help="Resume screening and scoring engine",
    no_args_is_help=True,
)


def _load_jd_source(path: Path) -> str:
    """Read the job-description file as a string."""
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigurationError(f"cannot read job description {path}: {exc}") from exc


_MEDIA_TYPE_BY_SUFFIX: dict[str, str] = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/plain",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".rtf": "application/rtf",
    ".html": "text/html",
}

_RESUME_SUFFIXES: frozenset[str] = frozenset(_MEDIA_TYPE_BY_SUFFIX)


def _media_type_for(path: Path) -> str:
    """Return a media type for *path* based on its extension.

    This is a minimal wiring helper; full magic-byte detection is delegated to
    the ingest component in the integrated build.
    """
    return _MEDIA_TYPE_BY_SUFFIX.get(path.suffix.lower(), "application/octet-stream")


_JOB_DESCRIPTION_NAMES: frozenset[str] = frozenset({"jd", "job_description", "job-description"})


def _is_output_directory(directory: Path) -> bool:
    """Return True if *directory* looks like a previous run output directory."""
    return (directory / "run_manifest.json").is_file()


def _is_likely_job_description(path: Path) -> bool:
    """Return True if *path* looks like a job-description file, not a resume."""
    return path.stem.lower() in _JOB_DESCRIPTION_NAMES


def _load_source_documents(path: Path) -> list[SourceDocument]:
    """Create a simple source-document list from a directory scan.

    Only files with known resume extensions are included. Hidden files and
    directories, as well as directories that contain a previous run's
    ``run_manifest.json``, are skipped. This prevents output directories and
    other artefacts inside the input tree from being treated as candidate
    documents.

    Full ingestion (magic-byte detection, hashing, duplicate clustering) is
    delegated to the ingest component in the integrated build.
    """
    if not path.is_dir():
        raise ConfigurationError(f"input path is not a directory: {path}")
    docs: list[SourceDocument] = []
    for item in sorted(path.rglob("*")):
        if not item.is_file() or item.suffix.lower() not in _RESUME_SUFFIXES:
            continue
        if _is_likely_job_description(item):
            continue
        rel_parts = item.relative_to(path).parts
        if any(part.startswith(".") for part in rel_parts):
            continue
        if any(_is_output_directory(item.parents[i]) for i in range(len(rel_parts) - 1)):
            continue
        stat = item.stat()
        docs.append(
            SourceDocument(
                path=str(item.resolve()),
                content_sha256="",
                bytes=stat.st_size,
                pages=None,
                mtime="",
                media_type=_media_type_for(item),
            )
        )
    return docs


@dataclass(frozen=True)
class JobBundle:
    """A discovered JD folder paired with its mapped resume folder."""

    name: str
    jd_dir: Path
    jd_file: Path
    resumes_dir: Path


def _discover_job_bundles(root: Path) -> list[JobBundle]:
    """Discover ``JDx`` folders under *root* and pair each with ``RESUMESJDx``.

    Conventions (matching ``TESTDATA/JD1`` + ``TESTDATA/RESUMESJD1``):

    - A JD lives in a folder named ``JD<index>`` (case-insensitive prefix).
    - The JD file is the ``JD``/``jd``/``job_description`` text file inside it;
      if there is exactly one text file in the folder it is used as a fallback.
    - The mapped resume folder is a sibling named ``RESUMESJD<index>`` (or
      ``resumesJD<index>`` case-insensitive).

    Returns one bundle per JD folder that has both a JD file and a mapped
    resume folder.
    """
    bundles: list[JobBundle] = []
    if not root.is_dir():
        raise ConfigurationError(f"JD root is not a directory: {root}")
    for jd_dir in sorted(root.iterdir()):
        if not jd_dir.is_dir():
            continue
        name = jd_dir.name
        if not name.upper().startswith("JD"):
            continue
        jd_file = _find_jd_file(jd_dir)
        if jd_file is None:
            continue
        resumes_dir = _find_mapped_resumes_dir(root, name)
        if resumes_dir is None:
            continue
        bundles.append(
            JobBundle(
                name=name,
                jd_dir=jd_dir,
                jd_file=jd_file,
                resumes_dir=resumes_dir,
            )
        )
    return bundles


def _find_jd_file(jd_dir: Path) -> Path | None:
    """Return the job-description file inside *jd_dir*, or ``None``.

    Prefers a file whose stem is one of the known JD names; otherwise uses the
    single text file in the folder.
    """
    candidates = [p for p in jd_dir.iterdir() if p.is_file() and _is_likely_job_description(p)]
    if candidates:
        return sorted(candidates)[0]
    text_files = [
        p for p in jd_dir.iterdir() if p.is_file() and p.suffix.lower() in {".txt", ".md"}
    ]
    if len(text_files) == 1:
        return text_files[0]
    return None


def _find_mapped_resumes_dir(root: Path, jd_dir_name: str) -> Path | None:
    """Return the resume folder paired with a ``JDx`` folder, or ``None``.

    The pair name is ``RESUMES<dir-name>`` (e.g. ``JD1`` -> ``RESUMESJD1``);
    the comparison is case-insensitive so ``JD1`` also matches ``resumesJD1``.
    """
    expected = f"RESUMES{jd_dir_name}"
    for sibling in root.iterdir():
        if sibling.is_dir() and sibling.name.upper() == expected.upper():
            return sibling
    return None


@app.command()
def run(
    resumes: Annotated[Path, typer.Option(..., help="Directory of candidate resumes")],
    jd: Annotated[Path, typer.Option(..., help="Job description or pre-compiled JobSpec file")],
    out: Annotated[Path, typer.Option(help="Output directory")] = Path("./resume-ranker-out"),
    config: Annotated[Path | None, typer.Option(help="YAML configuration file")] = None,
    mode: Annotated[str, typer.Option(help="offline only")] = "offline",
    threshold: Annotated[float, typer.Option(help="Minimum composite score for selection")] = 70.0,
    top_n: Annotated[int | None, typer.Option(help="Select at most N candidates")] = None,
    blind: Annotated[bool, typer.Option(help="Redact identity attributes before scoring")] = True,
    workers: Annotated[int | None, typer.Option(help="Process-pool size")] = None,
    cache: Annotated[Path | None, typer.Option(help="Content-addressed cache directory")] = None,
    no_cache: Annotated[bool, typer.Option(help="Disable the cache")] = False,
    review_jobspec: Annotated[
        bool, typer.Option(help="Halt after JD compilation for review")
    ] = False,
    dry_run: Annotated[bool, typer.Option(help="Ingest and compile only; do not score")] = False,
    force: Annotated[bool, typer.Option(help="Overwrite a non-empty output directory")] = False,
    log_format: Annotated[str, typer.Option(help="auto | text | json")] = "auto",
) -> None:
    """Run the full RESUME-RANKER pipeline."""
    if resumes.resolve() == out.resolve():
        typer.echo("Output directory cannot be the input directory", err=True)
        raise typer.Exit(2)
    if out.exists() and any(out.iterdir()) and not force:
        typer.echo(f"Output directory exists and is non-empty: {out}", err=True)
        raise typer.Exit(7)

    try:
        cfg, cfg_hash = ConfigResolver(config).resolve(_cli_overrides(locals()))
    except ConfigurationError as exc:
        typer.echo(f"Configuration error: {exc}", err=True)
        raise typer.Exit(2) from exc

    if review_jobspec:
        typer.echo("--review-jobspec: compile and review the JobSpec, then exit.", err=True)
        raise typer.Exit(0)

    if dry_run:
        typer.echo("Dry run: ingestion and JobSpec compilation only.")
        pipeline = build_pipeline(cfg, mode)
        ctx = RunContext(run_id="dry-run")
        jd_source = _load_jd_source(jd)
        jd_result = pipeline.compile_jd(jd_source, ctx)
        if not jd_result.ok:
            typer.echo(f"JobSpec compilation failed: {jd_result.diagnostics}", err=True)
            raise typer.Exit(4)
        typer.echo(f"Would score {len(_load_source_documents(resumes))} document(s).")
        raise typer.Exit(0)

    docs = _load_source_documents(resumes)
    if not docs:
        typer.echo(f"No readable resumes found in {resumes}", err=True)
        raise typer.Exit(3)

    pipeline = build_pipeline(cfg, mode)
    jd_source = _load_jd_source(jd)
    settings = RunSettings(
        run_id="run_" + cfg_hash[:16],
        config=cfg,
        config_hash=cfg_hash,
        code_version=__version__,
        now="2026-08-29",
        output_dir=out,
    )
    result = pipeline.run(docs, jd_source, settings)
    failed_share = result.manifest.documents_failed / max(result.manifest.documents_in, 1)
    tolerance = 0.2  # TRD §10.3 default failure tolerance
    if failed_share > tolerance:
        typer.echo(f"Document failure rate exceeded tolerance: {failed_share:.1%}", err=True)
        raise typer.Exit(5)
    typer.echo(f"Run complete: {len(result.scorecards)} scorecard(s) written to {out}")


@app.command("run-all")
def run_all(
    root: Annotated[
        Path, typer.Option(help="Directory containing JDx and RESUMESJDx folders")
    ] = Path("./TESTDATA"),
    out: Annotated[Path, typer.Option(help="Output root directory")] = Path(
        "./resume-ranker-out-all"
    ),
    config: Annotated[Path | None, typer.Option(help="YAML configuration file")] = None,
    threshold: Annotated[float, typer.Option(help="Minimum composite score for selection")] = 70.0,
    top_n: Annotated[int | None, typer.Option(help="Select at most N candidates")] = None,
    blind: Annotated[bool, typer.Option(help="Redact identity attributes before scoring")] = True,
    force: Annotated[bool, typer.Option(help="Overwrite a non-empty output directory")] = False,
    dry_run: Annotated[bool, typer.Option(help="Ingest and compile only; do not score")] = False,
) -> None:
    """Run every discovered JDx folder against its mapped RESUMESJDx folder.

    Discovers ``JD<index>`` folders under *root*, pairs each with its
    ``RESUMESJD<index>`` sibling, and runs the full pipeline once per pair.
    Each job writes its artefacts to ``<out>/<JDx>/``.
    """
    try:
        cfg, cfg_hash = ConfigResolver(config).resolve(
            _cli_overrides({"threshold": threshold, "top_n": top_n, "blind": blind})
        )
    except ConfigurationError as exc:
        typer.echo(f"Configuration error: {exc}", err=True)
        raise typer.Exit(2) from exc

    bundles = _discover_job_bundles(root)
    if not bundles:
        typer.echo(f"No JD folders with mapped resume folders found under {root}", err=True)
        raise typer.Exit(3)

    typer.echo(f"Discovered {len(bundles)} job bundle(s): {', '.join(b.name for b in bundles)}")
    pipeline = build_pipeline(cfg, "offline")

    if dry_run:
        for bundle in bundles:
            n_docs = len(_load_source_documents(bundle.resumes_dir))
            typer.echo(
                f"[dry-run] {bundle.name}: JD={bundle.jd_file.name} "
                f"resumes={n_docs} -> {out / bundle.name}"
            )
        raise typer.Exit(0)

    failures: list[str] = []
    for bundle in bundles:
        bundle_out = out / bundle.name
        if bundle_out.exists() and any(bundle_out.iterdir()) and not force:
            typer.echo(f"Skipping {bundle.name}: output exists and is non-empty", err=True)
            failures.append(bundle.name)
            continue
        docs = _load_source_documents(bundle.resumes_dir)
        if not docs:
            typer.echo(f"Skipping {bundle.name}: no readable resumes found", err=True)
            failures.append(bundle.name)
            continue
        try:
            jd_source = _load_jd_source(bundle.jd_file)
            settings = RunSettings(
                run_id="run_" + cfg_hash[:16],
                config=cfg,
                config_hash=cfg_hash,
                code_version=__version__,
                now="2026-08-29",
                output_dir=bundle_out,
            )
            result = pipeline.run(docs, jd_source, settings)
            failed_share = result.manifest.documents_failed / max(result.manifest.documents_in, 1)
            if failed_share > 0.2:
                typer.echo(
                    f"{bundle.name}: document failure rate {failed_share:.1%} exceeded tolerance",
                    err=True,
                )
                failures.append(bundle.name)
                continue
            typer.echo(
                f"{bundle.name}: {len(result.scorecards)} scorecard(s) written to {bundle_out}"
            )
        except Exception as exc:  # noqa: BLE001 - a JD failure must not abort the batch
            typer.echo(f"{bundle.name}: run failed: {exc}", err=True)
            failures.append(bundle.name)

    if failures:
        typer.echo(f"Batch finished with {len(failures)} failed bundle(s): {', '.join(failures)}")
        raise typer.Exit(5)
    typer.echo(f"Batch complete: {len(bundles)} job bundle(s) processed.")


@app.command()
def parse(
    resumes: Annotated[Path, typer.Option(..., help="Directory of candidate resumes")],
    out: Annotated[Path, typer.Option(help="Output directory")] = Path("./resume-ranker-out"),
    config: Annotated[Path | None, typer.Option(help="YAML configuration file")] = None,
) -> None:
    """Extract and structure resumes without scoring."""
    try:
        cfg, _cfg_hash = ConfigResolver(config).resolve(_cli_overrides(locals()))
    except ConfigurationError as exc:
        typer.echo(f"Configuration error: {exc}", err=True)
        raise typer.Exit(2) from exc

    docs = _load_source_documents(resumes)
    if not docs:
        typer.echo(f"No readable resumes found in {resumes}", err=True)
        raise typer.Exit(3)

    pipeline = build_pipeline(cfg, "offline")
    ctx = RunContext(run_id="parse-run")
    out.mkdir(parents=True, exist_ok=True)
    for doc in docs:
        result = pipeline.parse(doc, ctx)
        if result.ok and result.value is not None:
            parsed_path = out / f"{result.value.candidate_id}.resume.json"
            parsed_path.write_text(result.value.model_dump_json(indent=2), encoding="utf-8")
    typer.echo(f"Parsed {len(docs)} document(s) to {out}")


@app.command()
def compile_jd(
    jd: Annotated[Path, typer.Option(..., help="Job description file")],
    out: Annotated[Path, typer.Option(help="Output JobSpec file")] = Path("./jobspec.yaml"),
    config: Annotated[Path | None, typer.Option(help="YAML configuration file")] = None,
) -> None:
    """Compile a job description into a reviewable JobSpec."""
    try:
        cfg, _cfg_hash = ConfigResolver(config).resolve(_cli_overrides(locals()))
    except ConfigurationError as exc:
        typer.echo(f"Configuration error: {exc}", err=True)
        raise typer.Exit(2) from exc

    pipeline = build_pipeline(cfg, "offline")
    jd_source = _load_jd_source(jd)
    ctx = RunContext(run_id="compile-jd")
    result = pipeline.compile_jd(jd_source, ctx)
    if not result.ok or result.value is None:
        typer.echo(f"JobSpec compilation failed: {result.diagnostics}", err=True)
        raise typer.Exit(4)
    out.write_text(yaml.safe_dump(result.value.model_dump(mode="json")), encoding="utf-8")
    typer.echo(f"JobSpec written to {out}")


@app.command()
def explain(
    out: Annotated[Path, typer.Option(..., help="Output directory from a run")],
    candidate: Annotated[str, typer.Option(..., help="Candidate identifier")],
) -> None:
    """Explain the score derivation for one candidate."""
    scorecard_path = out / "candidates" / f"{candidate}.scorecard.json"
    if not scorecard_path.exists():
        scorecard_path = out / f"{candidate}.scorecard.json"
    if not scorecard_path.exists():
        typer.echo(f"ScoreCard not found for candidate {candidate}", err=True)
        raise typer.Exit(2)

    try:
        scorecard = ScoreCard.model_validate_json(scorecard_path.read_text(encoding="utf-8"))
    except Exception as exc:
        typer.echo(f"Invalid scorecard: {exc}", err=True)
        raise typer.Exit(2) from exc

    explanation = explain_scorecard(scorecard)
    typer.echo(explanation)


@app.command()
def validate_config(
    config: Annotated[Path, typer.Option(..., help="YAML configuration file")],
) -> None:
    """Validate a configuration file and print the effective configuration."""
    if not config.exists():
        typer.echo(f"Configuration file not found: {config}", err=True)
        raise typer.Exit(2)
    try:
        cfg, cfg_hash = ConfigResolver(config).resolve(_cli_overrides({}))
    except ConfigurationError as exc:
        typer.echo(f"Configuration error: {exc}", err=True)
        raise typer.Exit(2) from exc
    typer.echo(yaml.safe_dump(cfg.model_dump(mode="json")))
    typer.echo(f"config_hash: {cfg_hash}")


@app.command()
def calibrate(
    resumes: Annotated[Path, typer.Option(..., help="Directory of labelled resumes")],
    out: Annotated[Path, typer.Option(help="Output file")] = Path("./calibration.yaml"),
    config: Annotated[Path | None, typer.Option(help="YAML configuration file")] = None,
) -> None:
    """Run the weight-tuning calibration procedure."""
    try:
        cfg, _cfg_hash = ConfigResolver(config).resolve(_cli_overrides(locals()))
    except ConfigurationError as exc:
        typer.echo(f"Configuration error: {exc}", err=True)
        raise typer.Exit(2) from exc

    pipeline = build_pipeline(cfg, "offline")
    ctx = RunContext(run_id="calibrate")
    report = pipeline.calibrate([], ctx)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    typer.echo(f"Calibration report written to {out}")


@app.command()
def audit(
    out: Annotated[Path, typer.Option(..., help="Output directory from a run")],
    demographics: Annotated[
        Path | None, typer.Option(help="Demographics CSV (candidate_id, group)")
    ] = None,
) -> None:
    """Audit a completed run and produce an adverse-impact report."""
    manifest_path = out / "run_manifest.json"
    if not manifest_path.exists():
        typer.echo(f"Run manifest not found in {out}", err=True)
        raise typer.Exit(2)
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not manifest_data.get("finished_at"):
        typer.echo("Run manifest is incomplete; cannot audit.", err=True)
        raise typer.Exit(2)

    scorecards: list[ScoreCard] = []
    candidates_dir = out / "candidates"
    if candidates_dir.exists():
        for path in sorted(candidates_dir.glob("*.scorecard.json")):
            try:
                scorecards.append(ScoreCard.model_validate_json(path.read_text(encoding="utf-8")))
            except Exception as exc:
                typer.echo(f"Warning: could not load scorecard {path}: {exc}", err=True)

    demo_data: dict[str, Any] | None = None
    if demographics:
        demo_data = {"file": str(demographics)}
        try:
            with demographics.open(newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                demo_data["mapping"] = {
                    row["candidate_id"]: row["group"]
                    for row in reader
                    if row.get("candidate_id") and row.get("group")
                }
        except OSError as exc:
            typer.echo(f"Cannot read demographics file {demographics}: {exc}", err=True)
            raise typer.Exit(2) from None

    result = RunResult(
        manifest=manifest_data,
        scorecards=tuple(scorecards),
    )
    report = audit_run(result, demo_data)
    typer.echo(json.dumps(report, indent=2))


def _cli_overrides(params: dict[str, Any]) -> dict[str, Any]:
    """Translate the CLI local variables into nested config overrides.

    Only scalar parameters that correspond to a RootConfig field are retained.
    """
    overrides: dict[str, Any] = {}
    if params.get("mode"):
        overrides["llm"] = {"mode": params["mode"]}
    if params.get("threshold") is not None:
        overrides["selection"] = {"threshold": params["threshold"]}
    if params.get("top_n") is not None:
        overrides["selection"] = overrides.get("selection", {})
        overrides["selection"]["top_n"] = params["top_n"]
    if params.get("blind") is not None:
        overrides["fairness"] = {"blind": params["blind"]}
    if params.get("workers") is not None:
        overrides["workers"] = params["workers"]
    return overrides


def main() -> None:
    """Entry point for the installed ``resume-ranker`` console script."""
    app()


if __name__ == "__main__":
    main()
