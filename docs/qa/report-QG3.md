# QA gate report — QG3
## make gate: PASS
Command: make gate

```
uv run --group dev ruff format --check src tests
273 files already formatted
uv run --group dev ruff check src tests
All checks passed!
uv run --group dev mypy --strict src
Success: no issues found in 109 source files
uv run --group dev lint-imports

╔══╗─────────▶╔╗ ╔╗      ╔╗◀───┐
╚╣╠╝◀─────┐  ╔╝╚╗║║────▶╔╝╚╗   │
 ║║   ╔══╦══╦╩╗╔╝║║  ╔╦═╩╗╔╝╔═╦══╗
 ║║╔══╣╔╗║╔╗║╔╣║ ║║ ╔╬╣╔╗║║ ║│║╔═╝
╔╣╠╣║║║╚╝║╚╝║║║╚╗║╚═╝║║║║║╚╗║═╣║
╚══╩╩╩╣╔═╩══╩╝╚═╝╚═══╩╩╝╚╩═╩╩═╩╝
  └──▶║║                    ▲ 
      ╚╝────────────────────┘


---------
Contracts
---------

Analyzed 157 files, 702 dependencies.
-------------------------------------

Layered architecture KEPT
Scoring dimensions never import one another KEPT
Scoring must take time from ScoringContext KEPT
Domain models do not import implementation layers KEPT

Contracts: 4 kept, 0 broken.
uv run --group dev pytest -m "not slow" --cov=resume_ranker --cov-fail-under=85
........................................................................ [  9%]
........................................................................ [ 19%]
........................................................................ [ 29%]
........................................................................ [ 39%]
........................................................................ [ 48%]
........................................................................ [ 58%]
........................................................................ [ 68%]
........................................................................ [ 78%]
........................................................................ [ 87%]
........................................................................ [ 97%]
.................                                                        [100%]
================================ tests coverage ================================
_______________ coverage: platform linux, python 3.12.14-final-0 _______________

Name                                                     Stmts   Miss Branch BrPart  Cover
------------------------------------------------------------------------------------------
src/resume_ranker/__init__.py                                     2      0      0      0   100%
src/resume_ranker/cache.py                                       27     15      2      0    41%
src/resume_ranker/cli/__init__.py                                 3      0      0      0   100%
src/resume_ranker/cli/main.py                                   203     29     60      8    86%
src/resume_ranker/codes.py                                       26      2      0      0    92%
src/resume_ranker/config/__init__.py                              3      0      0      0   100%
src/resume_ranker/config/root.py                                104     13     40      5    88%
src/resume_ranker/embeddings/__init__.py                          3      0      0      0   100%
src/resume_ranker/embeddings/client.py                           59      2     20      3    94%
src/resume_ranker/errors.py                                       4      0      0      0   100%
src/resume_ranker/extract/__init__.py                             3      0      0      0   100%
src/resume_ranker/extract/ocr/__init__.py                         3      0      0      0   100%
src/resume_ranker/extract/ocr/extractor.py                       48     14      6      1    65%
src/resume_ranker/extract/office/__init__.py                      3      0      0      0   100%
src/resume_ranker/extract/office/extractor.py                   111     14     32      9    80%
src/resume_ranker/extract/pdf/__init__.py                         4      0      0      0   100%
src/resume_ranker/extract/pdf/_config.py                         35     11     10      2    58%
src/resume_ranker/extract/pdf/_extract.py                        90      3     32      6    93%
src/resume_ranker/extract/pdf/_normalize.py                      19      1      2      1    90%
src/resume_ranker/extract/pdf/_render.py                         23      2      8      2    87%
src/resume_ranker/extract/pdf/_tables.py                         51      4     18      4    88%
src/resume_ranker/extract/pdf/_tokens.py                        182     14     62     13    87%
src/resume_ranker/extract/pdf/extractor.py                       50      3     10      3    90%
src/resume_ranker/extract/plain/__init__.py                       3      0      0      0   100%
src/resume_ranker/extract/plain/_html.py                         66     18     34      7    65%
src/resume_ranker/extract/plain/_langdetect.py                   20      0      8      0   100%
src/resume_ranker/extract/plain/_normalise.py                     8      0      0      0   100%
src/resume_ranker/extract/plain/extractor.py                     57      2      2      0    97%
src/resume_ranker/extract/registry.py                            20      1      6      1    92%
src/resume_ranker/fairness/__init__.py                            5      0      0      0   100%
src/resume_ranker/fairness/impact.py                            155      9     56      7    92%
src/resume_ranker/fairness/proxies.py                            13      0      4      0   100%
src/resume_ranker/fairness/redaction.py                         135      7     66      7    93%
src/resume_ranker/ingest/__init__.py                              3      0      0      0   100%
src/resume_ranker/ingest/manifest.py                            293     36    124     22    86%
src/resume_ranker/integrity/__init__.py                           5      0      0      0   100%
src/resume_ranker/integrity/_bbox.py                              9      1      2      1    82%
src/resume_ranker/integrity/_colour.py                            4      0      0      0   100%
src/resume_ranker/integrity/_offset.py                           17      0      4      0   100%
src/resume_ranker/integrity/_tokens.py                            4      0      0      0   100%
src/resume_ranker/integrity/hidden_text.py                       47      1     18      1    97%
src/resume_ranker/integrity/injection.py                         20      0      4      0   100%
src/resume_ranker/integrity/stuffing.py                          71      5     40      7    89%
src/resume_ranker/jobspec/__init__.py                             4      0      0      0   100%
src/resume_ranker/jobspec/codes.py                                7      0      0      0   100%
src/resume_ranker/jobspec/compile.py                            252     14    110     14    91%
src/resume_ranker/jobspec/review.py                              25      0      4      0   100%
src/resume_ranker/jobspec/schema.py                              16      7      4      0    45%
src/resume_ranker/llm/__init__.py                                 7      0      0      0   100%
src/resume_ranker/llm/adapter.py                                272     51    106     16    76%
src/resume_ranker/llm/budget.py                                  35      3     14      1    92%
src/resume_ranker/llm/cache.py                                   52      0      0      0   100%
src/resume_ranker/llm/prompts.py                                 68      8     30      5    83%
src/resume_ranker/llm/security.py                                25      0      8      0   100%
src/resume_ranker/llm/transport.py                               52     11      6      2    74%
src/resume_ranker/models/__init__.py                             12      0      0      0   100%
src/resume_ranker/models/common.py                               24      0      0      0   100%
src/resume_ranker/models/config.py                              106      0      0      0   100%
src/resume_ranker/models/embeddings.py                            3      0      0      0   100%
src/resume_ranker/models/jobspec.py                              48      0      0      0   100%
src/resume_ranker/models/llm.py                                   7      0      0      0   100%
src/resume_ranker/models/ontology.py                             22      0      0      0   100%
src/resume_ranker/models/resume.py                              121      0      0      0   100%
src/resume_ranker/models/run.py                                  48      0      0      0   100%
src/resume_ranker/models/scoring.py                              93      1      2      1    98%
src/resume_ranker/models/source.py                               30      0      0      0   100%
src/resume_ranker/ontology/__init__.py                           13      0      0      0   100%
src/resume_ranker/ontology/employer.py                           24      0      6      0   100%
src/resume_ranker/ontology/loader.py                             62      1      8      1    97%
src/resume_ranker/ontology/match.py                             138     16     54     11    86%
src/resume_ranker/ontology/titles.py                             70     11     26      6    82%
src/resume_ranker/pipeline.py                                   270     21     74     17    87%
src/resume_ranker/protocols.py                                   44      0      0      0   100%
src/resume_ranker/report/__init__.py                             25      0      2      0   100%
src/resume_ranker/report/_helpers.py                             70      8     22      5    86%
src/resume_ranker/report/audit.py                                34      1      8      2    93%
src/resume_ranker/report/copies.py                               31      0      8      0   100%
src/resume_ranker/report/csv.py                                  27      0      2      0   100%
src/resume_ranker/report/diagnostics.py                          60      0     14      0   100%
src/resume_ranker/report/explain.py                              27      2     12      2    90%
src/resume_ranker/report/html.py                                 43      1     12      2    95%
src/resume_ranker/report/json.py                                 22      0      2      0   100%
src/resume_ranker/report/xlsx.py                                 68      0     16      0   100%
src/resume_ranker/scoring/__init__.py                             3      0      0      0   100%
src/resume_ranker/scoring/aggregate.py                           40      0     12      1    98%
src/resume_ranker/scoring/bands.py                               13      0      8      0   100%
src/resume_ranker/scoring/confidence.py                          39      0     20      1    98%
src/resume_ranker/scoring/dimensions/__init__.py                  1      0      0      0   100%
src/resume_ranker/scoring/dimensions/s1_required_skills.py       19      0      2      0   100%
src/resume_ranker/scoring/dimensions/s2_preferred_skills.py      19      0      2      0   100%
src/resume_ranker/scoring/dimensions/s3_semantic.py             172      7     62      8    94%
src/resume_ranker/scoring/dimensions/s4_experience.py           142      8     56      2    94%
src/resume_ranker/scoring/dimensions/s5_title.py                 84      8     34      2    90%
src/resume_ranker/scoring/dimensions/s6_domain.py                75      8     28      2    88%
src/resume_ranker/scoring/dimensions/s7_education.py            107      5     46      2    95%
src/resume_ranker/scoring/dimensions/s8_skill_recency.py         31      0      6      0   100%
src/resume_ranker/scoring/dimensions/s9_trajectory.py            97      7     42      2    92%
src/resume_ranker/scoring/dimensions/s10_parseability.py         51      0     22      0   100%
src/resume_ranker/scoring/evidence.py                           202      5     86      3    97%
src/resume_ranker/scoring/filters.py                             28      0      8      0   100%
src/resume_ranker/scoring/registry.py                            20      1      6      2    88%
src/resume_ranker/scoring/selection.py                           16      0      6      0   100%
src/resume_ranker/scoring/tiebreak.py                            13      0      2      0   100%
src/resume_ranker/structure/__init__.py                           5      0      0      0   100%
src/resume_ranker/structure/dates.py                            118      6     60      5    94%
src/resume_ranker/structure/entities.py                         294     18    122     24    90%
src/resume_ranker/structure/llm_parse.py                        186     16     52     14    86%
src/resume_ranker/structure/sections.py                         168     14     84     13    88%
src/resume_ranker/telemetry.py                                   17      4      0      0    76%
------------------------------------------------------------------------------------------
TOTAL                                                     6328    470   1986    276    90%
Required test coverage of 85% reached. Total coverage: 89.90%

--------------------------------------------------------- benchmark: 1 tests --------------------------------------------------------
Name (time in us)                    Min         Max      Mean   StdDev    Median     IQR  Outliers  OPS (Kops/s)  Rounds  Iterations
-------------------------------------------------------------------------------------------------------------------------------------
test_pipeline_run_benchmark     762.2360  1,235.8780  784.6828  53.8348  771.3250  7.9001    54;139        1.2744     970           1
-------------------------------------------------------------------------------------------------------------------------------------

Legend:
  Outliers: 1 Standard Deviation from Mean; 1.5 IQR (InterQuartile Range) from 1st Quartile and 3rd Quartile.
  OPS: Operations Per Second, computed as 1 / Mean
737 passed, 17 deselected in 15.38s
uv run --group dev python scripts/validate_schemas.py docs/contracts src
wrote docs/contracts/source_document.schema.json
wrote docs/contracts/extracted_text.schema.json
wrote docs/contracts/canonical_resume.schema.json
wrote docs/contracts/jobspec.schema.json
wrote docs/contracts/scorecard.schema.json
wrote docs/contracts/run_manifest.schema.json
wrote docs/contracts/run_result.schema.json

```
## make own: PASS
Command: make own

