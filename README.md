# RESUME-RANKER

Resume screening and scoring engine that turns a job description and a set of resumes into a ranked, evidence-backed shortlist.

The full specification lives in the companion documents:

- `docs/TRD.md` — requirements, data model, formulas, scoring contracts, fairness rules
- `docs/IMPLEMENTATION_PLAN.md` — multi-agent build plan, component ownership map, merge order
- `docs/QA_PLAN.md` — independent verification gates, reference oracle, mutation testing, traceability

This README focuses on the algorithmic core and how to run the code.

---

## What the engine does

RESUME-RANKER is a deterministic, explainable, locally-run pipeline. It does not call LLM endpoints and loads its embedding model from the local Hugging Face cache:

1. **Ingest** resumes and one job description per run.
2. **Extract** text from PDF, Word, RTF and plain-text files, preserving reading order and page locations.
3. **Structure** the resume into a `CanonicalResume` (identity, experience, education, skills, certifications).
4. **Compile** the job description into a `JobSpec` (required/preferred skills, experience targets, knockouts, education, domain).
5. **Normalise** skills and titles through an ontology (ESCO + O*NET + curated aliases) and title taxonomy.
6. **Score** every candidate on ten evidence-backed dimensions.
7. **Aggregate** into a composite score, band, rank, and confidence.
8. **Report** via recruiter-facing explanations, CSV/Excel exports, and audit manifests.

The system is designed to **never raise on bad data**. Every stage returns a `StageResult` with a value and a list of diagnostics; only programmer errors raise.

---

## Recent improvements

- **Prose JD skill parsing** — the JobSpec compiler extracts required and preferred skills from free-text sections such as *Minimum Qualifications* and *Preferred Qualifications*, including parenthetical acronym lists and separators like `like` / `such as`.
- **Robust skill-list extraction** — the resume structurer parses comma, semicolon, bullet, ampersand, and slash-delimited skill lines and ignores heading-style two-item lines (e.g., `SCOPE & AUTHORITY`).
- **Keyword and semantic skill fallback** — when the ontology does not contain an exact match, the scorer falls back to keyword matching on extracted skills and, when embeddings are available, embedding-based semantic similarity.
- **Context-aware integrity detection** — the keyword-stuffing detector excludes the dedicated skills section and uses a higher threshold, reducing false positives on dense but legitimate skills lists.
- **Full-text skill scanner** — the resume structurer also scans the entire extracted text for known skill phrases and acronyms (e.g., `BGP`, `OSPF`, `WireGuard`, `containerization`) that may only appear in experience bullets, not in a dedicated skills list.
- **Keyword overlap threshold fix** — multi-token skill targets such as `ai/ml` now require full token overlap, eliminating false matches against unrelated phrases like `AI governance`.
- **Minimum-qualification gate** — scorecard explanations now report `Required skills: X/Y` and `Preferred: X/Y` counts so recruiters can see a quick pass/fail summary.
- **Pinned embedding model identifier** — the run manifest records the exact Hugging Face snapshot hash of the local embedding model (e.g., `Qwen/Qwen3-Embedding-8B@<snapshot_hash>`), making S3 reproducibility auditable.
- **S3 restored to TRD max-cosine similarity** — S3 now uses `sim(r_j) = max_k cos(r_j, e_k)` per TRD §5.3.3 instead of classifier probabilities, which had compressed raw scores below the calibration floor and zeroed the dimension for every candidate.
- **JD prose noise filtering** — the JobSpec compiler now rejects responsibility-like fragments ("shipping products", "external vendors understand") and sentence fragments that merely mention "certification", so only genuine skills and certifications enter the spec.

---

## Algorithmic core

### Scoring dimensions (S1–S10)

Each dimension returns a `SubScore` in `[0, 100]` together with `Evidence` spans that quote the source text. The evidence span must equal `text[span[0]:span[1]]`.

All weights, half-lives, thresholds and match factors are read from configuration; nothing is hard-coded.

#### S1 — Required skills coverage (default weight 30)

S1 is the weighted mean of the best evidence found for each required skill. For each required skill `i` with weight `w_i`:

