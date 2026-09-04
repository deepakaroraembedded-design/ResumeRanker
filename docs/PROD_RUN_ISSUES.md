# Production Run Issues & Action Items

**Branch:** `PROD.RUN.ISSUES`  
**Date:** 2026-09-04  
**Run command:** `resume-ranker run` per role with `small-model-config.yaml` (all-MiniLM-L6-v2)  
**Data:** `TESTDATA/RESUMESeptember1/` — five roles, 714 PDF resumes, 744 scorecards produced.

---

## 1. Executive Summary

The pipeline completed successfully for all five roles with **zero extraction failures**. However, the output diagnostics and score distributions show systemic issues that make the current results unreliable for selection decisions:

- The default 8B embedding model does **not fit** on the available 16 GB GPU.
- A fallback small model was used, degrading S3 semantic relevance.
- Integrity detectors produce **massive false positives** (hidden-text and keyword-stuffing).
- The JobSpec compiler extracts **JD prose fragments as required skills**, polluting S1.
- The ontology fails to map common skills (Python, SQL, React, etc.) and does not normalize variants.
- S4 defaults to a neutral 70 for every candidate when no minimum years are specified.
- S5 title matching is too literal for intern roles.
- No adverse-impact audit was performed.

**No candidate scored above 46.11/100; all top candidates were classified as `weak` or `not_a_match`.**

---

## 2. Hardware / Model Issue

### Issue 2.1 — Qwen 8B model OOMs on 16 GB GPU

**Observation:** Running with the default `Qwen/Qwen3-Embedding-8B` fails with:

```
OutOfMemoryError: CUDA out of memory. Tried to allocate 30.00 MiB.
GPU 0 has a total capacity of 15.46 GiB of which 24.44 MiB is free.
```

**Root cause:** The model weights alone consume ~16 GB in FP16, leaving no room for activations. The current code batches resumes but keeps the full model in GPU memory.

**Why a "pipeline / stream resumes" approach does not help:**

- The pipeline already processes one resume at a time through the model.
- The bottleneck is the **model weight footprint**, not the input batch size.
- Reducing `batch_size` to 1 still OOMs because the model is loaded as a whole.

### Action Items

| ID | Action | Owner | Priority |
|---|---|---|---|
| HW-1 | Add 8-bit quantization support to `LocalEmbeddingClient` via `BitsAndBytesConfig(load_in_8bit=True)` so the Qwen model fits in ~8 GB. | C-11 | P0 |
| HW-2 | Add 4-bit quantization option as a fallback for even smaller footprint. | C-11 | P1 |
| HW-3 | Expose `quantization` setting in `EmbeddingConfig` (or env var) so operators can choose without editing code. | C-11 / C-15 | P1 |
| HW-4 | Benchmark runtime and quality against the current `all-MiniLM-L6-v2` workaround and document recommended GPU specs. | C-11 / C-QA | P2 |
| HW-5 | Consider CPU-offloading only as a last-resort option; it is too slow for production volumes. | C-11 | P3 |

---

## 3. Integrity Detection Issues

### Issue 3.1 — Hidden-text detector false positives

**Observation:** Many resumes are flagged as `HIDDEN_TEXT` with 100% of tokens exceeding the threshold:

```
HIDDEN_TEXT,Hidden text detected: 1031 of 1031 tokens (100%) exceed the configured threshold (15%)
HIDDEN_TEXT,Hidden text detected: 1370 of 1370 tokens (100%) exceed the configured threshold (15%)
```

**Impact:** Almost every candidate receives the maximum integrity penalty, compressing the score range and making the flag useless.

### Issue 3.2 — Keyword-stuffing detector false positives

**Observation:** Common skills listed in a dedicated skills section are flagged as "claimed-but-unnarrated":

```
KEYWORD_STUFFING,Keyword stuffing detected: claimed-but-unnarrated skills: Python, Java, SQL, Docker, AWS, React, TypeScript, ...
```

**Impact:** Intern and new-grad resumes, which legitimately list skills without detailed narrative, are penalized heavily.

### Action Items

