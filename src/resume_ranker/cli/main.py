from __future__ import annotations

import csv
import json
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


def _media_type_for(path: Path) -> str:
    """Return a media type for *path* based on its extension.

    This is a minimal wiring helper; full magic-byte detection is delegated to
    the ingest component in the integrated build.
    """
    return _MEDIA_TYPE_BY_SUFFIX.get(path.suffix.lower(), "application/octet-stream")


def _load_source_documents(path: Path) -> list[SourceDocument]:
    """Create a simple source-document list from a directory scan.

    This is a minimal wiring helper used by the ``parse`` and ``run`` commands.
    Full ingestion (magic-byte detection, hashing, duplicate clustering) is
    delegated to the ingest component in the integrated build.
    """
    if not path.is_dir():
        raise ConfigurationError(f"input path is not a directory: {path}")
    docs: list[SourceDocument] = []
    for item in sorted(path.rglob("*")):
        if item.is_file():
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


@app.command()
def run(
    resumes: Annotated[Path, typer.Option(..., help="Directory of candidate resumes")],
    jd: Annotated[Path, typer.Option(..., help="Job description or pre-compiled JobSpec file")],
    out: Annotated[Path, typer.Option(help="Output directory")] = Path("./resume-ranker-out"),
    config: Annotated[Path | None, typer.Option(help="YAML configuration file")] = None,
    mode: Annotated[str, typer.Option(help="hybrid | offline")] = "hybrid",
    threshold: Annotated[float, typer.Option(help="Minimum composite score for selection")] = 70.0,
    top_n: Annotated[int | None, typer.Option(help="Select at most N candidates")] = None,
    blind: Annotated[bool, typer.Option(help="Redact identity attributes before scoring")] = True,
    workers: Annotated[int | None, typer.Option(help="Process-pool size")] = None,
    llm_concurrency: Annotated[int, typer.Option(help="Maximum in-flight LLM requests")] = 16,
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

    if mode == "hybrid" and cfg.llm.provider is None:
        typer.echo(
            "Hybrid mode requires an LLM provider; set --mode offline or configure llm.provider",
            err=True,
        )
        raise typer.Exit(6)

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
    if params.get("llm_concurrency") is not None:
        overrides["llm"] = overrides.get("llm", {})
        overrides["llm"]["concurrency"] = params["llm_concurrency"]
    return overrides


def main() -> None:
    """Entry point for the installed ``resume-ranker`` console script."""
    app()


if __name__ == "__main__":
    main()
