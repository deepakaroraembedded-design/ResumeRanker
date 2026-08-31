# RESUME-RANKER — Implementation Design & Multi-Agent Build Plan

| | |
|---|---|
| **Document** | Implementation design and parallel build plan |
| **System** | RESUME-RANKER — resume screening & scoring engine |
| **Companions** | *Technical Requirements & Design Document v1.0* (**TRD**) · *QA Plan & QA Agent Definition v1.0* (**QAP**) |
| **Version** | 1.1 |
| **Date** | 29 August 2026 |
| **Author** | Deepak Arora |
| **Build agent** | [opencode](https://opencode.ai) — 14 parallel component agents + 1 QA agent + 1 integrator |
| **Status** | Ready to execute once Wave 0 is signed off |

---

## 0. How to read this

The TRD says *what* to build. This document says *how the work is cut up*, *who owns which file*, and *how fourteen agents working simultaneously produce one coherent repository at the end*.

Three audiences:

- **The human orchestrator** — read §1, §5, §6, §7. That is the whole operating procedure.
- **Each component agent** — is pointed at §2 (ownership), §3 (contracts) and its own block in §4. It does not need the rest.
- **The QA agent** — reads §2.2 and §2.3 for defect routing and its own boundary, then works from `docs/QA_PLAN.md`.
- **The integrator agent** — reads §7 and §8.

Everything in §3 is **frozen** before any parallel work starts. That freeze is the single mechanism that makes parallelism safe; the rest of this document is bookkeeping around it.

---

## 1. Why this plan is shaped the way it is

Parallel AI agents fail on integration, not on implementation. Each agent writes plausible code; the code does not compose. The three recurring causes are: agents inventing slightly different versions of the same type, two agents editing the same file, and agents drifting apart on conventions no one wrote down. This plan attacks each one directly.

### 1.1 The three invariants

**Invariant 1 — Contracts are frozen before fan-out.**
Every type that crosses a component boundary (`CanonicalResume`, `JobSpec`, `ScoreCard`, `SubScore`, `Evidence`, `Diagnostic`) and every interface (`TextExtractor`, `Dimension`, `LLMClient`, …) is written, reviewed and tagged in Wave 0. After the tag `contracts-frozen`, **no component agent may modify anything under `src/resume_ranker/models/`, `protocols.py`, `errors.py` or `codes.py`.** An agent that believes a contract is wrong files a change request (§7.6) and does not edit it.

**Invariant 2 — Every file has exactly one owner.**
The ownership map in §2.2 assigns every path in the repository to exactly one component. Two agents never have write access to the same file. This is not a convention — it is checked mechanically before merge (§7.1) and enforced at import level by `import-linter` (§3.7).

**Invariant 3 — No shared registries, no shared mutable lists.**
The classic parallel-work conflict is ten agents each appending a line to the same `__init__.py`, enum, or settings file. Wave 0 removes every such file by construction: dimensions and extractors are discovered by directory scan, reason codes are declared per-package and collected, changelog entries are per-component files, and dependencies are pinned up front so nobody edits `pyproject.toml`. §3.5 gives the patterns.

### 1.2 What normally goes wrong, and the counter-measure

| Failure mode | Counter-measure |
|---|---|
| Two agents define their own `Resume` type | Wave 0 freezes the models; agents import, never define |
| Agent B blocked waiting for Agent A | Wave 0 ships a working **fake** for every protocol; B codes and tests against the fake |
| Merge conflicts in `__init__.py` / registries | Glob-based discovery; no central registration file (§3.4) |
| Agent adds a dependency, lockfile conflicts | All deps pinned in Wave 0; agents file a request instead (§3.5) |
| Agent "fixes" a contract to make its code work | Contracts are read-only after the freeze; change protocol in §7.6 |
| Everything is green, nothing works together | Integrator merges one component at a time, running the full gate after each (§7.2) |
| Agent silently reduces scope | Definition of Done is a checklist in §4, verified by the `contract-guard` subagent before merge |
| **Agent grades its own homework** — misreads a formula, writes tests that agree with the misreading, branch goes green | C-QA: an independent agent that derives a reference implementation from the TRD *before* reading the code, and mutation-tests the suite to prove it constrains anything (QAP §3, §4) |
| Scoring drifts from the specified formulas | Every dimension has a table-driven test whose expected values come from TRD §5, written in Wave 0 as **failing** tests |

That last row deserves emphasis. Wave 0 writes the scoring acceptance tests *before* the scoring agents start, taken directly from the formulas and the worked example in TRD §5.8. The agents' job is to make pre-existing failing tests pass. This is the strongest available defence against an agent inventing a formula that looks reasonable and is wrong.

---

## 2. Repository layout and the ownership map

### 2.1 Tree

```
resume-ranker/
├── AGENTS.md                     # shared agent rules            [W0]
├── opencode.json                 # agent + command definitions   [W0]
├── pyproject.toml  uv.lock       # ALL deps pinned in Wave 0     [W0]
├── Makefile  .importlinter       # the gate                      [W0]
├── .opencode/
│   ├── commands/build-component.md, review-branch.md, integrate.md
│   └── prompts/component-builder.md, integrator.md
├── changelog.d/                  # one newsfragment per component
├── data/
│   ├── ontology/2026.07/         # skills graph + aliases        [C-04]
│   └── titles/2026.07/           # title taxonomy                [C-04]
├── docs/
│   ├── IMPLEMENTATION_PLAN.md    # this file
│   ├── QA_PLAN.md                # QA plan + QA agent            [C-QA]
│   ├── contracts/                # generated JSON Schemas        [W0]
│   ├── dep-requests/C-xx.md      # one file per component
│   ├── contract-change/          # change requests               [see §7.6]
│   └── qa/                       # gate reports, defects, trace  [C-QA]
├── scripts/
│   ├── spawn-agents.sh  merge-components.sh  check-ownership.py  [W0]
│   └── qa/                       # oracle, mutation, trace tools [C-QA]
├── src/resume_ranker/
│   ├── models/                   # FROZEN domain types           [W0]
│   ├── protocols.py errors.py codes.py cache.py telemetry.py     [W0]
│   ├── ingest/                                                   [C-01]
│   ├── extract/
│   │   ├── __init__.py registry.py                               [W0]
│   │   ├── pdf/        ocr/                                      [C-02]
│   │   ├── office/     plain/                                    [C-03]
│   ├── ontology/                                                 [C-04]
│   ├── llm/                                                      [C-05]
│   ├── integrity/                                                [C-06]
│   ├── report/                                                   [C-07]
│   ├── structure/                                                [C-08]
│   ├── jobspec/                                                  [C-09]
│   ├── embeddings/                                               [C-11]
│   ├── scoring/
│   │   ├── __init__.py registry.py                               [W0]
│   │   ├── dimensions/__init__.py                                [W0]
│   │   ├── dimensions/s1_required_skills.py s2_preferred_skills.py
│   │   │                s8_skill_recency.py + evidence.py        [C-10]
│   │   ├── dimensions/s3_semantic.py                             [C-11]
│   │   ├── dimensions/s4_experience.py s5_title.py s6_domain.py
│   │   │                s7_education.py s9_trajectory.py
│   │   │                s10_parseability.py                      [C-12]
│   │   └── aggregate.py confidence.py bands.py tiebreak.py
│   │        filters.py                                           [C-13]
│   ├── fairness/                                                 [C-14]
│   ├── pipeline.py                                               [C-15]
│   ├── config/                                                   [C-15]
│   └── cli/                                                      [C-15]
└── tests/
    ├── conftest.py  fakes/  corpus/                               [W0]
    ├── unit/<component>/          # one dir per component
    ├── property/  golden/  adversarial/  fairness/
    ├── integration/  e2e/                                        [C-15]
    ├── benchmark/                                                [C-15]
    └── qa/                        # oracle, corpora, gates       [C-QA]
```

### 2.2 Ownership map

`[W0]` = written in Wave 0 and read-only thereafter. Every other path is exclusively writable by exactly one component agent.

| ID | Component | Exclusive write paths |
|---|---|---|
| **W0** | Foundation | `src/resume_ranker/models/**`, `protocols.py`, `errors.py`, `codes.py`, `cache.py`, `telemetry.py`, `*/registry.py`, `extract/__init__.py`, `scoring/__init__.py`, `scoring/dimensions/__init__.py`, `tests/conftest.py`, `tests/fakes/**`, `tests/corpus/**`, `pyproject.toml`, `uv.lock`, `Makefile`, `.importlinter`, `.github/**`, `AGENTS.md`, `opencode.json`, `.opencode/**`, `scripts/**` |
| **C-01** | Ingest & triage | `src/resume_ranker/ingest/**`, `tests/unit/ingest/**` |
| **C-02** | PDF & OCR extraction | `src/resume_ranker/extract/pdf/**`, `src/resume_ranker/extract/ocr/**`, `tests/unit/extract_pdf/**`, `tests/adversarial/test_pdf_*.py` |
| **C-03** | Office / plain / HTML extraction | `src/resume_ranker/extract/office/**`, `src/resume_ranker/extract/plain/**`, `tests/unit/extract_office/**` |
| **C-04** | Ontology & normalisation | `src/resume_ranker/ontology/**`, `data/ontology/**`, `data/titles/**`, `tests/unit/ontology/**`, `tests/property/test_ontology_*.py` |
| **C-05** | LLM adapter & prompts | `src/resume_ranker/llm/**`, `tests/unit/llm/**` |
| **C-06** | Integrity detectors | `src/resume_ranker/integrity/**`, `tests/unit/integrity/**`, `tests/adversarial/test_integrity_*.py` |
| **C-07** | Report writers | `src/resume_ranker/report/**`, `tests/unit/report/**` |
| **C-08** | Resume structuring | `src/resume_ranker/structure/**`, `tests/unit/structure/**`, `tests/golden/structure/**` |
| **C-09** | JobSpec compiler | `src/resume_ranker/jobspec/**`, `tests/unit/jobspec/**` |
| **C-10** | Scoring — evidence dims | `src/resume_ranker/scoring/evidence.py`, `scoring/dimensions/s1_required_skills.py`, `s2_preferred_skills.py`, `s8_skill_recency.py`, `tests/unit/scoring_evidence/**` |
| **C-11** | Scoring — semantic + embeddings | `src/resume_ranker/embeddings/**`, `scoring/dimensions/s3_semantic.py`, `tests/unit/scoring_semantic/**` |
| **C-12** | Scoring — profile dims | `scoring/dimensions/s4_experience.py`, `s5_title.py`, `s6_domain.py`, `s7_education.py`, `s9_trajectory.py`, `s10_parseability.py`, `tests/unit/scoring_profile/**` |
| **C-13** | Aggregation & filters | `src/resume_ranker/scoring/aggregate.py`, `confidence.py`, `bands.py`, `tiebreak.py`, `filters.py`, `tests/unit/scoring_aggregate/**`, `tests/property/test_aggregate_*.py` |
| **C-14** | Fairness | `src/resume_ranker/fairness/**`, `tests/fairness/**` |
| **C-15** | CLI, config, pipeline | `src/resume_ranker/cli/**`, `src/resume_ranker/config/**`, `src/resume_ranker/pipeline.py`, `tests/integration/**`, `tests/e2e/**`, `tests/benchmark/**` |
| **C-QA** | Independent verification | `tests/qa/**`, `docs/qa/**`, `scripts/qa/**` — see **QAP** |

Beyond the table, three naming rules close the remaining gaps. They exist so that no path is ever unowned, which is the condition `scripts/check-ownership.py` actually enforces.

**Per-component files.** Every component owns two scratch files named after itself, which keep append-only information out of shared files:

```
changelog.d/<ID>.<type>.md      # newsfragment: feature | fix | doc
docs/dep-requests/<ID>.md       # third-party packages the component wants
```

**Test placement.** A component's tests live under paths keyed to that component, whatever the test *kind*:

```
tests/unit/<component-dir>/**          # unit AND property tests, by default
tests/golden/<component-dir>/**        # golden-file tests
tests/adversarial/test_<prefix>_*.py   # only where the table grants the prefix
tests/property/test_<prefix>_*.py      # only where the table grants the prefix
tests/fairness/**                      # C-14 only
```

So C-12's counterfactual fairness tests live in `tests/unit/scoring_profile/`, not in `tests/fairness/`. The cross-cutting directories are shared surfaces and are granted by explicit glob in the table above — nowhere else. `tests/integration/`, `tests/e2e/` and `tests/benchmark/` belong to C-15 alone, because they are the only places two real components meet.

**Test fixtures.** Wave 0 owns `tests/corpus/`. A component needing a new fixture adds it under its own test directory; fixtures that more than one component needs are a Wave-0 request, not a copy-paste.

### 2.3 Files no agent may touch

Beyond the `[W0]` list: no agent creates a file at the repository root, and no agent edits another component's tests to make its own pass. Both are ownership violations and are caught by `scripts/check-ownership.py` before merge.

**The QA wall is two-way and absolute.** No component agent may write anything under `tests/qa/**`, and the QA agent may not write anything under `src/**`. QA *reads* `src/` freely — it cannot triage a defect otherwise — but it files defects rather than fixing them. The rationale, and the one exception (the blind-derivation rule for the reference oracle), are in **QAP §1.1** and **§3.2**.

The reason this boundary is worth a hard rule: every component agent writes its own tests, which means an agent that misreads a formula writes tests agreeing with the misreading, and the branch goes green. C-QA exists to be the party that has not read the implementation before forming an expectation.

---

## 3. Wave 0 — the contract freeze

**One agent. Serial. Nothing else starts until this is tagged.** Budget: one focused session, human-reviewed. This is the highest-leverage work in the whole plan; do not delegate it to a fast model and do not rush the review.

### 3.1 Deliverables

1. Repository skeleton, `pyproject.toml` with **every** dependency from TRD §14 pinned, `uv.lock` committed.
2. Frozen domain models (§3.2) with generated JSON Schemas in `docs/contracts/`.
3. Frozen protocols (§3.3).
4. Registry mechanisms that need no central edits (§3.4, §3.5).
5. A working fake for every protocol, in `tests/fakes/` (§3.6).
6. Test fixtures: 40 synthetic resumes, 5 job descriptions, 12 adversarial documents.
7. **Pre-written failing tests** for every scoring formula in TRD §5, marked `xfail(strict=True)`.
8. `make gate` and the `import-linter` contracts (§3.7).
9. `AGENTS.md`, `opencode.json`, the command files, and `scripts/spawn-agents.sh`.
10. Tag `contracts-frozen` on `main`.

### 3.2 Frozen domain models

`src/resume_ranker/models/` — Pydantic v2 models mirroring TRD §4 exactly, one module per aggregate:

```
models/
  source.py       SourceDocument, ExtractionMetadata, ExtractedText, TextBlock
  resume.py       CanonicalResume, Identity, ExperienceEntry, EducationEntry,
                  Certification, SkillMention, Timeline, DateValue, DatePrecision
  jobspec.py      JobSpec, RequiredSkill, PreferredSkill, KnockoutRule,
                  ResponsibilityChunk, ExperienceRequirement, EducationRequirement
  scoring.py      SubScore, Evidence, ScoreCard, KnockoutResult, Band, MatchRoute
  run.py          RunContext, ScoringContext, RunResult, RunManifest, Provenance
  common.py       Diagnostic, StageResult, IntegrityFinding, ReidentificationMap
```

Non-negotiable modelling decisions, because they change every downstream signature:

```python
# models/scoring.py
@dataclass(frozen=True, slots=True)
class Evidence:
    span: tuple[int, int]          # char offsets into ExtractedText.text
    quote: str                     # MUST equal text[span[0]:span[1]]
    page: int | None = None
    source: Literal["resume", "jobspec"] = "resume"

@dataclass(frozen=True, slots=True)
class SubScore:
    dimension: str                       # "S1".."S10"
    value: float | None                  # None => unavailable, weight redistributed
    evidence: tuple[Evidence, ...] = ()
    detail: Mapping[str, object] = field(default_factory=dict)
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.value is not None and not 0.0 <= self.value <= 100.0:
            raise ValueError(f"{self.dimension} out of range: {self.value}")
```

```python
# models/common.py
@dataclass(frozen=True, slots=True)
class Diagnostic:
    stage: str                     # "S1".."S9" pipeline stage, not dimension
    code: str                      # from the collected reason-code registry
    message: str
    fatal: bool = False

T = TypeVar("T")

@dataclass(frozen=True, slots=True)
class StageResult(Generic[T]):
    """Every stage returns this. A stage NEVER raises for bad input data —
    it returns value=None plus diagnostics. Raising is reserved for defects."""
    value: T | None
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def ok(self) -> bool:
        return self.value is not None
```

`SubScore.value = None` and `StageResult` together implement the TRD's "degrade, never abort" rule (TRD §2.5, §10.3). Agents must not invent an alternative error channel.

### 3.3 Frozen protocols

`src/resume_ranker/protocols.py` — the complete list. Each component implements one or more of these and depends only on the others' protocol, never on their implementation.

```python
@runtime_checkable
class TextExtractor(Protocol):
    media_types: ClassVar[frozenset[str]]
    def supports(self, doc: SourceDocument) -> bool: ...
    def extract(self, doc: SourceDocument, ctx: RunContext) -> StageResult[ExtractedText]: ...

@runtime_checkable
class Structurer(Protocol):
    def structure(self, text: ExtractedText, ctx: RunContext) -> StageResult[CanonicalResume]: ...

@runtime_checkable
class JobSpecCompiler(Protocol):
    def compile(self, source: str, ctx: RunContext) -> StageResult[JobSpec]: ...

@runtime_checkable
class OntologyIndex(Protocol):
    version: str
    def canonicalise(self, raw: str) -> SkillMatch | None: ...
    def relation(self, candidate: str, target: str) -> SkillRelation: ...   # EXACT|ALIAS|CHILD|PARENT|FUZZY|EMBEDDING|NONE
    def is_timeless(self, canonical: str) -> bool: ...

@runtime_checkable
class TitleTaxonomy(Protocol):
    def normalise(self, raw_title: str) -> TitleMatch | None: ...
    def similarity(self, a: TitleMatch, b: TitleMatch) -> float: ...        # 1.0 | 0.8 | 0.55 | 0.15
    def seniority_gap(self, role: TitleMatch, target: TitleMatch) -> int: ...

@runtime_checkable
class Dimension(Protocol):
    id: ClassVar[str]                       # "S1".."S10"
    name: ClassVar[str]
    requires: ClassVar[frozenset[str]]      # capability tags, e.g. {"embeddings", "llm"}
    def score(self, resume: CanonicalResume, spec: JobSpec,
              ctx: ScoringContext) -> SubScore: ...

@runtime_checkable
class LLMClient(Protocol):
    async def structured(self, *, template: str, variables: Mapping[str, object],
                         schema: type[T], samples: int = 1,
                         trace: str) -> StageResult[LLMResult[T]]: ...

@runtime_checkable
class EmbeddingClient(Protocol):
    dimensions: int
    async def embed(self, texts: Sequence[str]) -> Sequence[Vector]: ...

@runtime_checkable
class IntegrityDetector(Protocol):
    code: ClassVar[str]
    def inspect(self, doc: SourceDocument, text: ExtractedText,
                resume: CanonicalResume | None) -> Sequence[IntegrityFinding]: ...

@runtime_checkable
class Redactor(Protocol):
    def redact(self, resume: CanonicalResume) -> tuple[CanonicalResume, ReidentificationMap]: ...

@runtime_checkable
class ReportWriter(Protocol):
    artefact: ClassVar[str]                 # "scores.csv", "report.html", ...
    def write(self, run: RunResult, out_dir: Path) -> StageResult[Path]: ...
```

`ScoringContext` is the only channel through which a dimension reaches shared services. It is frozen too, and it is deliberately narrow:

```python
@dataclass(frozen=True, slots=True)
class ScoringContext:
    ontology: OntologyIndex
    titles: TitleTaxonomy
    embeddings: EmbeddingClient | None      # None in offline mode w/o local model
    llm: LLMClient | None                   # None in offline mode
    config: ScoringConfig
    pool: PoolStatistics                    # percentiles for S3 calibration
    now: date                               # never call date.today() in a dimension
```

`now` being injected is what makes recency scoring reproducible; a dimension that calls `date.today()` fails the determinism test.

### 3.4 The dimension and extractor registries

No component ever edits a registration file. Registration is by decorator plus directory scan:

```python
# src/resume_ranker/scoring/registry.py                                   [W0, read-only]
_REGISTRY: dict[str, Dimension] = {}

def dimension(cls: type[Dimension]) -> type[Dimension]:
    inst = cls()
    if inst.id in _REGISTRY:
        raise RuntimeError(f"duplicate dimension id {inst.id}")
    _REGISTRY[inst.id] = inst
    return cls

def load_dimensions() -> Mapping[str, Dimension]:
    pkg = importlib.import_module("resume_ranker.scoring.dimensions")
    for mod in pkgutil.iter_modules(pkg.__path__):
        importlib.import_module(f"{pkg.__name__}.{mod.name}")
    return MappingProxyType(_REGISTRY)
```

A dimension agent writes exactly one new file and touches nothing else:

```python
# src/resume_ranker/scoring/dimensions/s1_required_skills.py              [C-10]
from resume_ranker.scoring.registry import dimension

@dimension
class S1RequiredSkills:
    id = "S1"
    name = "Required skills coverage"
    requires = frozenset()
    def score(self, resume, spec, ctx) -> SubScore: ...
```

`src/resume_ranker/extract/registry.py` uses the same pattern over `resume_ranker.extract.*` subpackages and dispatches on `TextExtractor.supports()`. This is why C-02 and C-03 can add extractors concurrently without ever meeting in a file.

### 3.5 Conflict-free aggregation patterns

| Shared thing | Naive approach (conflicts) | Pattern used here |
|---|---|---|
| Dimension / extractor registration | append to `__init__.py` | decorator + `pkgutil` scan (§3.4) |
| Reason codes | one central `StrEnum` | per-package `codes.py` defining a `StrEnum`; `resume_ranker/codes.py` collects them by scan and a Wave-0 test asserts global uniqueness |
| Changelog | one `CHANGELOG.md` | towncrier newsfragments: `changelog.d/C-04.feature.md`; integrator assembles at the end |
| Dependencies | each agent edits `pyproject.toml` | **all deps pinned in Wave 0.** An agent needing another writes `docs/dep-requests/C-04.md` and uses a stdlib workaround or stops; the integrator batches additions |
| Config schema | one settings class | each package owns `config.py` with its own Pydantic sub-model; `config/root.py` (C-15) composes them by scan |
| Test fixtures | shared `conftest.py` | Wave 0 owns the root `conftest.py`; each component adds `tests/unit/<comp>/conftest.py` |

### 3.6 Fakes

`tests/fakes/` ships a deterministic implementation of every protocol so that no agent is ever blocked on another:

- `FakeLLMClient` — replays canned JSON keyed by `(template, hash(variables))`; raises on an unrecognised key so an agent cannot silently depend on unspecified behaviour.
- `FakeEmbeddingClient` — deterministic hash-based vectors with a fixed, documented similarity structure (`"python"` and `"py"` at cosine 0.91, and so on) so S3 tests have stable expected values.
- `FakeOntology` — 200 canonical skills, aliases, and one parent/child chain per relation type.
- `FakeExtractor`, `FakeRedactor`, `FakeReportWriter`, `StubDimension(value=…)`.

Rule for agents: **test against the fake, never against a sibling's real implementation.** Cross-component behaviour is verified once, by the integrator, in `tests/integration/`.

### 3.7 The gate

```make
gate: fmt lint types imports test schema
lint:     ruff check src tests
fmt:      ruff format --check src tests
types:    mypy --strict src
imports:  lint-imports                       # import-linter contracts
test:     pytest -m "not slow" --cov=resume_ranker --cov-fail-under=85
schema:   python scripts/validate_schemas.py docs/contracts src
own:      python scripts/check-ownership.py  # branch touched only its own paths
```

`.importlinter` encodes the architecture as machine-checked layers, so an agent physically cannot import across a boundary it does not own:

```ini
[importlinter]
root_package = resume_ranker

[importlinter:contract:layers]
name = Layered architecture
type = layers
layers =
    resume_ranker.cli
    resume_ranker.pipeline
    resume_ranker.report
    resume_ranker.scoring
    resume_ranker.fairness : resume_ranker.integrity
    resume_ranker.structure : resume_ranker.jobspec
    resume_ranker.extract : resume_ranker.ingest
    resume_ranker.ontology : resume_ranker.embeddings : resume_ranker.llm
    resume_ranker.models : resume_ranker.protocols : resume_ranker.errors : resume_ranker.codes

[importlinter:contract:dimension-independence]
name = Scoring dimensions never import one another
type = independence
modules =
    resume_ranker.scoring.dimensions.s1_required_skills
    resume_ranker.scoring.dimensions.s2_preferred_skills
    resume_ranker.scoring.dimensions.s3_semantic
    resume_ranker.scoring.dimensions.s4_experience
    resume_ranker.scoring.dimensions.s5_title
    resume_ranker.scoring.dimensions.s6_domain
    resume_ranker.scoring.dimensions.s7_education
    resume_ranker.scoring.dimensions.s8_skill_recency
    resume_ranker.scoring.dimensions.s9_trajectory
    resume_ranker.scoring.dimensions.s10_parseability

[importlinter:contract:no-clock-in-scoring]
name = Scoring must take time from ScoringContext
type = forbidden
source_modules = resume_ranker.scoring
forbidden_modules = time
```

### 3.8 Wave 0 exit criteria

- [ ] `make gate` green on an otherwise empty implementation (all real modules raise `NotImplementedError`).
- [ ] Every protocol has a fake, and `test_fakes_satisfy_protocols.py` passes with `runtime_checkable` assertions.
- [ ] Scoring acceptance tests exist and are `xfail(strict=True)` — including the TRD §5.8 worked example asserting a composite of **87.06**.
- [ ] JSON Schemas generated and committed; round-trip test passes.
- [ ] Ownership map in `scripts/check-ownership.py` matches §2.2 exactly.
- [ ] A human has reviewed the models and protocols. **This review is the gate. Do not skip it.**
- [ ] `git tag contracts-frozen`.

---

## 4. Component catalogue

Each block is what its agent is given, verbatim, alongside §2.2 and §3.

---

### C-01 — Ingest & triage
**Wave 1** · **Implements** — (no protocol; exposes a function) · **Size** ≈ 600 LOC + 400 test

Walks the input directory, sniffs types by magic bytes, hashes, detects duplicates and near-duplicates, applies size and page guards, and emits a manifest. Never reads document *content* semantically — that is C-02/C-03.

**Public API**
```python
def build_manifest(root: Path, cfg: IngestConfig) -> StageResult[Manifest]: ...
# Manifest.documents: tuple[SourceDocument, ...]
# Manifest.duplicate_clusters: tuple[DuplicateCluster, ...]
# Manifest.skipped: tuple[Diagnostic, ...]
```

**Definition of Done**
- [ ] Recursive walk with include/exclude globs; symlinks never followed outside root (FR-101, FR-108)
- [ ] Magic-byte type detection overrides extension; mislabelled-file test passes (FR-103)
- [ ] SHA-256 content hash → `candidate_id = "c_" + sha[:8]` (FR-104)
- [ ] Duplicate detection: exact hash, normalised contact identity, SimHash ≤ 3 Hamming (FR-105)
- [ ] Cluster representative = highest `parse_completeness`, tie-break most recent mtime (FR-106)
- [ ] Size and page guards emit `ING_OVERSIZE`, never raise (FR-107)
- [ ] Property test: manifest order is stable across runs regardless of filesystem order
- [ ] Zip-bomb and path-traversal fixtures handled (TRD §10.4)

**Gotchas.** Page count for the guard must not require a full parse — read the PDF page tree only. Contact-identity de-duplication runs *after* structuring in the real pipeline, so expose `cluster_by_identity()` separately for C-15 to call later; the manifest pass does hash and SimHash only.

---

### C-02 — PDF & OCR extraction
**Wave 1** · **Implements** `TextExtractor` ×2 · **Size** ≈ 1,100 LOC + 700 test · *Largest wave-1 component; give it the strongest model.*

**Public API** — registers `PdfExtractor` and `OcrPdfExtractor` with `extract.registry`.

**Definition of Done**
- [ ] Text-layer extraction with per-glyph position, colour, size and render mode retained (FR-205; required by C-06)
- [ ] OCR fallback triggered below the configured chars-per-page threshold or on a legibility check (FR-201)
- [ ] Multi-column reading order by x-clustering, columns before rows (FR-202)
- [ ] Table cells emitted row-wise, not column-interleaved (FR-203)
- [ ] Repeated headers/footers detected and dropped (FR-204)
- [ ] `ExtractionMetadata` populated: chars/page, OCR confidence, column count, text-layer present (FR-206)
- [ ] Encrypted PDFs → `EXT_ENCRYPTED` diagnostic, no decryption attempted (FR-207)
- [ ] Unicode NFKC, ligature repair, zero-width and bidi control stripping (FR-210)
- [ ] `render_page_tokens()` exposed for C-06's text-layer/OCR corroboration
- [ ] Golden tests over the 12 fixture PDFs including two-column, tabular, and scanned
- [ ] `Evidence.quote == text[span]` holds for every emitted block (property test)

**Gotchas.** Span offsets are into the *final* normalised text, not the raw extraction — normalise first, then index. Getting this wrong breaks every downstream evidence citation. OCR concurrency is capped separately (TRD §10.2); expose it as config, do not spawn freely.

---

### C-03 — Office, RTF, plain-text & HTML extraction
**Wave 1** · **Implements** `TextExtractor` ×4 · **Size** ≈ 500 LOC + 350 test

**Definition of Done**
- [ ] `.docx` via python-docx including tables and headers; `.doc`/`.rtf` via headless converter with networking and macros disabled and a hard timeout (FR-208)
- [ ] `.txt`, `.md`, `.html` extractors; HTML stripped to text with block structure preserved
- [ ] Language detection populated on every result (FR-209)
- [ ] Same Unicode normalisation contract as C-02 — **import the shared helper from `models/source.py`, do not reimplement**
- [ ] Converter failure → diagnostic, never an exception escaping the extractor
- [ ] Timeout test proves the converter is killed and the run continues

---

### C-04 — Ontology & normalisation
**Wave 1** · **Implements** `OntologyIndex`, `TitleTaxonomy` · **Size** ≈ 900 LOC + 500 test + data

Also ships the versioned data files. Everything downstream of skill matching depends on this being right, so it is a Wave-1 priority merge.

**Definition of Done**
- [ ] Match cascade in the exact order of FR-501: exact → alias → case/punct-insensitive → fuzzy ≥ 92 → embedding ≥ 0.82; `SkillMatch.route` records which fired
- [ ] Parent/child relations; `is_timeless()` backed by an ontology flag (FR-502, TRD §5.3.1)
- [ ] Ontology is data, version string exposed, no skills hard-coded in Python (FR-503)
- [ ] Title normalisation to family + seniority, handling inflated titles ("Ninja", "Rockstar", "Associate Director II") (FR-504)
- [ ] Employer normalisation: legal-suffix stripping, alias map (FR-505)
- [ ] Unmapped strings returned as `None`, never guessed; caller keeps them as free-text (FR-506)
- [ ] `data/ontology/2026.07/` seeded with ≥ 1,500 canonical skills covering the five pilot role families
- [ ] Property test: `canonicalise` is idempotent and case-stable
- [ ] Benchmark: 10,000 lookups < 200 ms warm

**Gotchas.** The embedding tier must be lazy — `OntologyIndex` takes an optional `EmbeddingClient` and skips that tier when it is `None` (offline mode without a local model). Do not make the ontology import `resume_ranker.embeddings`; take the client through the constructor. `import-linter` will fail you otherwise.

---

### C-05 — LLM adapter, prompt templates & response cache
**Wave 1** · **Implements** `LLMClient` · **Size** ≈ 800 LOC + 600 test

**Definition of Done**
- [ ] Provider-agnostic adapter; provider selected by config, no provider SDK imported at module scope
- [ ] Schema-constrained calls with validation, one repair retry, then one reduced-scope retry, then `StageResult(value=None, LLM_DEGRADED)` (FR-307, TRD §6.2)
- [ ] Evidence-span verification: any returned span is checked against the source text and the field dropped if it does not match (FR-306)
- [ ] Prompt templates for `E-PARSE`, `E-JD`, `R-SEM`, `R-TRANS`, `G-EXPL` as versioned files under `llm/prompts/`, version in the cache key
- [ ] Injection hardening: nonce-delimited content blocks, data-not-instructions system prompt, control-character stripping, length caps, quarantined-span removal (TRD §6.4)
- [ ] Cache keyed on SHA-256 of (model id, template version, rendered prompt); SQLite-backed
- [ ] Bounded concurrency semaphore, exponential backoff with jitter on 429/5xx, per-call timeout
- [ ] Token and cost accounting exposed per run
- [ ] `temperature=0` enforced in code, not left to config
- [ ] Tests use a recorded-response transport; **no test makes a network call**

**Gotchas.** `samples > 1` must issue genuinely independent requests and return all of them — C-11 needs the spread for `model_agreement` in the confidence formula. Do not deduplicate them via the cache; include the sample index in the cache key.

---

### C-06 — Integrity detectors
**Wave 1** · **Implements** `IntegrityDetector` ×3 · **Size** ≈ 700 LOC + 600 test (adversarial-heavy)

**Definition of Done**
- [ ] `HiddenTextDetector`: colour within ΔE < 5 of background, font < 4 pt, render mode 3, text outside media box (FR-1101)
- [ ] Text-layer vs OCR corroboration; token-set difference > 15 % raises `HIDDEN_TEXT` (FR-1102)
- [ ] `KeywordStuffingDetector`: skills-section token share, repetition without context, claimed-but-unnarrated skills (FR-1103)
- [ ] `InjectionDetector`: instruction-like content aimed at a model; returns exact spans for quarantine (FR-1104)
- [ ] Findings carry spans and quotes; **detectors never apply penalties** — that is C-13 (FR-1106)
- [ ] Adversarial corpus: hidden-text recall ≥ 0.95, injection recall ≥ 0.98 (TRD §13.3)
- [ ] False-positive test: 40 clean fixture resumes produce zero findings

**Gotchas.** The hidden-text detector needs glyph-level colour and size, which only C-02 can supply. Consume it through `ExtractionMetadata`/`TextBlock` as frozen in Wave 0 — if the frozen model lacks a field you need, that is a contract change request (§7.6), not a local edit.

---

### C-07 — Report writers
**Wave 1** · **Implements** `ReportWriter` ×6 · **Size** ≈ 900 LOC + 400 test

`scores.csv`, `scores.xlsx`, per-candidate ScoreCard JSON, `report.html`, `audit.jsonl`, `diagnostics/*.csv`.

**Definition of Done**
- [ ] `scores.csv` columns exactly as TRD §9.2, in that order (FR-901)
- [ ] XLSX with summary / dimensions / diagnostics sheets and conditional formatting on composite (FR-903)
- [ ] Self-contained HTML: no external assets, no network requests, opens from the filesystem (FR-904, TRD §9.3)
- [ ] HTML review queue rendered **above** the ranked list (FR-1143)
- [ ] Decision-support banner on every artefact (FR-1142)
- [ ] Selected-resume copies named `{rank:03d}_{score}_{candidate_id}_{basename}`, originals untouched (FR-905)
- [ ] `audit.jsonl` append-only, one record per candidate, complete provenance (FR-909)
- [ ] Atomic writes: temp file + rename; a failed artefact does not block the others (TRD §10.3)
- [ ] Golden-file tests on rendered output for a fixed `RunResult`

**Gotchas.** The HTML report must render correctly with `identity` fully redacted (blind mode) — write the template so a missing name degrades to the candidate id rather than an empty cell.

---

### C-08 — Resume structuring
**Wave 2** · **Implements** `Structurer` ×2 (heuristic + LLM) · **Size** ≈ 1,200 LOC + 900 test · *Second-largest; strongest model.*

**Definition of Done**
- [ ] Section segmentation over heading patterns, typography and position (FR-301)
- [ ] Experience entries with employer, title, location, dates, employment type, bullets (FR-302)
- [ ] Date parsing for all formats in FR-303, `DatePrecision` recorded, "Present"/"Current"/"Till date" → `ctx.now`
- [ ] Overlapping and concurrent roles reconciled into calendar-union coverage; **total months never double counted** (FR-304)
- [ ] LLM structurer is schema-constrained and validated; falls back to heuristic on failure with `LLM_DEGRADED` (FR-305, FR-307)
- [ ] Every LLM-derived field carries a verified evidence span or is dropped (FR-306)
- [ ] Skills harvested from all sections with section provenance and surrounding sentence (FR-308)
- [ ] Education and certifications extracted with expiry status (FR-309)
- [ ] **No field is ever inferred.** Absent → `None` (FR-310)
- [ ] `MULTI_RESUME` raised on repeated contact blocks (TRD §12)
- [ ] Golden corpus: field-level F1 ≥ 0.92 hybrid / ≥ 0.88 heuristic (TRD §13.3)
- [ ] `parse_completeness` computed and populated

**Gotchas.** The calendar-union logic is the single most-tested piece here; write it as a pure function over intervals with a Hypothesis property test (union length ≤ sum of lengths; idempotent; order-independent) before wiring it to anything.

---

### C-09 — JobSpec compiler
**Wave 2** · **Implements** `JobSpecCompiler` · **Size** ≈ 600 LOC + 500 test

**Definition of Done**
- [ ] Free-text JD → `JobSpec` with weighted criteria and knockouts (FR-401)
- [ ] Hand-authored YAML/JSON JobSpec accepted and validated, bypassing the LLM entirely (FR-402)
- [ ] Compiled JobSpec written for review; `--review-jobspec` halts the run (FR-403)
- [ ] Ambiguous requirements default to **weighted, not knockout** (FR-404)
- [ ] Importance weights 1–5 derived from requirement language, overridable (FR-405)
- [ ] Warning above 12 required skills (FR-406)
- [ ] Protected-proxy language flagged and requiring acknowledgement before becoming a knockout (FR-407)
- [ ] Compilation failure is **fatal** — this is the one stage that aborts the run, exit code 4 (TRD §2.5)
- [ ] Snapshot tests over 5 fixture JDs, asserting stable compiled output

---

### C-10 — Scoring: evidence dimensions (S1, S2, S8)
**Wave 2** · **Implements** `Dimension` ×3 · **Size** ≈ 700 LOC + 800 test

Also owns `scoring/evidence.py`, the shared match/proficiency/recency factor machinery that S1, S2 and S8 all use.

**Definition of Done**
- [ ] `f_match`, `f_prof`, `f_recency` implemented exactly per TRD §5.3.1, all factors read from `ctx.config`
- [ ] `m_i = max over evidence of f_match × f_prof × f_recency` — multiplicative, not additive
- [ ] `f_recency` clamped at `r_min` (0.50 default) and using the timeless half-life for flagged skills
- [ ] S1 `= 100 × Σ(w·m)/Σw`; S2 identical over preferred skills; **S2 returns `value=None` when the JobSpec declares no preferred skills** (weight redistribution is C-13's job)
- [ ] S8 over the three highest-weighted required skills, ties broken by canonical name for determinism
- [ ] `R-TRANS` transferable-skill adjudication used only when the deterministic cascade finds nothing, and only credited with a verified evidence span (`f_match = 0.50`)
- [ ] Every matched skill emits `Evidence`; every unmatched required skill emits a gap entry with the search terms tried (FR-907)
- [ ] The Wave-0 `xfail` table-driven tests now pass, including all boundary values
- [ ] Property tests: monotonic in evidence; bounded [0,100]; independent of skill ordering

**Gotchas.** `ctx.now` for recency — never `date.today()`. `import-linter` forbids importing `time` from `resume_ranker.scoring`; use `datetime` arithmetic on injected dates only.

---

### C-11 — Scoring: semantic relevance (S3) & embeddings
**Wave 2** · **Implements** `Dimension` ×1, `EmbeddingClient` · **Size** ≈ 700 LOC + 500 test

**Definition of Done**
- [ ] Local sentence-transformer client and optional hosted client behind one protocol; local is the default so offline mode needs no network
- [ ] Chunking: JD → requirement chunks, resume → one chunk per bullet/project/summary paragraph
- [ ] Asymmetric max-similarity: `sim(r_j) = max_k cos(r_j, e_k)`, then JD-weighted mean
- [ ] Pool calibration: p10/p90 when pool ≥ 30, fixed anchors (0.25, 0.70) below that; anchors written to `PoolStatistics` for the manifest
- [ ] `S3 = 0.6 × (100 × cal) + 0.4 × L`; in offline mode `S3 = 100 × cal` and `requires` excludes `"llm"`
- [ ] `R-SEM` called with `samples=2`; the spread is returned in `SubScore.detail["rubric_stdev"]` for C-13's confidence formula
- [ ] Embedding cache keyed by text hash; batch size configurable
- [ ] Determinism test: same pool, same order-independent result — sort chunks before batching
- [ ] Exhaustive dot product below 50k chunks; no index built (TRD §14)

**Gotchas.** S3 is the only pool-relative dimension. It must be computable in two passes — one to embed everything and gather percentiles, one to score — so expose `prepare(pool)` separately from `score()`. Wave 0 froze `ScoringContext.pool` for exactly this reason.

---

### C-12 — Scoring: profile dimensions (S4–S7, S9, S10)
**Wave 2** · **Implements** `Dimension` ×6 · **Size** ≈ 900 LOC + 900 test

**Definition of Done**
- [ ] S4: `relevance(r) = 0.35·title_sim + 0.45·skill_overlap + 0.20·domain_sim`; calendar-union before summing; the four-branch piecewise function of TRD §5.3.4 with exact boundary behaviour
- [ ] S4 over-qualification decay **disabled by default** and gated behind explicit config (TRD §11.2)
- [ ] S5: `title_sim × seniority_factor × recency_weight`, max over roles
- [ ] S6: max domain match weighted by recency, floor 0.20, returns `None` when domain weight is 0
- [ ] S7: `0.6·edu + 0.4·cert`; expired certs 0.40, in-progress 0.50; `cert = 1.0` when none named
- [ ] S7 uses **no institution ranking**; assert the ontology exposes none (TRD §5.3.7)
- [ ] S9: trajectory × stability; contract roles excluded from the tenure median
- [ ] **S9 never penalises employment gaps.** A test asserts that injecting a 12-month gap changes S9 by exactly 0.0, and this behaviour is not configurable (TRD §11.2)
- [ ] S10: deduction table from TRD §5.3.10, floor 0, never a knockout
- [ ] All Wave-0 `xfail` boundary tests pass
- [ ] Counterfactual tests: graduation-year shift, gap injection, pronoun substitution (TRD §13.4)

**Gotchas.** S4's `n < 0.5a` branch divides by `a`; guard `a == 0` (a JD with no stated minimum) by returning a neutral 70 rather than raising or dividing by zero. Wave 0's test table includes that case.

---

### C-13 — Aggregation, confidence, bands, tie-break & hard filters
**Wave 2** · **Size** ≈ 600 LOC + 700 test · *Small but the highest-consequence component.*

**Public API**
```python
def evaluate_knockouts(resume, spec, cfg) -> tuple[bool, tuple[KnockoutResult, ...]]: ...
def aggregate(sub_scores: Mapping[str, SubScore], weights: Mapping[str, float],
              findings: Sequence[IntegrityFinding], cfg) -> Aggregation: ...
def confidence(resume, sub_scores, mode) -> float: ...
def band(composite: float, cfg) -> Band: ...
def rank(cards: Sequence[ScoreCard]) -> tuple[ScoreCard, ...]: ...
```

**Definition of Done**
- [ ] Three-valued knockouts: only an explicit `FAIL` excludes; `UNVERIFIED` stays eligible with a flag (FR-602)
- [ ] Ineligible candidates are still scored and retained (FR-603)
- [ ] Knockouts refuse to reference any attribute in the fairness forbidden list — raises a config error at load (FR-605, FR-1105)
- [ ] Weight redistribution: dimensions returning `None` or weight 0 are dropped and the remainder renormalised to 100 (FR-702)
- [ ] Integrity penalties additive, **capped at 25 total**, applied after the weighted mean, always disclosed (TRD §5.4)
- [ ] Confidence per TRD §5.5; `model_agreement = 1.0` in offline mode
- [ ] Confidence < 0.60 → `LOW_CONFIDENCE` + mandatory review, **never exclusion** (FR-704)
- [ ] Tie-break chain in the exact order of TRD §5.6, terminating on `candidate_id` — never file order, never timestamp
- [ ] Property tests: renormalisation preserves the 0–100 range; ranking is a total order; ranking is stable under input permutation
- [ ] The TRD §5.8 worked example produces **87.06** exactly

**Gotchas.** Weight redistribution and penalty application must happen in that order — renormalise the weighted mean first, *then* subtract penalties, then clip. Reversing it lets a penalised candidate be rescued by redistribution.

---

### C-14 — Fairness: redaction, proxy guards, adverse impact
**Wave 2** · **Implements** `Redactor` · **Size** ≈ 700 LOC + 700 test

**Definition of Done**
- [ ] Blind mode is **on by default**; redacts every attribute in TRD §11.1 from `CanonicalResume` and from all model prompts (FR-507)
- [ ] Graduation years replaced with intervals relative to other dates so experience arithmetic still works
- [ ] Re-identification map written to a separate sidecar with restrictive permissions, never readable by the scoring path — enforced by a test asserting `ScoringContext` has no path to it
- [ ] Forbidden-knockout-attribute list loaded from config and handed to C-13
- [ ] Adverse-impact report: selection rate per group, impact ratio, Fisher exact p-value, 95 % CI, per-dimension means, leave-one-dimension-out recomputation (TRD §11.3)
- [ ] Groups under 30 flagged as statistically unreliable
- [ ] Demographics file is read **only** by the audit path and never during a scoring run — architectural test asserts no import path exists
- [ ] Counterfactual name-swap test: composite change ≤ 0.5 pts non-blind, exactly 0.0 blind (TRD §13.4)

---

### C-15 — CLI, configuration & pipeline orchestrator
**Wave 3 — the integrator's component.** · **Size** ≈ 1,000 LOC + 800 test

Written last, by the integrator, once every component is merged. It contains no business logic — only wiring, configuration resolution and process orchestration.

**Definition of Done**
- [ ] All seven commands of TRD §7.1: `run`, `parse`, `compile-jd`, `explain`, `validate-config`, `calibrate`, `audit`
- [ ] Config precedence flag > env (`RESUME_RANKER_` prefix, `__` nesting) > file > default; effective config hashed into the manifest (FR-1002)
- [ ] Schema validation with exit code 2 and a precise message (FR-1003)
- [ ] All exit codes of TRD §7.3 implemented and tested
- [ ] Never writes into the input directory (FR-1005)
- [ ] Process pool for extraction and deterministic scoring; asyncio + bounded semaphore for LLM/embedding I/O; OCR rate-limited separately (TRD §10.2)
- [ ] Streaming — the full corpus is never resident (TRD §10.2)
- [ ] Content-hash cache enables restart-from-interruption (FR-109)
- [ ] Failure tolerance → exit code 5 with results still written
- [ ] Secrets from env/secrets-file only; redacted from logs and manifest (FR-1007)
- [ ] `run_manifest.json` with full provenance (FR-908)
- [ ] End-to-end acceptance suite of §7.5 passes

---

---

### C-QA — Independent verification
**Runs across every wave** · **Agent** `qa-engineer` · **Size** ≈ 2,500 LOC of test and tooling + corpora

Full specification in **`docs/QA_PLAN.md`**. Summarised here so that the ownership map and the merge procedure are self-contained.

QA is not a phase at the end. It is a fifteenth agent running from the moment Wave 0 is tagged, doing work no component agent can do: verifying the contract freeze before fan-out, maintaining a reference implementation of the scoring model derived independently from the TRD, proving the tests actually constrain behaviour, and running the four quality gates.

**Owns** `tests/qa/**`, `docs/qa/**`, `scripts/qa/**`
**May read** everything, including `src/**` — with one exception (below)
**May never write** `src/**`, another component's tests, or any frozen file

**The three techniques that carry the weight**

- **Reference oracle** (QAP §3) — an independent second implementation of TRD §5, written from the specification text before the corresponding implementation is read, and differentially tested against the real engine over generated cases. Two independent derivations agreeing is evidence; one implementation agreeing with its own tests is not.
- **Mutation testing** (QAP §4) — break the implementation deliberately and confirm the suite notices. `scoring/**` must reach a 90 % mutation score. This is the only reliable way to distinguish a real test from one that passes for the wrong reason.
- **Traceability audit** (QAP §5) — every Must-have requirement must have a covering test that *kills a mutant*, not merely a test that carries a marker. This is what stops §8 of this document from quietly becoming a work of fiction.

**Quality gates** (QAP §10)

| Gate | When | Blocking? |
|---|---|---|
| **QG0** Contract freeze audit | After Wave 0, **before fan-out** | Yes — do not launch agents without it |
| **QG1** Component acceptance | Per branch, after `contract-guard`, before merge | Yes, on S1/S2 |
| **QG2** Integration acceptance | After each merge and after all | Yes, on S1 |
| **QG3** Release acceptance | Before the pilot run | Yes |

QG0 is the cheapest hour in the programme. A contract defect found there costs one fix; the same defect found at QG2 costs fourteen rebases.

**Definition of Done** — per gate, in QAP §11.5. In outline: a report at `docs/qa/report-<gate>.md` listing every check with pass/fail, a defect record with a minimal repro for every failure, metrics recorded and trended, and an explicit **SIGNED OFF** or **BLOCKED**. Never a hedge, and never a sign-off with an open S1.

**Gotchas.** The blind-derivation rule (QAP §3.2) is why QA must start early rather than after the components land: once QA has read an implementation, the oracle's independence for that dimension is gone and cannot be recovered. Also read QAP §11.6 — an autonomous QA agent has its own characteristic failure modes, and rubber-stamping is the most likely one. A gate report with zero findings across a fourteen-agent build is itself a finding.

---

## 5. Dependency graph and scheduling

### 5.1 Graph

```
                          ┌──────────────────────┐
                          │  W0  contract freeze │
                          └──────────┬───────────┘
                                     │  (everything below depends only on
                                     │   frozen contracts + fakes)
        ┌────────┬────────┬──────────┼──────────┬────────┬────────┐
        │        │        │          │          │        │        │
      C-01     C-02     C-03       C-04       C-05     C-06     C-07
     ingest   pdf/ocr  office    ontology     llm    integrity  report
        │        │        │          │          │        │        │
        └────┬───┴────┬───┘          ├──────┬───┴───┐    │        │
             │        │              │      │       │    │        │
             ▼        ▼              ▼      ▼       ▼    │        │
           C-08 ◄─────────────────  C-04   C-05   C-09   │        │
        structuring                   │      │            │        │
             │                        │      │            │        │
             ├────────────┬───────────┴──┬───┴────────┐   │        │
             ▼            ▼              ▼            ▼   │        │
           C-10         C-11           C-12         C-14  │        │
        S1/S2/S8    S3+embeddings    S4-S7,S9,S10  fairness│        │
             └────────────┴──────┬───────┴─────────────┴───┘        │
                                 ▼                                  │
                               C-13  aggregate/confidence/rank      │
                                 └──────────────┬───────────────────┘
                                                ▼
                                       C-15  CLI + pipeline
```

Solid arrows are **interface** dependencies, all of which are satisfied by Wave-0 fakes. They constrain *merge order*, not *start time*.

### 5.2 Waves are merge order, not start order

This is the point that makes the plan genuinely parallel rather than nominally so. Because every dependency is a frozen protocol with a working fake, **all fourteen component agents can start at the same moment.** C-10 does not wait for C-04; it codes against `FakeOntology` and its tests pass against `FakeOntology`. The first time C-10's code meets the real ontology is in `tests/integration/`, run by the integrator.

The waves therefore mean: *the order in which branches are merged, and the order in which integration tests become runnable.*

**C-QA runs alongside all of them, start to finish.** During Waves 1–2 it needs no implementation at all: it blind-derives the ten oracle modules from the TRD, assembles the adversarial, edge-case, fairness and performance corpora, writes the Hypothesis strategies, and stands up the mutation and traceability tooling. Its suites are written with `pytest.importorskip`, so they skip cleanly against modules that have not merged yet and light up progressively as components land.

### 5.3 Two ways to schedule

| | **Option A — maximum parallelism** | **Option B — staged** |
|---|---|---|
| Component agents at once | 14 | 7, then 7 |
| Wall clock | ~1 long session | ~2 sessions |
| Risk | A contract defect is discovered by 14 agents simultaneously | Wave 1 flushes out contract defects before Wave 2 starts |
| Review load | 14 branches land together | 7 + 7 |
| Recommended for | A repeat run, or a team confident in the freeze | **First execution of this plan** |

In both options `qa-engineer` runs continuously in a fifteenth worktree and is not counted above.

Option B is the default recommendation. The dominant risk in this whole approach is a defect in the frozen contracts, and QG0 followed by Wave 1 is the cheapest place to find one.

### 5.4 Critical path

`W0 → C-04 → C-08 → C-10/C-12 → C-13 → C-15`. Ontology and structuring are the long poles. If you are compressing the schedule, start C-04 and C-08 first and give them the strongest model; everything else has slack.

---

## 6. opencode orchestration

> Verified against the opencode documentation at the time of writing. Config keys and CLI flags do move — run `opencode --help` and check `https://opencode.ai/docs/agents/` before the first run, and adjust the snippets below if your version differs. Note in particular that agent markdown files have lived at both `.opencode/agent/` and `.opencode/agents/` across versions; the JSON form below is unambiguous, so prefer it.

### 6.1 Bootstrap files (written in Wave 0)

**`AGENTS.md`** — loaded automatically into every session. Keep it short; long rule files get skimmed.

```markdown
# RESUME-RANKER — rules for all agents

You are implementing ONE component of RESUME-RANKER. Read `docs/IMPLEMENTATION_PLAN.md`
§2.2 (ownership) and your own block in §4 before writing any code.

## Hard rules
1. Write ONLY inside your component's owned paths. Creating or editing a file
   outside them fails the build and the branch is rejected.
2. NEVER modify `src/resume_ranker/models/`, `protocols.py`, `errors.py`, `codes.py`,
   `pyproject.toml`, `uv.lock`, `Makefile`, or anything under `tests/fakes/`.
   These are frozen. If one is wrong, write `docs/contract-change/<ID>-NNN.md`
   describing the problem and STOP. Do not work around it by editing it.
3. Depend on protocols, never on another component's implementation. Test
   against `tests/fakes/`.
4. Do not add third-party dependencies. Everything you need is already pinned.
   If something is genuinely missing, record it in `docs/dep-requests/<ID>.md`.
5. Scoring code takes the current date from `ScoringContext.now`. Never call
   `date.today()` or import `time`.
6. Stages return `StageResult` with diagnostics on bad input. Raising is for
   programmer errors only. Never let a bad document abort a run.
7. Every positive scoring claim carries an `Evidence` span, and
   `Evidence.quote` must equal `text[span[0]:span[1]]`.

## Definition of done
`make gate` passes, plus every checkbox in your §4 block. Tests marked
`xfail(strict=True)` that cover your component must now pass — remove the
marker, do not delete or weaken the test.

## Style
Python 3.12, `from __future__ import annotations`, full type annotations,
`mypy --strict` clean. Small pure functions. Docstrings state the TRD section
each formula comes from.
```

**`opencode.json`**

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "instructions": ["AGENTS.md", "docs/IMPLEMENTATION_PLAN.md"],
  "agent": {
    "component-builder": {
      "description": "Implements one RESUME-RANKER component inside its own git worktree, against frozen contracts.",
      "mode": "primary",
      "temperature": 0.1,
      "prompt": "{file:./.opencode/prompts/component-builder.md}",
      "permission": { "edit": "allow", "bash": "allow", "webfetch": "deny" }
    },
    "contract-guard": {
      "description": "Read-only reviewer. Verifies a branch touched only its owned paths, left frozen files untouched, and satisfies its Definition of Done.",
      "mode": "subagent",
      "temperature": 0,
      "permission": { "edit": "deny", "bash": "ask", "webfetch": "deny" }
    },
    "qa-engineer": {
      "description": "Independent verification. Maintains the reference oracle and QA suites, audits test adequacy and requirement coverage, runs the quality gates, files defects. Never edits implementation code and never fixes defects.",
      "mode": "primary",
      "temperature": 0,
      "prompt": "{file:./.opencode/prompts/qa-engineer.md}",
      "permission": { "edit": "allow", "bash": "allow", "webfetch": "deny" }
    },
    "integrator": {
      "description": "Merges component branches in dependency order, wires the pipeline, and runs end-to-end acceptance.",
      "mode": "primary",
      "temperature": 0,
      "prompt": "{file:./.opencode/prompts/integrator.md}",
      "permission": { "edit": "allow", "bash": "allow" }
    }
  },
  "command": {
    "build-component": {
      "description": "Implement one RESUME-RANKER component end to end",
      "agent": "component-builder",
      "template": "Implement component $1.\n\nRead docs/IMPLEMENTATION_PLAN.md — §2.2 for your owned paths and §4 for your component block. Read src/resume_ranker/protocols.py and src/resume_ranker/models/ for the frozen contracts, and tests/fakes/ for the doubles you must test against.\n\nWork in this order:\n1. Restate your owned paths and your Definition of Done checklist. If anything is ambiguous, say so before writing code.\n2. Find every test in the repository that covers your component, including xfail-marked ones. These are your acceptance criteria — read them first.\n3. Implement. Small commits. Never touch a file outside your owned paths.\n4. Run `make gate` until green, then `make own` to confirm you stayed in your lane.\n5. Post a summary: what you implemented, which DoD boxes are ticked, which are not and why, and any contract-change requests you filed.\n\nStop and report rather than guessing if a frozen contract appears wrong."
    },
    "review-branch": {
      "description": "Contract-guard review of a component branch",
      "agent": "contract-guard",
      "subtask": true,
      "template": "Review branch feat/$1 against docs/IMPLEMENTATION_PLAN.md.\n\nCheck and report, as a pass/fail list:\n1. `git diff --name-only contracts-frozen...HEAD` — every path is owned by $1 per §2.2.\n2. No frozen file (models/, protocols.py, errors.py, codes.py, pyproject.toml, uv.lock, Makefile, tests/fakes/) was modified.\n3. Every Definition of Done checkbox in §4 for $1 is genuinely satisfied by code you can point at.\n4. No xfail-strict test covering $1 was deleted or weakened rather than made to pass.\n5. No `date.today()`, no `import time` in scoring, no network calls in tests.\n6. `make gate` passes.\n\nDo not fix anything. Report only."
    }
  }
}
```

**`.opencode/prompts/component-builder.md`** carries the standing brief in §6.3; **`.opencode/prompts/qa-engineer.md`** carries the QA brief in QAP §11.2, and the QA commands (`/qa-freeze-audit`, `/qa-accept`, `/qa-integrate`, `/qa-release`, and the rest) are defined in QAP §11.3.

> The coarse `edit: allow` permission cannot express "read `src/`, write only `tests/qa/`" for the QA agent. If your opencode version supports path-scoped edit permissions, use them; otherwise the boundary rests on `scripts/check-ownership.py` in the pre-commit hook and in CI. QAP §11.1 covers this.

### 6.2 Worktree topology

One git worktree per agent. Worktrees give each agent a real, isolated checkout that shares one object database — cheap to create, and merging is ordinary git.

```bash
#!/usr/bin/env bash
# scripts/spawn-agents.sh — create one worktree per component
set -euo pipefail
ROOT=$(git rev-parse --show-toplevel)
PARENT="$ROOT/../ats-agents"
FREEZE="contracts-frozen"

git rev-parse --verify "$FREEZE" >/dev/null || { echo "Wave 0 not tagged"; exit 1; }
mkdir -p "$PARENT"

while IFS=: read -r id slug; do
  [[ "$id" =~ ^# ]] && continue
  wt="$PARENT/$id"
  [ -d "$wt" ] && { echo "skip $id"; continue; }
  git worktree add -b "feat/$id-$slug" "$wt" "$FREEZE"
  ( cd "$wt" && uv sync --frozen )
  echo "ready: $wt  (branch feat/$id-$slug)"
done < scripts/components.txt
```

```
# scripts/components.txt
C-01:ingest
C-02:extract-pdf
C-03:extract-office
C-04:ontology
C-05:llm
C-06:integrity
C-07:report
C-08:structure
C-09:jobspec
C-10:scoring-evidence
C-11:scoring-semantic
C-12:scoring-profile
C-13:aggregate
C-14:fairness
C-QA:qa
```

`C-QA` gets a worktree like any other agent, but it is launched with `--agent qa-engineer` and it is launched **first** — its QG0 audit gates the fan-out of everything else.

Launch, one pane per agent:

```bash
# Interactive — recommended for the first run, so you can watch and intervene
tmux new-session -d -s ats
while IFS=: read -r id slug; do
  [[ "$id" =~ ^# ]] && continue
  tmux new-window -t ats -n "$id" -c "$PWD/../ats-agents/$id" \
    "opencode --agent component-builder"
done < scripts/components.txt
tmux attach -t ats
```

```bash
# Unattended — for a repeat run once the plan is proven
for id in C-01 C-02 C-03 C-04 C-05 C-06 C-07; do
  ( cd "../ats-agents/$id" \
    && opencode run --agent component-builder --auto "/build-component $id" \
       > "../logs/$id.log" 2>&1 ) &
done
wait
```

`--auto` auto-approves permissions. Only use it because each agent is confined to a worktree, `webfetch` is denied, and `make own` will catch anything that escapes its lane. Do not use it on the integrator.

### 6.3 The standing agent brief

`.opencode/prompts/component-builder.md`:

```markdown
You implement exactly one component of RESUME-RANKER, in an isolated git worktree.

Your contract with the rest of the system is entirely in
`src/resume_ranker/protocols.py` and `src/resume_ranker/models/`. Those files are frozen.
Other components are being written right now by other agents; you will never
see their code and must never depend on it. Where you need them, use the
doubles in `tests/fakes/`.

Method:
- Read your §4 block in docs/IMPLEMENTATION_PLAN.md and restate the DoD as a
  checklist before coding.
- Read the failing tests that cover your component. They are the specification;
  they were written before you started, from the TRD formulas.
- Implement in small, reviewable commits. Prefer pure functions.
- After each commit run `make gate`. Before you finish run `make own`.
- Where you implement a formula, cite the TRD section in the docstring.

Boundaries, restated because they matter more than anything else you will do:
- Never write outside your owned paths.
- Never modify a frozen file. File `docs/contract-change/<ID>-NNN.md` and stop.
- Never add a dependency.
- Never weaken or delete a test to make the suite pass.

Finish by reporting: DoD boxes ticked, boxes not ticked and why, contract-change
requests filed, and anything the integrator needs to know.
```

### 6.4 Per-component invocation

Everything a component needs is in this document, so the invocation is one line:

| Agent | Worktree | Command |
|---|---|---|
| C-01 | `../ats-agents/C-01` | `/build-component C-01` |
| C-02 | `../ats-agents/C-02` | `/build-component C-02` |
| C-03 | `../ats-agents/C-03` | `/build-component C-03` |
| C-04 | `../ats-agents/C-04` | `/build-component C-04` |
| C-05 | `../ats-agents/C-05` | `/build-component C-05` |
| C-06 | `../ats-agents/C-06` | `/build-component C-06` |
| C-07 | `../ats-agents/C-07` | `/build-component C-07` |
| C-08 | `../ats-agents/C-08` | `/build-component C-08` |
| C-09 | `../ats-agents/C-09` | `/build-component C-09` |
| C-10 | `../ats-agents/C-10` | `/build-component C-10` |
| C-11 | `../ats-agents/C-11` | `/build-component C-11` |
| C-12 | `../ats-agents/C-12` | `/build-component C-12` |
| C-13 | `../ats-agents/C-13` | `/build-component C-13` |
| C-14 | `../ats-agents/C-14` | `/build-component C-14` |
| **C-QA** | `../ats-agents/C-QA` | `/qa-freeze-audit` first, then `/qa-oracle S1`…`S10`, then `/qa-accept <ID>` per branch |

Suggested model allocation, if you are mixing models: the strongest available for **C-QA, C-02, C-08, C-10, C-12, C-13** — QA is on that list because a weak verifier is worse than none, since it produces confident sign-offs. A mid-tier model is sufficient for C-01, C-03, C-07, C-09; C-04, C-05, C-06, C-11, C-14 sit in between. Override per agent with `--model provider/model-id`.

### 6.5 Guardrails

- **Worktree isolation** — an agent cannot see or edit another's files at all.
- **`webfetch: deny`** on builders — the specification is in the repository; browsing invites invented APIs.
- **`make own`** — `scripts/check-ownership.py` diffs the branch against `contracts-frozen` and fails on any path not owned by that component. Also runs in CI on every push.
- **`import-linter`** — architectural boundaries are compile-time facts, not conventions.
- **`xfail(strict=True)`** — an agent cannot quietly skip a scoring formula; a passing test that is still marked xfail is itself a failure.
- **`contract-guard` review** — an independent read-only pass before any branch is merged.

### 6.6 When an agent gets stuck

| Symptom | Action |
|---|---|
| Filed a contract-change request | Treat as a Wave-0 defect. Batch it; see §7.6. Do not let the agent proceed on a guess. |
| Wants a dependency | Read `docs/dep-requests/<ID>.md`. If justified, the integrator adds it to `pyproject.toml` on `main` and the agent rebases. |
| Repeatedly failing `make gate` | Attach to the session, read the last failure yourself. Usually a misread contract, not a hard problem. |
| Touching files it does not own | Stop it immediately. `git checkout -- <paths>` and re-issue the brief with §2.2 quoted. Recurrence means the component is cut wrong — re-cut it. |
| Finished suspiciously fast | Run `/review-branch <ID>`. The common failure is DoD boxes silently skipped. |

---

## 7. Integration — combining the work

### 7.1 Preconditions

No branch is considered until all five hold:

1. `make gate` green on the branch.
2. `make own` green — the branch touched only its owned paths.
3. `/review-branch <ID>` returns a clean pass from `contract-guard`.
4. Every `xfail(strict=True)` test covering the component is now passing with the marker removed.
5. **`/qa-accept <ID>` returns SIGNED OFF** — QG1 passed with no open S1 or S2 (QAP §10). `contract-guard` checks that the branch is well-formed; QG1 checks that it is *correct*, and the two are not the same question.

### 7.2 Merge order and procedure

Merge order follows the dependency graph. Because owned paths are disjoint, order does not affect *whether* merges succeed — it affects how early integration tests become meaningful and how cheaply a defect is localised.

```
C-QA → C-04 → C-05 → C-01 → C-02 → C-03 → C-06 → C-07
     → C-08 → C-09 → C-11 → C-10 → C-12 → C-13 → C-14
     → then write C-15
```

**C-QA merges first**, before any component. Its suites use `pytest.importorskip`, so they skip harmlessly against modules that do not exist yet and activate automatically as each component lands — which means every subsequent merge is checked by independent tests from the moment it arrives, rather than at the end.

```bash
#!/usr/bin/env bash
# scripts/merge-components.sh
set -euo pipefail
ORDER="C-QA C-04 C-05 C-01 C-02 C-03 C-06 C-07 C-08 C-09 C-11 C-10 C-12 C-13 C-14"
git checkout main
for id in $ORDER; do
  branch=$(git branch --list "feat/$id-*" | tr -d ' *')
  echo "=== merging $branch ==="
  git merge --no-ff --no-commit "$branch" || { echo "CONFLICT in $id"; exit 1; }
  if make gate && make qa-gate; then          # qa-gate = QG2 incremental
    git commit -m "merge($id): integrate $branch"
  else
    echo "GATE FAILED after $id — aborting"; git merge --abort; exit 1
  fi
done
towncrier build --yes                       # assemble changelog.d/ → CHANGELOG.md
```

One `--no-ff` commit per component means any single component can be backed out with `git revert -m 1 <sha>` without disturbing the others.

### 7.3 Conflict policy

**A merge conflict outside integrator-owned files is a defect, not a merge problem.** It means an agent wrote outside its lane and `make own` did not catch it. The response is:

1. `git merge --abort`.
2. Identify the offending paths and which component actually owns them.
3. Revert those changes on the offending branch; if the work is needed, re-assign it to the owning component.
4. Fix `scripts/check-ownership.py` so the same escape is caught next time.

**Never hand-resolve a conflict in component code.** Hand-resolution produces a file neither agent's tests were written against, which is precisely the integration failure this whole plan exists to prevent.

The only files the integrator may resolve by hand: `pyproject.toml`, `uv.lock`, `CHANGELOG.md`, and anything else marked `[W0]`.

### 7.4 Wiring the pipeline (C-15)

Only after all fourteen merges are green. The integrator now writes the component that has been deliberately absent until this moment:

1. `config/root.py` — compose each package's config sub-model by scan; resolve flag > env > file > default; hash the effective config.
2. `pipeline.py` — instantiate real implementations, resolve extractors and dimensions through the registries, and run stages S1–S9 of TRD §2.5 with the concurrency model of TRD §10.2.
3. `cli/` — the seven commands, progress display, exit-code mapping.
4. `tests/integration/` — the first tests in the project where two real components meet. Expect to find defects here; that is what this suite is for. Every defect found is fixed **in the owning component's files**, with a test added there.

### 7.5 End-to-end acceptance

`make e2e` against a 60-resume fixture requisition. All must pass before the build is called done. These fourteen checks are the *functional* half of QG2; the rest of that gate — adversarial, fairness, accuracy, mutation and traceability — is in QAP §10 and is run by the QA agent, not the integrator.

| # | Check | Pass condition |
|---|---|---|
| E1 | Full run, offline mode | Exit 0; all artefacts present and schema-valid |
| E2 | Full run, hybrid mode with recorded LLM transport | Exit 0; no network call escapes the transport |
| E3 | **Determinism** | Two offline runs produce byte-identical `scores.csv` |
| E4 | Reproducibility, hybrid | Composite spread ≤ ±2.0 pts over five runs |
| E5 | Worked example | The TRD §5.8 candidate scores exactly **87.06** |
| E6 | Injection zero-efficacy | Adversarial fixtures alter no sub-score by more than 1 pt |
| E7 | Blind-mode counterfactual | Name swaps change no composite by any amount |
| E8 | Gap neutrality | Injecting a 12-month gap changes the composite by 0.0 |
| E9 | Degradation | LLM transport failing mid-run still exits 0 with `LLM_DEGRADED` recorded |
| E10 | Partial failure | A corrupt PDF in the batch appears in `errors.csv`, run still exits 0 |
| E11 | Exit codes | Each of TRD §7.3 reproduced by a targeted fixture |
| E12 | Adverse impact | `resume-ranker audit` produces a valid report on a synthetic cohort |
| E13 | Performance | 1,000-resume offline run ≤ 6 min, peak RSS ≤ 4 GB (TRD §10.1) |
| E14 | Warm cache | Re-run of the same batch ≤ 90 s |

### 7.6 Contract changes and rollback

**Contract change protocol.** An agent that finds a frozen contract inadequate writes `docs/contract-change/<ID>-NNN.md` — what is wrong, what it needs, what it will do meanwhile — and stops on that thread. The integrator batches requests, applies them to `main` as a single **contract amendment** commit, moves the `contracts-frozen` tag, and notifies every agent to `git rebase contracts-frozen`. Amendments are batched, never applied one at a time: each one costs fourteen rebases.

If more than three amendments are needed, stop the run. That is a signal Wave 0 was not finished, and continuing will cost more than redoing the freeze.

**Rollback.** Each component is one `--no-ff` merge commit. `git revert -m 1 <sha>` removes it cleanly. Because dimensions register by scan, reverting a scoring component removes its dimension from the registry without any other edit — the aggregation code sees a smaller dimension set and renormalises weights, which is behaviour C-13 already implements and tests.

---

## 8. Verification matrix

| Component | Unit | Property | Golden | Adversarial | Fairness | Integration | TRD requirements |
|---|:--:|:--:|:--:|:--:|:--:|:--:|---|
| C-01 Ingest | ● | ● | | ● | | ● | FR-101…110 |
| C-02 PDF/OCR | ● | ● | ● | ● | | ● | FR-201…207, 210 |
| C-03 Office/plain | ● | | ● | | | ● | FR-208…210 |
| C-04 Ontology | ● | ● | | | ● | ● | FR-501…506 |
| C-05 LLM | ● | | | ● | | ● | FR-305…307, §6 |
| C-06 Integrity | ● | | | ● | | ● | FR-1101…1104 |
| C-07 Report | ● | | ● | | ● | ● | FR-901…910 |
| C-08 Structure | ● | ● | ● | | | ● | FR-301…310 |
| C-09 JobSpec | ● | | ● | | ● | ● | FR-401…407 |
| C-10 S1/S2/S8 | ● | ● | ● | | ● | ● | FR-701, 705, §5.3.1-2, 5.3.8 |
| C-11 S3 | ● | ● | | | | ● | §5.3.3 |
| C-12 S4–S7,S9,S10 | ● | ● | ● | | ● | ● | §5.3.4-7, 5.3.9-10 |
| C-13 Aggregate | ● | ● | ● | ● | ● | ● | FR-601…605, 702…704, 801…803 |
| C-14 Fairness | ● | ● | | | ● | ● | FR-507, §11 |
| C-15 CLI/pipeline | ● | | | | | ● | FR-1001…1007, §10 |
| **C-QA** verification | ● | ● | ● | ● | ● | ● | **Audits all of the above** — QAP §5 |

The last row is the important one: C-QA does not add another column to this table, it independently checks that the rest of the table is true. A verification matrix maintained by the same agents whose work it describes is a self-report; QAP §5 cross-references every requirement against a test that provably kills a mutant, which is the difference between a matrix and a claim.

---

## Appendix A — Makefile

```make
.PHONY: gate fmt lint types imports test schema own e2e bench clean

gate: fmt lint types imports test schema

fmt:      ; uv run ruff format --check src tests
lint:     ; uv run ruff check src tests
types:    ; uv run mypy --strict src
imports:  ; uv run lint-imports
test:     ; uv run pytest -m "not slow" --cov=resume_ranker --cov-fail-under=85
schema:   ; uv run python scripts/validate_schemas.py docs/contracts src
own:      ; uv run python scripts/check-ownership.py --base contracts-frozen
e2e:      ; uv run pytest tests/e2e -m e2e -v

# QA targets — owned by C-QA, see docs/QA_PLAN.md
qa-gate:  ; uv run python scripts/qa/gate.py --gate QG2 --incremental
qa-diff:  ; uv run pytest tests/qa/test_differential_scoring.py -q
qa-mutate:; uv run python scripts/qa/mutate.py --package $(PKG)
qa-trace: ; uv run python scripts/qa/trace.py --out docs/qa/traceability.md
qa-flake: ; uv run python scripts/qa/flake-detect.py --runs 3
qa-full:  ; uv run pytest tests/qa -q
bench:    ; uv run pytest tests/benchmark --benchmark-compare-fail=mean:20%
clean:    ; rm -rf .pytest_cache .mypy_cache .coverage htmlcov
```

## Appendix B — Branch checklist

Pasted into every component's final report:

```
[ ] make gate green
[ ] make own green — only owned paths touched
[ ] /review-branch <ID> clean
[ ] /qa-accept <ID> returns SIGNED OFF (QG1, QAP §10)
[ ] All xfail-strict tests for this component passing, markers removed
[ ] Every §4 DoD checkbox ticked, or explicitly listed as not done with a reason
[ ] Docstrings cite the TRD section for every implemented formula
[ ] No date.today(); no import time in scoring; no network calls in tests
[ ] changelog.d/<ID>.feature.md written
[ ] docs/dep-requests/<ID>.md written (or explicitly empty)
[ ] No contract-change requests outstanding, or they are listed in the report
```

## Appendix C — Component brief template

For adding a component later, or re-cutting one that proved too large:

```markdown
### C-NN — <name>
**Wave** N · **Implements** <protocols> · **Size** ≈ <LOC> + <test LOC>

<Two or three sentences: what it does, and explicitly what it does NOT do.>

**Owns** <exact paths — must be disjoint from every other component>
**May read** src/resume_ranker/models/**, protocols.py, tests/fakes/**
**Public API** <signatures>
**Definition of Done** <checkboxes, each traceable to a TRD requirement>
**Gotchas** <the traps a competent implementer would otherwise fall into>
```

---

## 9. Open items

| # | Item | Owner | Needed by |
|---|---|---|---|
| B1 | Confirm the opencode version and re-verify §6.1 config keys and §6.2 CLI flags against its docs | Orchestrator | Before Wave 0 |
| B2 | Decide Option A vs Option B scheduling (§5.3) | Engineering lead | Before fan-out |
| B3 | Model allocation and budget per agent (§6.4) | Engineering lead | Before fan-out |
| B4 | Source the ESCO/O\*NET base data and confirm licensing for `data/ontology/` | Engineering | Wave 0 |
| B5 | Recorded LLM transport fixtures — record against the chosen provider once selected (TRD Q1) | Engineering | Start of Wave 2 |
| B6 | Who performs the human review of the Wave 0 contracts (§3.8) | Engineering lead | Wave 0 |
| B7 | Whether the gold corpus (TRD §13.2) is available in time for C-08's golden tests, or whether synthetic fixtures stand in initially | Talent Acquisition | Start of Wave 2 |
| B8 | Confirm whether the opencode version supports path-scoped edit permissions; if not, the QA `src/**` write ban rests entirely on the ownership check (QAP §11.1) | Orchestrator | Before Wave 0 |
| B9 | Storage and access control for Q-GOLD, which contains real personal data (QAP §6.6) | Engineering + Legal | Start of Wave 1 |
| B10 | Who reads the first QG1 report line by line to confirm the QA agent is not rubber-stamping (QAP §11.6) | Engineering lead | First branch completion |

---

*Companion to the RESUME-RANKER Technical Requirements & Design Document v1.0 and the QA Plan & QA Agent Definition v1.0. Section references prefixed **TRD** point into the requirements document, **QAP** into the QA plan; unprefixed references point into this one.*