| ID | Action | Owner | Priority |
|---|---|---|---|
| INT-1 | Fix hidden-text detector: verify it is consuming the correct glyph-level metadata from `ExtractionMetadata` / `TextBlock`; ensure font size / colour checks are not applied to the normalised plain text. | C-06 | P0 |
| INT-2 | Add a calibration pass on the 40 clean fixture resumes: no resume from the clean corpus should trigger a hidden-text flag. | C-06 / C-QA | P0 |
| INT-3 | Tune keyword-stuffing thresholds for new-grad / intern resumes: skills listed in a dedicated skills section should not be counted as "unnarrated" unless the section is disproportionately large. | C-06 | P0 |
| INT-4 | Distinguish between a short skills list and genuine keyword stuffing (repetition, context-free terms). | C-06 | P1 |
| INT-5 | Review the single `INJECTION_ATTEMPT` flag in the AI role to confirm it is a true positive. | C-06 | P2 |

---

## 4. JobSpec Compiler Issues

### Issue 4.1 — JD prose is extracted as skills

**Observation:** The compiled `JobSpec` contains phrases that are not skills:

```
-haves, what you ll gain, ownership meaningful, willingness learn over long checklist,
currently pursuing, genuine instinct clear, non-spammy b2b messaging, texas office,
completed, business, economics, related field
```

These appear in `missing_required` and `matched_required` columns, reducing S1 to a noise signal.

### Action Items

| ID | Action | Owner | Priority |
|---|---|---|---|
| JD-1 | Strengthen the JD skill filter: reject sentence fragments, section headers, benefit statements, and location clauses. | C-09 | P0 |
| JD-2 | Add a blocklist of JD prose patterns (`-haves`, `what you'll gain`, `what you ll gain`, etc.) that must never enter the skill list. | C-09 | P1 |
| JD-3 | Validate that every extracted skill term appears as a noun phrase or known skill shape. | C-09 | P1 |
| JD-4 | Add a test that compiles all five fixture JDs and asserts the noise terms above are absent. | C-09 / C-QA | P0 |

---

## 5. Ontology Issues

### Issue 5.1 — Common technical skills are unmapped

**Observation:** `unmapped_skills.csv` contains fundamental skills:

```
Python, SQL, JavaScript, React, TypeScript, Node.js, Git, GitHub, Docker, AWS,
Pandas, NumPy, PyTorch, TensorFlow, HTML, CSS
```

### Issue 5.2 — Skill variants are not normalized

**Observation:** Skills like `Node.`, `React.`, `Database Management: MySQL`, `Linux (Fedora, Ubuntu)`, `Windows RStudio`, `js`, `NodeJS` are not canonicalized.

### Issue 5.3 — Soft skills and non-technical terms are treated as skills

**Observation:** `Time Management`, `Service`, `English`, `Leadership`, `Communication`, `Problem Solving` are extracted and sometimes scored.

### Action Items

| ID | Action | Owner | Priority |
|---|---|---|---|
| ONTO-1 | Add canonical entries and aliases for the top 50 unmapped technical skills found in the prod run. | C-04 | P0 |
| ONTO-2 | Add skill normalization: strip trailing punctuation, split colon/semi-colon lists, merge variants (`Node.js`, `Node`, `NodeJS`, `js`). | C-04 | P0 |
| ONTO-3 | Add a soft-skill / non-technical filter so terms like `Time Management`, `English`, `Leadership` are not scored as technical skills. | C-04 | P1 |
| ONTO-4 | Persist the ontology embedding index (keyed by ontology version + model snapshot) so it is not rebuilt for every run. | C-04 / C-11 | P2 |
| ONTO-5 | Add a regression test that the prod-run unmapped list shrinks monotonically. | C-04 / C-QA | P1 |

---

## 6. Scoring Dimension Issues

### Issue 6.1 — S4 defaults to neutral 70 for every candidate

**Observation:** Top candidates all have `S4 = 70.00`. This happens when the JD does not specify a minimum-years requirement and the code returns a neutral default.

**Impact:** Experience becomes a non-discriminative dimension.

### Issue 6.2 — S5 is zero for most candidates on intern roles