```
m_i = max over evidence e of f_match(e) × f_prof(e) × f_recency(e)
S1 = 100 × Σ(w_i × m_i) / Σ(w_i)
```

**`f_match`** — how the skill was identified:

| Route | Value |
|---|---|
| Exact / ontology-canonical | 1.00 |
| Curated alias | 1.00 |
| Ontology child of required skill | 0.90 |
| Ontology parent of required skill | 0.70 |
| Fuzzy match ratio ≥ 92 | 0.85 |
| Embedding cosine ≥ 0.82 | 0.60 + 0.75 × (cos − 0.82), capped at 0.85 |
| No evidence | 0.00 |

**`f_prof`** — strength of evidence:

| Evidence strength | Value |
|---|---|
| Applied in a role/project ≥ 12 months | 1.00 |
| Applied in a role/project < 12 months | 0.85 |
| Listed in skills section and corroborated in narrative | 0.80 |
| Listed in skills section only | 0.55 |
| Single incidental mention | 0.40 |

**`f_recency`** — exponential decay with floor:

```
f_recency = clamp( exp( -ln(2) × dt / H ), r_min, 1.0 )

dt = years since last evidenced use
H = half-life (default 4.0 y; 12.0 y for skills marked timeless)
r_min = 0.50
```

The three factors multiply, so a skill that is merely listed and long unused cannot score highly on a single strong signal.

#### S2 — Preferred skills coverage (default weight 8)

Same formula as S1 over preferred skills. If the JobSpec declares no preferred skills, S2 is excluded and its weight is redistributed proportionally across the remaining active dimensions.

#### S3 — Semantic relevance (default weight 18)

S3 asks whether the candidate’s actual work resembles the job description, independent of named-skill overlap. It is the dimension that rescues strong candidates whose vocabulary differs from the JD.

```
R = requirement chunks from JD, each with JD weight v_j
E = evidence chunks from resume bullets, projects, summary

sim(r_j) = max over e_k of cos( emb(r_j), emb(e_k) )
raw = Σ_j ( v_j × sim(r_j) ) / Σ_j v_j

if pool size >= 30:
    cal = clip( (raw - p10) / max(p90 - p10, 0.05), 0, 1 )
else:
    cal = clip( (raw - 0.25) / 0.45, 0, 1 )

S3 = 100 × cal
```

Because S3 is calibrated against the pool, two runs over different pools are not directly comparable. The run manifest records the anchors so audits can detect this.

#### S4 — Relevant experience depth (default weight 15)

What is scored is **relevant** years, not raw tenure. For each role `r`:

```
relevance(r) = clip( 0.35 × title_sim(r) + 0.45 × skill_overlap(r) + 0.20 × domain_sim(r), 0, 1 )

n = Σ covered spans ( years × relevance )

a = min_years, b = target_years (default a + 3)

n < 0.5a            S4 = 40 × ( n / (0.5a) )
0.5a <= n < a       S4 = 40 + 30 × ( n - 0.5a ) / (0.5a)
a <= n <= b         S4 = 70 + 30 × ( n - a ) / ( b - a )
n > b               S4 = 100 - min( overqual_cap, k × (n - b) )
```

Overlapping and concurrent roles are merged into a calendar-union timeline first; the maximum relevance applies for overlapped spans. Internships count at half duration unless configured otherwise. The overqualification penalty is disabled by default because it is a common proxy for age.

#### S5 — Role and title alignment (default weight 8)

```
S5 = 100 × max over roles r of ( title_sim(r) × seniority_factor(r) × rw(r) )

rw(r) = f_recency(role end date, half-life 6.0 y, floor 0.55)
```

| Title similarity | Value |
|---|---|
| Exact canonical title | 1.00 |
| Same family, different specialisation | 0.80 |
| Adjacent family | 0.55 |
| Unrelated family | 0.15 |

| Seniority vs target | Factor |
|---|---|
| At target level or one below | 1.00 |
| One above | 0.95 |
| Two or more above | 0.85 |
| Two below | 0.70 |
| Three or more below | 0.45 |

#### S6 — Domain and industry match (default weight 5)

