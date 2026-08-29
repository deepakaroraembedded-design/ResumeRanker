# Reference oracle

This is an independent second implementation of the ATS-Scan scoring model,
written directly from `docs/TRD.md` §5 without consulting the corresponding
`src/ats_scan/scoring/dimensions/*` files.

## Derivation rules

- Each module implements exactly one TRD clause.
- Inputs are plain dictionaries and lists; the oracle never imports
  implementation modules.
- Every intermediate variable is named after the TRD formula it represents.
- Docstrings cite the TRD section and formula.
- Defaults are explicit and mirror the Wave-0 `ScoringConfig` defaults.

## Clause index

| Module | TRD clause |
|--------|------------|
| `s1.py` | §5.3.1 — required skills coverage |
| `s2.py` | §5.3.2 — preferred skills |
| `s3.py` | §5.3.3 — semantic relevance |
| `s4.py` | §5.3.4 — relevant experience depth |
| `s5.py` | §5.3.5 — role and title alignment |
| `s6.py` | §5.3.6 — domain and industry match |
| `s7.py` | §5.3.7 — education and certifications |
| `s8.py` | §5.3.8 — skill recency |
| `s9.py` | §5.3.9 — career trajectory and stability |
| `s10.py` | §5.3.10 — resume parseability |
| `aggregate.py` | §5.4 — composite aggregation |
| `bands.py` | §5.4 — band thresholds |
| `confidence.py` | §5.5 — confidence |
| `tiebreak.py` | §5.6 — deterministic ranking |

## Use

The differential harness in `tests/qa/test_differential_scoring.py` feeds the
same pre-resolved inputs to the engine and the oracle and asserts equality.