**Observation:** `S5 = 0.00` for most candidates because their prior titles do not exactly match the intern title.

**Impact:** Title alignment is effectively disabled for intern hiring.

### Issue 6.3 — Score range is compressed

**Observation:** No candidate scored above 46.11; the highest band reached is `weak`.

**Likely causes:**
- Integrity penalties applied to most candidates.
- S1 diluted by JD-prose skills.
- S4 neutralized at 70.
- S5 zeroed for most.

### Action Items

| ID | Action | Owner | Priority |
|---|---|---|---|
| S-1 | Re-evaluate S4 behavior when `a == 0`: return `None` so weight redistributes, or infer a sensible minimum for intern roles. | C-12 | P0 |
| S-2 | Add a config flag or JD hint that allows S5 to use relaxed title matching for intern / entry-level roles. | C-12 / C-09 | P0 |
| S-3 | After fixing INT/JD/ONTO issues, re-run the five roles and verify at least some candidates reach the `good` or `strong` band. | C-QA | P1 |
| S-4 | Review default selection threshold (70.0) per role family; it may be too high for the current JDs and candidate pool. | C-13 / C-15 | P2 |
| S-5 | Add a diagnostic flag `LOW_SCORE_HIGH_CONFIDENCE` when confidence is high but composite is low. | C-13 | P2 |

---

## 7. Performance & Operational Issues

### Issue 7.1 — Ontology embedding index rebuilt on every run

**Observation:** The KNN classifier over canonical skills is reconstructed for every run, causing repeated work.

### Issue 7.2 — No adverse-impact audit performed

**Observation:** The `audit` command was not run with a demographics file.

### Action Items

| ID | Action | Owner | Priority |
|---|---|---|---|
| PERF-1 | Cache the ontology embedding index to disk and load it when the ontology version and model snapshot match. | C-04 / C-11 | P2 |
| PERF-2 | Add a `resume-ranker run-all` convenience wrapper that discovers the five role folders and runs them in one command. | C-15 | P2 |
| PERF-3 | Run adverse-impact audit with a demographics file and verify impact ratios are ≥ 0.80 across groups. | C-14 / C-QA | P1 |
| PERF-4 | Add progress logging / ETA so long runs are observable. | C-15 | P3 |
| PERF-5 | Document recommended GPU/CPU specs and the quantization config for operators. | C-15 | P2 |

---

## 8. Immediate Re-run Checklist

Before the next production run, verify:

- [ ] HW-1 implemented and Qwen model loads on 16 GB GPU without OOM.
- [ ] INT-1 and INT-3 fixed; clean fixture resumes produce zero hidden-text and keyword-stuffing flags.
- [ ] JD-1 and JD-4 fixed; the five JDs no longer compile noise terms as skills.
- [ ] ONTO-1 and ONTO-2 fixed; common technical skills and variants are canonicalized.
- [ ] S-1 and S-2 evaluated; S4 and S5 produce discriminative scores.
- [ ] A demographics file is supplied and the adverse-impact audit is green.
- [ ] `make gate` and `make own` pass on the integration branch.
- [ ] C-QA signs off the re-run with QG2.

---

## 9. Files & Evidence

- Run outputs: `TESTDATA/runs/<role>/`
- Fallback config used: `TESTDATA/small-model-config.yaml`
- JD text conversions: `TESTDATA/RESUMESeptember1/<role>/JD/*.txt`
- This issue log: `docs/PROD_RUN_ISSUES.md`

---

## 10. Component Owner Reference

| Component | Owner ID | Issues |
|---|---|---|
| Embedding client | C-11 | HW-* |
| Integrity detectors | C-06 | INT-* |
| JobSpec compiler | C-09 | JD-* |
| Ontology / titles | C-04 | ONTO-* |
| Scoring dimensions | C-12 | S-* |
| Aggregation / confidence | C-13 | S-4, S-5 |
| CLI / pipeline | C-15 | PERF-2, PERF-4, PERF-5 |
| Fairness / audit | C-14 | PERF-3 |
| Independent QA | C-QA | all verification gates |