```
S6 = 100 × max over roles of domain_match, weighted by role recency
```

| Match | Value |
|---|---|
| Exact sector (NAICS 3-digit) | 1.00 |
| Adjacent sector | 0.60 |
| No match | 0.20 (floor) |

If the JobSpec does not require domain matching, S6 is excluded and its weight is redistributed.

#### S7 — Education and certifications (default weight 7)

```
edu = 1.00 if level >= required AND field in accepted list
edu = 0.80 if level >= required AND adjacent field
edu = 0.70 if one level below AND equivalent_experience_allowed AND relevant_years >= min_years + 2
edu = clip( level_ordinal / required_ordinal, 0.20, 1 ) otherwise

cert = Σ( matched cert weights ) / Σ( required + preferred cert weights )
       expired certification = 0.40
       in-progress / candidate status = 0.50
       no certifications named = 1.0 (neutral)

S7 = 100 × clip( 0.6 × edu + 0.4 × cert, 0, 1 )
```

Institution prestige is deliberately not a factor.

#### S8 — Skill recency (default weight 5)

```
T = the three required skills with the highest JobSpec weight
    (ties broken by canonical name, for determinism)
S8 = 100 × mean over t in T of f_recency( last evidenced use of t )
```

A required skill with no evidence contributes 0 to the mean; it is already penalised in S1. Currency in the top requirements is a distinct signal from breadth of coverage.

#### S9 — Career trajectory and stability (default weight 2)

```
trajectory = 1.00 if seniority increased over the last 6 years
           = 0.70 if lateral movement
           = 0.40 if seniority decreased
           = 0.70 if insufficient history (< 2 roles)

stability = 1.00 if median tenure >= 24 months
        = 0.75 if 12 to 24 months
        = 0.45 if < 12 months
        (contract/freelance roles excluded from the median)

S9 = 100 × ( 0.5 × trajectory + 0.5 × stability )
```

Employment gaps are detected and reported as context but **never penalised**. Career breaks correlate with caregiving, illness and immigration status; penalising them is both a fairness risk and a poor predictor.

#### S10 — Resume parseability (default weight 2)

S10 measures the document, not the candidate. Start at 100 and deduct:

| Problem | Deduction |
|---|---|
| No machine-readable text layer (OCR was required) | −40 |
| Multi-column layout requiring reconstruction | −15 |
| Each critical section missing (experience/skills/education), max −30 | −15 |
| Dates unparseable in > 25% of roles | −15 |
| Contact block not detected (ignored in blind mode) | −10 |

Floor at 0. A low S10 is a data-quality flag, never a knockout.

---

## Composite aggregation

```
active = dimensions with weight > 0 that produced a value
base = Σ_k ( w_k × S_k ) / Σ_k w_k

integrity_penalty = additive, capped at 25
  HIDDEN_TEXT      25
  INJECTION_ATTEMPT 25
  KEYWORD_STUFFING 10

composite = clip( base - integrity_penalty, 0, 100 )
```

If a dimension is disabled or unavailable, its weight is redistributed proportionally among the remaining active dimensions so that composites stay comparable within a run.

### Bands

| Range | Band |
|---|---|
| ≥ 85 | strong |
| 70 – 84.99 | good |
| 55 – 69.99 | borderline |
| 40 – 54.99 | weak |
| < 40 | not_a_match |

### Confidence

Confidence is reported separately and never folded into the score:

```
C = 0.30 × parse_completeness
  + 0.25 × extraction_quality
  + 0.25 × evidence_density
  + 0.20 × model_agreement
```

- `parse_completeness` = populated required `CanonicalResume` fields / total required
- `extraction_quality` = 1.0 for native text layer; 1 − OCR error rate otherwise
- `evidence_density` = distinct cited evidence spans / JD criteria, clipped to [0, 1]
- `model_agreement` = `clip( 1 - stdev(S3 rubric samples) / 25, 0, 1 )`; 1.0 in deterministic mode

`C < 0.60` sets `LOW_CONFENCE` and routes the candidate to mandatory human review, but the candidate is never auto-excluded.

### Tie-breaking and stable ordering

Ranking is deterministic. The tie-break chain is applied in order:

