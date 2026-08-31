from __future__ import annotations

from pydantic import BaseModel, Field


class IngestConfig(BaseModel):
    """Configuration for the ingest stage."""

    include: tuple[str, ...] = (
        "**/*.pdf",
        "**/*.docx",
        "**/*.doc",
        "**/*.rtf",
        "**/*.txt",
        "**/*.md",
        "**/*.html",
    )
    exclude: tuple[str, ...] = ("**/~$*", "**/.*")
    max_file_mb: int = 25
    max_pages: int = 40
    simhash_hamming_max: int = 3
    match_on_contact: bool = True
    languages: tuple[str, ...] = ("en",)  # supported document languages (FR-209)
    office_converter_command: str | None = None  # soffice binary path (FR-208)
    office_converter_timeout_seconds: int = 60  # hard wall-clock timeout (FR-208)
    failure_tolerance: float = 0.20  # fraction of docs that may fail before exit 5


class ProficiencyFactors(BaseModel):
    """f_prof table from TRD §5.3.1."""

    applied_long: float = 1.00
    applied_short: float = 0.85
    listed_corroborated: float = 0.80
    listed_only: float = 0.55
    incidental: float = 0.40


class RecencyFactors(BaseModel):
    """Recency factor configuration."""

    half_life_years: float = 4.0
    half_life_timeless_years: float = 12.0
    floor: float = 0.50


class OverqualificationConfig(BaseModel):
    """Over-qualification decay configuration (disabled by default)."""

    enabled: bool = False
    cap: int = 15
    points_per_year: int = 3


class ExperienceConfig(BaseModel):
    """Experience-scoring configuration."""

    default_target_offset_years: int = 3
    count_internships: bool = False
    internship_duration_factor: float = 0.5
    overqualification: OverqualificationConfig = Field(default_factory=OverqualificationConfig)


class SemanticConfig(BaseModel):
    """Semantic scoring configuration."""

    embedding_share: float = 0.6
    pool_calibration_min_size: int = 30


class BandConfig(BaseModel):
    """Band thresholds from TRD §5.4."""

    strong: float = 85.0
    good: float = 70.0
    borderline: float = 55.0
    weak: float = 40.0


class ScoringConfig(BaseModel):
    """All scoring configuration in one place."""

    weights: dict[str, int] = Field(
        default_factory=lambda: {
            "S1": 30,
            "S2": 8,
            "S3": 18,
            "S4": 15,
            "S5": 8,
            "S6": 5,
            "S7": 7,
            "S8": 5,
            "S9": 2,
            "S10": 2,
        }
    )
    factors: ProficiencyFactors = Field(default_factory=ProficiencyFactors)
    recency: RecencyFactors = Field(default_factory=RecencyFactors)
    experience: ExperienceConfig = Field(default_factory=ExperienceConfig)
    semantic: SemanticConfig = Field(default_factory=SemanticConfig)
    bands: BandConfig = Field(default_factory=BandConfig)


class SelectionConfig(BaseModel):
    """Selection / threshold configuration."""

    threshold: float = 70.0
    top_n: int | None = None
    warn_if_selected_share_above: float = 0.40
    warn_if_knockout_excludes_share_above: float = 0.60


class IntegrityConfig(BaseModel):
    """Integrity detector configuration."""

    hidden_text_token_delta_share: float = 0.15
    min_font_pt: float = 4.0
    skills_token_share_max: float = 0.25
    keyword_repeat_max: int = 8
    penalties: dict[str, int] = Field(
        default_factory=lambda: {
            "hidden_text": 25,
            "injection_attempt": 25,
            "keyword_stuffing": 10,
        }
    )
    penalty_total_cap: int = 25


class FairnessConfig(BaseModel):
    """Fairness controls."""

    blind: bool = True
    redact: tuple[str, ...] = (
        "name",
        "email",
        "phone",
        "address",
        "photo",
        "dob",
        "gender",
        "nationality",
        "marital_status",
        "graduation_year",
        "affiliations",
    )
    redact_institution: bool = True
    forbid_knockouts_on: tuple[str, ...] = (
        "age",
        "gender",
        "nationality",
        "marital_status",
        "employment_gaps",
        "graduation_year",
    )
    penalise_employment_gaps: bool = False


class LLMConfig(BaseModel):
    """LLM adapter configuration."""

    mode: str = "hybrid"  # hybrid | offline
    provider: str | None = None
    model: str | None = None
    temperature: float = 0.0
    concurrency: int = 16
    timeout_s: float = 90.0
    max_retries: int = 3
    allow_degrade: bool = True
    price_per_mtok_in: float | None = None
    price_per_mtok_out: float | None = None


class EmbeddingConfig(BaseModel):
    """Embedding client configuration."""

    local: bool = True
    model: str | None = "Qwen/Qwen3-Embedding-8B"
    batch_size: int = 64


class OutputConfig(BaseModel):
    """Output artefact configuration."""

    formats: tuple[str, ...] = ("csv", "xlsx", "json", "html")
    copy_selected: bool = True
    retention_days: int = 180


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = "info"
    format: str = "auto"
    redact_pii: bool = True


class OntologyConfig(BaseModel):
    """Ontology/taxonomy data paths."""

    path: str = "data/ontology/2026.07"
    fuzzy_min_ratio: float = 92.0
    embedding_min_cosine: float = 0.82


class RootConfig(BaseModel):
    """Fully-resolved application configuration."""

    version: int = 1
    ingest: IngestConfig = Field(default_factory=IngestConfig)
    extraction: dict[str, object] = Field(default_factory=dict)
    ontology: OntologyConfig = Field(default_factory=OntologyConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    selection: SelectionConfig = Field(default_factory=SelectionConfig)
    bands: BandConfig = Field(default_factory=BandConfig)
    integrity: IntegrityConfig = Field(default_factory=IntegrityConfig)
    fairness: FairnessConfig = Field(default_factory=FairnessConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    embeddings: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
