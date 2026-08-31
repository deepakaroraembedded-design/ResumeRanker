# RESUME-RANKER C-QA status snapshot

**Date:** 2026-08-29  
**Branch:** `main`  
**Local commit:** `3c97aec` (not yet pushed to origin)  
**Component owner:** C-QA (independent verification)

This file is a save-point. It records the exact state of the codebase and the
remaining work so the next session can resume without re-discovering any of it.

---

## 1. What was completed in this session

- Fixed `scripts/qa/trace.py` so it parses the TRD requirement tables, extracts
the MoSCoW priority from the last token, ignores non-row headers, and
deduplicates covering test paths.
- Added `@pytest.mark.covers(...)` markers to C-QA tests, giving traceability for
`FR-701`–`FR-707` and `FR-801`–`FR-803`.
- Took temporary C-13 ownership to implement `FR-802` (selection stage) in
`src/resume_ranker/scoring/selection.py` because the `feat/C-13-aggregate` branch
was dormant and even with `main`.
- Added `test_selection_*` tests in `tests/qa/test_differential_scoring.py`.
- Regenerated `docs/qa/traceability.md`, `docs/qa/report-QG2.md`, and
`docs/qa/mutants-QG2.md`.
- Verified `make gate` and `make qa-gate` pass.
- Corrected `docs/qa/metrics.csv` QG2 row: global Must-have coverage is **13.2%**
(10/76), not the stale 86.6%.
- Assessed every other component for QG3 readiness (see matrix below).

---

## 2. Gate status

| Gate | Command | Result |
|---|---|---|
| `make gate` | lint + type-check + import-linter + pytest + schema validation | **PASS** |
| `make own` | `scripts/check-ownership.py --base main` | **PASS** |
| `make e2e` | `pytest tests/e2e -m e2e` | **9/9 PASS** |
| `make qa-gate` | C-QA scoring gate | **PASS** |

QG2 for `resume_ranker/scoring` is **signed off**.

- Mutation score: **90.8%** (1645 killed, 162 survived, 4 no_tests, 1811 total)
- Scoring/rank Must-haves: **10/10 covered** (`FR-701`–`FR-707`, `FR-801`–`FR-803`)
- Global Must-haves: **10/76 covered (13.2%)**

Overall pytest coverage from `make gate`:

- Line coverage: **88.78%** (passes 85% threshold)
- Total statements: 6174, missing: 523
- Branches: 1936, missing branches: 387

---

## 3. Push blocker

The local commit `3c97aec` has **not** been pushed.

- Remote: `git@github.com:deepakaroraembedded-design/ResumeRanker.git`
- `~/.ssh/id_ed25519` (comment `github-deploy`) authenticates to GitHub but is not
  granted write access to this repository.
- `~/.ssh/id_publicgithub` (comment `deepakarora.embedded@gmail.com`) is
  passphrase-protected and non-interactive unlock attempts (`ssh-agent`,
  `SSH_ASKPASS`) timed out.
- The remote URL was reverted to `git@github.com:deepakaroraembedded-design/ResumeRanker.git`.

To push, provide the correct SSH key or a GitHub token with write access to the
repository.

---

## 4. Per-component readiness matrix

All component branches are **0 commits ahead of `main`** and fully merged.

| Component | Unit tests | Line coverage | Branch coverage | Traceability markers | Mutation gate | Notes |
|---|---:|---:|---:|---|---|---|
| C-01 ingest | yes | 87.8% | 80.6% | **none** | none | FR-100 uncovered |
| C-02 PDF/OCR | yes | 89.7% | 68.9% | **none** | none | FR-200 uncovered |
| C-03 office/plain | yes | 87.3% | 57.9% | **none** | none | FR-200 uncovered |
| C-04 ontology | yes | 90.9% | 80.9% | **none** | none | FR-500 uncovered |
| C-05 LLM | yes | 85.7% | 67.1% | **none** | none | cross-cutting LLM calls |
| C-06 integrity | yes | 96.0% | 86.8% | **none** | none | FR-1100 uncovered |
| C-07 report | yes | 96.0% | 85.7% | **none** | none | FR-900 uncovered |
| C-08 structure | yes | 92.7% | 79.2% | **none** | none | FR-300 uncovered |
| C-09 jobspec | yes | 84.5% | 69.5% | **none** | none | FR-400 uncovered; line coverage below 85% |
| C-10 evidence dims | yes | 98.2% | 96.9% | **none** | none | covered indirectly by FR-701–FR-707 |
| C-11 semantic/embeddings | yes | 95.9% | 87.1% | **none** | none | covered indirectly by FR-701–FR-707 |
| C-12 profile dims | yes | 93.3% | 91.7% | **none** | none | covered indirectly by FR-701–FR-707 |
| C-13 aggregation | yes | 99.4% | 93.5% | **FR-701–FR-803** | QG2 signed off | **scoring/rank complete** |
| C-14 fairness | yes | 94.2% | 86.5% | **none** | none | cross-cutting fairness/redaction |
| C-15 CLI/pipeline | yes | 81.4% | 75.8% | **none** | none | FR-1000 uncovered; line coverage below 85% |
| W0 / shared | yes | 96.5% | 60.0% | N/A | N/A | protocols, models, errors, codes, cache, telemetry, registries |