1. Higher composite score
2. Higher S1 (required skills coverage)
3. Higher S4 (relevant experience depth)
4. Higher confidence
5. Lexicographic `candidate_id`

---

## Fairness and integrity guardrails

- **Blind mode** redacts name, email, phone, age proxies, gender and ethnicity signals from all text sent to scoring.
- **Protected-attribute knockouts** are rejected; no knockout rule may reference protected or proxy-protected attributes.
- **Integrity detectors** report `HIDDEN_TEXT`, `INJECTION_ATTEMPT` and `KEYWORD_STUFFING` with evidence spans; they add penalties but do not exclude.
- **Adverse-impact checks** run before deployment and after weight calibration; a weight set that improves ranking while worsening group selection-rate ratios is rejected.
- **Employment gaps** and **over-qualification penalties** are not scored; the former is reported, the latter is disabled by default.

---

## Local-first operation

This branch runs **without LLM calls**. All scoring is deterministic: rule-based parsing, ontology matching, embedding cosine similarity, and arithmetic. The embedding model is loaded from the local Hugging Face cache (`local_files_only=True`), so the first run after the model is cached needs no network access.

| Stage | Mechanism | Determinism controls |
|---|---|---|
| Resume structuring | Heuristic section segmentation and entity extraction | Rule-based, reproducible over the same text |
| Job description compilation | Heuristic skill/weight extraction from prose | Rule-based, no external model |
| S3 semantic relevance | Local sentence-transformer embeddings + pool calibration | Anchored percentiles or fixed anchors recorded in the manifest |
| Transferable skills | Not awarded; unmatched required skills are reported as gaps | — |
| Explanations | Templated scorecard summary | Rule-based, cannot alter any score |

The `LLMClient` adapter, prompts, and cache remain in `src/resume_ranker/llm/` for future hybrid-mode work, but the pipeline never instantiates them.

---

## Project layout

```
.
├── AGENTS.md                         # Agent rules for opencode
├── Makefile                          # make gate, make own
├── README.md                         # This file
├── opencode.json                     # Subagent definitions
├── pyproject.toml                    # uv project, dependencies, tool config
├── uv.lock                           # Pinned dependency tree
├── .importlinter                     # Layered architecture contracts
├── scripts/                          # Wave 0 tooling + per-component spawn/merge
│   ├── check-ownership.py
│   ├── spawn-agents.sh
│   ├── merge-components.sh
│   ├── validate_schemas.py
│   └── generate_fixtures.py
├── docs/
│   ├── IMPLEMENTATION_PLAN.md        # Ownership map and build plan
│   ├── QA_PLAN.md                    # Independent verification plan
│   ├── TRD.md                        # Full technical requirements and design
│   └── contracts/                    # Generated JSON schemas
├── src/resume_ranker/
│   ├── models/                       # Frozen Pydantic v2 domain models
│   ├── protocols.py                  # Protocols every component implements
│   ├── errors.py, codes.py           # Reason codes and exceptions
│   ├── cache.py, telemetry.py        # Shared infrastructure
│   ├── extract/                      # Text extraction (PDF, OCR, Office, plain)
│   ├── structure/                    # Resume structuring
│   ├── jobspec/                      # JobSpec compilation
│   ├── ontology/                     # ESCO + O*NET ontology + title taxonomy
│   ├── llm/                          # LLM adapter, prompts, budget, cache (currently unused)
│   ├── embeddings/                   # Embedding client
│   ├── integrity/                    # Injection, stuffing, hidden-text detectors
│   ├── scoring/                      # Dimensions, aggregation, confidence, bands
│   ├── fairness/                     # Impact, proxies, redaction
│   ├── report/                       # CSV, HTML, XLSX, audit writers
│   └── cli/                          # Command-line interface
└── tests/
    ├── fakes/                        # Protocol doubles for unit tests
    ├── corpus/                       # 40 synthetic resumes, 5 JDs, 12 adversarial docs
    ├── unit/                         # Component tests (one directory per component)
    ├── qa/                           # Independent QA verification (C-QA)
    └── test_*.py                     # Cross-cutting import / protocol tests
```

