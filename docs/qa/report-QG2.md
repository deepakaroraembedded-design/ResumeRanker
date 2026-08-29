# QA gate report — QG2
*(incremental run)*
## make gate: PASS
Command: make gate

```
make[1]: Entering directory '/home/deepak7121/RESUMERANKER'
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

Analyzed 157 files, 700 dependencies.
-------------------------------------

Layered architecture KEPT
Scoring dimensions never import one another KEPT
Scoring must take time from ScoringContext KEPT
Domain models do not import implementation layers KEPT

Contracts: 4 kept, 0 broken.
uv run --group dev pytest -m "not slow" --cov=ats_scan --cov-fail-under=85
........................................................................ [  9%]
........................................................................ [ 19%]
........................................................................ [ 29%]
........................................................................ [ 39%]
........................................................................ [ 48%]
........................................................................ [ 58%]
........................................................................ [ 68%]
........................................................................ [ 78%]
........................................................................ [ 88%]
........................................................................ [ 97%]
................                                                         [100%]
================================ tests coverage ================================
_______________ coverage: platform linux, python 3.12.14-final-0 _______________

Name                                                     Stmts   Miss Branch BrPart  Cover
------------------------------------------------------------------------------------------
src/ats_scan/__init__.py                                     2      0      0      0   100%
src/ats_scan/cache.py                                       27     15      2      0    41%
src/ats_scan/cli/__init__.py                                 3      0      0      0   100%
src/ats_scan/cli/main.py                                   187     25     56      9    86%
src/ats_scan/codes.py                                       26      2      0      0    92%
src/ats_scan/config/__init__.py                              3      0      0      0   100%
src/ats_scan/config/root.py                                104     13     40      5    88%
src/ats_scan/embeddings/__init__.py                          3      0      0      0   100%
src/ats_scan/embeddings/client.py                           59      2     20      3    94%
src/ats_scan/errors.py                                       4      0      0      0   100%
src/ats_scan/extract/__init__.py                             3      0      0      0   100%
src/ats_scan/extract/ocr/__init__.py                         3      0      0      0   100%
src/ats_scan/extract/ocr/extractor.py                       48     14      6      1    65%
src/ats_scan/extract/office/__init__.py                      3      0      0      0   100%
src/ats_scan/extract/office/extractor.py                   111     14     32      9    80%
src/ats_scan/extract/pdf/__init__.py                         4      0      0      0   100%
src/ats_scan/extract/pdf/_config.py                         35     11     10      2    58%
src/ats_scan/extract/pdf/_extract.py                        90      3     32      6    93%
src/ats_scan/extract/pdf/_normalize.py                      19      1      2      1    90%
src/ats_scan/extract/pdf/_render.py                         23      2      8      2    87%
src/ats_scan/extract/pdf/_tables.py                         51      4     18      4    88%
src/ats_scan/extract/pdf/_tokens.py                        182     14     62     13    87%
src/ats_scan/extract/pdf/extractor.py                       50      3     10      3    90%
src/ats_scan/extract/plain/__init__.py                       3      0      0      0   100%
src/ats_scan/extract/plain/_html.py                         66     18     34      7    65%
src/ats_scan/extract/plain/_langdetect.py                   20      0      8      0   100%
src/ats_scan/extract/plain/_normalise.py                     8      0      0      0   100%
src/ats_scan/extract/plain/extractor.py                     57      2      2      0    97%
src/ats_scan/extract/registry.py                            20      1      6      1    92%
src/ats_scan/fairness/__init__.py                            5      0      0      0   100%
src/ats_scan/fairness/impact.py                            155     10     56      8    91%
src/ats_scan/fairness/proxies.py                            13      0      4      0   100%
src/ats_scan/fairness/redaction.py                         135      7     66      7    93%
src/ats_scan/ingest/__init__.py                              3      0      0      0   100%
src/ats_scan/ingest/manifest.py                            293     36    124     22    86%
src/ats_scan/integrity/__init__.py                           5      0      0      0   100%
src/ats_scan/integrity/_bbox.py                              9      1      2      1    82%
src/ats_scan/integrity/_colour.py                            4      0      0      0   100%
src/ats_scan/integrity/_offset.py                           17      0      4      0   100%
src/ats_scan/integrity/_tokens.py                            4      0      0      0   100%
src/ats_scan/integrity/hidden_text.py                       47      1     18      1    97%
src/ats_scan/integrity/injection.py                         20      0      4      0   100%
src/ats_scan/integrity/stuffing.py                          71      5     40      7    89%
src/ats_scan/jobspec/__init__.py                             4      0      0      0   100%
src/ats_scan/jobspec/codes.py                                7      0      0      0   100%
src/ats_scan/jobspec/compile.py                            252     14    110     14    91%
src/ats_scan/jobspec/review.py                              25      0      4      0   100%
src/ats_scan/jobspec/schema.py                              16      7      4      0    45%
src/ats_scan/llm/__init__.py                                 7      0      0      0   100%
src/ats_scan/llm/adapter.py                                272     51    106     16    76%
src/ats_scan/llm/budget.py                                  35      3     14      1    92%
src/ats_scan/llm/cache.py                                   52      0      0      0   100%
src/ats_scan/llm/prompts.py                                 68      8     30      5    83%
src/ats_scan/llm/security.py                                25      0      8      0   100%
src/ats_scan/llm/transport.py                               52     11      6      2    74%
src/ats_scan/models/__init__.py                             12      0      0      0   100%
src/ats_scan/models/common.py                               24      0      0      0   100%
src/ats_scan/models/config.py                              106      0      0      0   100%
src/ats_scan/models/embeddings.py                            3      0      0      0   100%
src/ats_scan/models/jobspec.py                              48      0      0      0   100%
src/ats_scan/models/llm.py                                   7      0      0      0   100%
src/ats_scan/models/ontology.py                             22      0      0      0   100%
src/ats_scan/models/resume.py                              121      0      0      0   100%
src/ats_scan/models/run.py                                  48      0      0      0   100%
src/ats_scan/models/scoring.py                              93      1      2      1    98%
src/ats_scan/models/source.py                               30      0      0      0   100%
src/ats_scan/ontology/__init__.py                           13      0      0      0   100%
src/ats_scan/ontology/employer.py                           24      0      6      0   100%
src/ats_scan/ontology/loader.py                             62      1      8      1    97%
src/ats_scan/ontology/match.py                             138     16     54     11    86%
src/ats_scan/ontology/titles.py                             70     11     26      6    82%
src/ats_scan/pipeline.py                                   264     21     72     17    87%
src/ats_scan/protocols.py                                   44      0      0      0   100%
src/ats_scan/report/__init__.py                             25      0      2      0   100%
src/ats_scan/report/_helpers.py                             70      8     22      5    86%
src/ats_scan/report/audit.py                                34      1      8      2    93%
src/ats_scan/report/copies.py                               31      0      8      0   100%
src/ats_scan/report/csv.py                                  27      0      2      0   100%
src/ats_scan/report/diagnostics.py                          60      0     14      0   100%
src/ats_scan/report/explain.py                              27      2     12      2    90%
src/ats_scan/report/html.py                                 43      1     12      2    95%
src/ats_scan/report/json.py                                 22      0      2      0   100%
src/ats_scan/report/xlsx.py                                 68      0     16      0   100%
src/ats_scan/scoring/__init__.py                             3      0      0      0   100%
src/ats_scan/scoring/aggregate.py                           40      0     12      1    98%
src/ats_scan/scoring/bands.py                               13      0      8      0   100%
src/ats_scan/scoring/confidence.py                          39      0     20      1    98%
src/ats_scan/scoring/dimensions/__init__.py                  1      0      0      0   100%
src/ats_scan/scoring/dimensions/s1_required_skills.py       19      0      2      0   100%
src/ats_scan/scoring/dimensions/s2_preferred_skills.py      19      0      2      0   100%
src/ats_scan/scoring/dimensions/s3_semantic.py             172      7     62      8    94%
src/ats_scan/scoring/dimensions/s4_experience.py           142      8     56      2    94%
src/ats_scan/scoring/dimensions/s5_title.py                 84      8     34      2    90%
src/ats_scan/scoring/dimensions/s6_domain.py                75      8     28      2    88%
src/ats_scan/scoring/dimensions/s7_education.py            107      5     46      2    95%
src/ats_scan/scoring/dimensions/s8_skill_recency.py         31      0      6      0   100%
src/ats_scan/scoring/dimensions/s9_trajectory.py            97      7     42      2    92%
src/ats_scan/scoring/dimensions/s10_parseability.py         51      0     22      0   100%
src/ats_scan/scoring/evidence.py                           202      5     86      3    97%
src/ats_scan/scoring/filters.py                             28      0      8      0   100%
src/ats_scan/scoring/registry.py                            20      1      6      2    88%
src/ats_scan/scoring/selection.py                           16      0      6      0   100%
src/ats_scan/scoring/tiebreak.py                            13      0      2      0   100%
src/ats_scan/structure/__init__.py                           5      0      0      0   100%
src/ats_scan/structure/dates.py                            118      6     60      5    94%
src/ats_scan/structure/entities.py                         294     18    122     24    90%
src/ats_scan/structure/llm_parse.py                        186     16     52     14    86%
src/ats_scan/structure/sections.py                         168     14     84     13    88%
src/ats_scan/telemetry.py                                   17      4      0      0    76%
------------------------------------------------------------------------------------------
TOTAL                                                     6306    467   1980    278    90%
Required test coverage of 85% reached. Total coverage: 89.87%

--------------------------------------------------------- benchmark: 1 tests --------------------------------------------------------
Name (time in us)                    Min         Max      Mean   StdDev    Median     IQR  Outliers  OPS (Kops/s)  Rounds  Iterations
-------------------------------------------------------------------------------------------------------------------------------------
test_pipeline_run_benchmark     745.6250  1,177.7780  763.0471  42.6596  758.1350  5.1550     18;41        1.3105     852           1
-------------------------------------------------------------------------------------------------------------------------------------

Legend:
  Outliers: 1 Standard Deviation from Mean; 1.5 IQR (InterQuartile Range) from 1st Quartile and 3rd Quartile.
  OPS: Operations Per Second, computed as 1 / Mean
736 passed, 17 deselected in 14.99s
uv run --group dev python scripts/validate_schemas.py docs/contracts src
wrote docs/contracts/source_document.schema.json
wrote docs/contracts/extracted_text.schema.json
wrote docs/contracts/canonical_resume.schema.json
wrote docs/contracts/jobspec.schema.json
wrote docs/contracts/scorecard.schema.json
wrote docs/contracts/run_manifest.schema.json
wrote docs/contracts/run_result.schema.json
make[1]: Leaving directory '/home/deepak7121/RESUMERANKER'

```
## make own: PASS
Command: make own

```
make[1]: Entering directory '/home/deepak7121/RESUMERANKER'
uv run --group dev python scripts/check-ownership.py --base main
OK: all changes in W0 owned paths.
make[1]: Leaving directory '/home/deepak7121/RESUMERANKER'

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
Command: python scripts/qa/mutate.py --package ats_scan/scoring

```
Saved CI/CD stats to mutants/mutmut-cicd-stats.json
Mutation score: 90.8% (killed 1645, survived 162, no_tests 4, total 1811)
Wrote docs/qa/mutants-QG2.md

```

## Verdict

SIGNED OFF