The only component with both traceability markers and a mutation gate is **C-13
aggregation / scoring**.

---

## 5. Uncovered Must-have requirements

Traceability report: `docs/qa/traceability.md`.

| Functional area | Requirement IDs | Uncovered Must-haves |
|---|---|---:|
| Ingestion (FR-100) | `FR-101`–`FR-108` | 8 |
| Text extraction (FR-200) | `FR-201`–`FR-203`, `FR-205`–`FR-208`, `FR-210` | 8 |
| Resume structuring (FR-300) | `FR-301`–`FR-308`, `FR-310` | 10 |
| JobSpec compilation (FR-400) | `FR-401`, `FR-402`, `FR-404`, `FR-405`, `FR-407` | 5 |
| Ontology & normalisation (FR-500) | `FR-501`–`FR-504`, `FR-506`, `FR-507` | 6 |
| Hard filters / knockouts (FR-600) | `FR-601`–`FR-603`, `FR-605` | 4 |
| Output & explainability (FR-900) | `FR-901`–`FR-909`, `FR-910` | 10 |
| CLI & configuration (FR-1000) | `FR-1001`–`FR-1003`, `FR-1005`, `FR-1007` | 5 |
| Integrity & oversight (FR-1100) | `FR-1101`–`FR-1107`, `FR-1141`–`FR-1143` | 10 |
| **Total** | | **66** |

Covered Must-haves: **10** (`FR-701`–`FR-707`, `FR-801`–`FR-803`).

---

## 6. Open defects

`docs/qa/defects/QA-0001.md` and `docs/qa/defects/QA-0002.md` are still recorded
as **open** from QG0. Both are routed to **W0** (foundation). On the current
`main` they no longer fail `make gate` or `make own`, so they should be formally
closed or re-triaged.

| ID | Severity | Component | Status | Summary |
|---|---|---|---|---|
| QA-0001 | S2 | W0 | open | `tests/test_fakes_satisfy_protocols.py` import order ruff violation |
| QA-0002 | S2 | W0 | open | `scripts/check-ownership.py` parses `feat/C-NN-foo` branches as component `C` |

---

## 7. Files that matter right now

- `docs/qa/traceability.md` — generated coverage matrix
- `docs/qa/metrics.csv` — trend file, QG2 row corrected
- `docs/qa/report-QG2.md` — signed-off C-13 scoring report
- `docs/qa/mutants-QG2.md` — mutation triage for scoring
- `docs/qa/defects/QA-0001.md`, `QA-0002.md` — open W0 defects
- `src/resume_ranker/scoring/selection.py` — new `FR-802` implementation
- `tests/qa/test_differential_scoring.py` — selection tests + scoring markers
- `scripts/qa/trace.py` — traceability parser
- `scripts/qa/gate.py` — gate runner

---

## 8. Next steps (pick at resume)

1. **Push the local commit** once the correct SSH key or GitHub token is
   available.
2. **Close or re-triage** `QA-0001` and `QA-0002`.
3. **Ask every component owner** to add `@pytest.mark.covers(...)` markers to
   their own tests and run their component-level mutation gate.
4. **Take temporary ownership** of specific components to add markers and
   mutation coverage, if the owners are unavailable.
5. **Re-run QG3** once all Must-haves are traceable and mutation gates exist for
   every component.