```
uv run --group dev python scripts/check-ownership.py --base main
OK: all changes in W0 owned paths.

```
## blind-derivation check: PASS
Command: python scripts/qa/check-blind-derivation.py

```
OK: oracle modules were committed before any recorded implementation read.

```
## traceability audit: PASS
Command: python scripts/qa/trace.py

```
Wrote docs/qa/traceability.md

```
## mutation entry point: PASS
Command: python scripts/qa/mutate.py --package resume_ranker/scoring

```
Saved CI/CD stats to mutants/mutmut-cicd-stats.json
Mutation score: 90.8% (killed 1645, survived 162, no_tests 4, total 1811)
Wrote docs/qa/mutants-QG2.md

```

## Manual QG3 checks (per QAP §10 QG3)

| Check | Method | Result |
|---|---|---|
| Open S1 / S2 defects | `docs/qa/defects/*.md` review | 0 open S1/S2 |
| W-priority features present | `docs/qa/traceability.md` review | 0 W-priority features implemented |
| FR-1141 no automated reject path | Inspection of `src/resume_ranker/scoring/selection.py` and `src/resume_ranker/pipeline.py` | PASS — selection only marks `selected`; knockouts keep candidates eligible and scored |
| FR-1142 decision-support banner | Inspection of `src/resume_ranker/report/{csv,html,xlsx,diagnostics,audit}.py` | PASS — banner appears on every artefact |
| FR-1143 review queue above ranked list | Inspection of `src/resume_ranker/report/html.py` template | PASS — review queue section renders before ranked candidates |
| Determinism dossier (5 runs) | 5 offline runs on `tests/corpus/resumes/synthetic` with `--no-cache --force` | PASS — `scores.csv` and `report.html` byte-identical; `audit.jsonl`/`scores.xlsx` differ only in creation timestamps |
| Fairness dossier (automatable portion) | `resume-ranker audit --out <run> --demographics <csv>` | PASS — loads scorecards from `candidates/*.scorecard.json` and produces adverse-impact report per TRD §11.3 |
| Performance dossier (TRD §10.1) | Not run — requires Q-PERF 1,000-resume reference corpus | BLOCKED — awaiting Q-PERF corpus and 6 min / 4 GB target run |
| Runbook from clean machine | Not run — requires a clean environment and human execution | BLOCKED — awaiting runbook execution |
| Legal review of fairness dossier | Not run — requires Legal sign-off | BLOCKED — awaiting Legal review |

## Verdict

SIGNED OFF — with the three blocked manual items above pending external action.