---

## Development quick start

### Prerequisites

- Python 3.12
- [uv](https://docs.astral.sh/uv/)

### Install and verify

```bash
uv sync --frozen
make gate
```

`make gate` runs: `fmt`, `lint`, `types`, `imports`, `test`, `schema`.

### Run tests

```bash
uv run pytest -m "not slow"
```

### Generate schemas

```bash
uv run python scripts/validate_schemas.py docs/contracts src
```

### Run the pipeline

```bash
# Score a directory of resumes against a job description (offline / deterministic mode)
uv run resume-ranker run --resumes path/to/resumes/ --jd path/to/jd.txt --out run-2026-08-30 --force
```

The pipeline runs in **offline mode** by default. All scoring is deterministic; no LLM calls are made.

Key flags:

- `--resumes` — directory containing candidate resumes (PDF, Word, RTF, plain text, HTML)
- `--jd` — path to a free-text job description or a pre-compiled `JobSpec` YAML file
- `--out` — output directory (default: `resume-ranker-out`)
- `--mode offline` — deterministic mode with local embeddings only (default)
- `--blind` / `--no-blind` — redact identity attributes before scoring (default: blind)
- `--force` — overwrite an existing output directory
- `--review-jobspec` — halt after compiling the JD so you can review the generated `JobSpec`
- `--dry-run` — ingest and compile only; do not score

### Parse resumes without scoring

```bash
uv run resume-ranker parse --resumes path/to/resumes/ --out parsed-resumes
```

This writes a `c_<id>.resume.json` per candidate with the structured `CanonicalResume`.

### Compile a job description for review

```bash
uv run resume-ranker compile-jd --jd path/to/jd.txt --out jobspec.yaml
```

### Calibrate scoring weights against a labelled set

The `calibrate` command runs the weight-tuning procedure described in TRD §5.7.
It expects a directory of resumes that have been labelled with target scores
(e.g., recruiter ratings) and writes a YAML file with tuned weights.

```bash
uv run resume-ranker calibrate --resumes path/to/labelled-resumes/ --out calibration.yaml
```

In the current isolated component build, `calibrate` returns a report indicating
that the real tuning is implemented by the scoring components; the CLI command
wires the procedure and persists the result.

### Audit a completed run

The `audit` command validates a completed run, reports band and selection counts,
and, when a demographics file is supplied, computes an adverse-impact report per
TRD §11.3.

```bash
# Basic audit (no demographics)
uv run resume-ranker audit --out run-2026-08-30

# Audit with adverse-impact analysis
uv run resume-ranker audit --out run-2026-08-30 --demographics path/to/demographics.csv
```

The demographics CSV must contain two columns: `candidate_id` and `group`.

See `docs/TRD.md` §9 and `uv run resume-ranker --help` for the full command surface.

---

## Multi-agent build workflow

This repository is built by parallel component agents after the Wave 0 contract freeze. The freeze is tagged `contracts-frozen`. Component agents work in branches `feat/C-xx-*` and are merged in the order specified in `scripts/merge-components.sh`.

Key rules:

- Frozen files (`src/resume_ranker/models/`, `protocols.py`, `errors.py`, `codes.py`, `pyproject.toml`, `uv.lock`, `Makefile`, `.importlinter`, `tests/fakes/`) are never edited by component agents.
- Every component tests against the fakes in `tests/fakes/`, never against another component’s implementation.
- The QA agent (C-QA) independently verifies every component against the TRD and never edits implementation code.
- `make own` enforces path ownership before merge.

See `docs/IMPLEMENTATION_PLAN.md` §2 and §4 for the ownership map and the merge procedure.

---

## Data sources and licensing

The skill ontology combines **ESCO** and **O*NET** base taxonomies with a curated alias layer. The ontology is stored as versioned data files in `data/ontology/2026.07/` and its version identifier is recorded in every run manifest. License notices are kept in `data/ontology/2026.07/LICENSE.*`.

---

## License

This project is licensed under the **GNU Lesser General Public License v3.0 (LGPL-3.0-or-later)**.
See the [`LICENSE`](LICENSE) file for the full text.
