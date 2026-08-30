# ATS-Scan — QA Plan & QA Agent Definition

| | |
|---|---|
| **Document** | Quality assurance plan and QA agent specification |
| **System** | ATS-Scan — resume screening & scoring engine |
| **Companions** | *Technical Requirements & Design Document v1.0* (**TRD**) · *Implementation Design & Multi-Agent Build Plan v1.1* (**IDP**) |
| **Version** | 1.0 |
| **Date** | 29 August 2026 |
| **Author** | Deepak Arora |
| **Owning agent** | `qa-engineer` — component **C-QA** in the IDP ownership map |
| **Status** | Ready to execute from the moment Wave 0 is tagged |

---

## 0. The problem this plan exists to solve

The IDP has fourteen agents each writing their own implementation *and their own tests*. That is a reasonable way to get code written quickly, and it is a terrible way to establish that the code is correct, because an agent that misreads a formula will write tests that agree with its misreading. The tests go green. The gate passes. `contract-guard` sees a tidy branch. Nothing catches it.

This matters more here than in most systems. ATS-Scan produces a number that influences whether a person is considered for a job. A scoring formula that is subtly wrong does not crash, does not fail a type check, and does not look wrong in a report — it just quietly ranks the wrong people. The whole point of the ten-dimension design in TRD §5 is that the numbers are defensible; a wrong number that nobody detected is worse than no number at all.

So QA here is not "run the tests and check coverage". It is **independent verification**: a separate agent, working from the TRD rather than from the code, whose job is to disagree with the implementation and produce evidence when it does.

Three techniques carry most of the weight, and everything else in this document supports them:

1. **A reference oracle** (§3) — an independent second implementation of the scoring model, derived from the TRD text alone, cross-checked against the real engine. Two independent derivations agreeing is real evidence. One implementation agreeing with its own tests is not.
2. **Mutation testing** (§4) — deliberately breaking the implementation to confirm the tests notice. This is the only reliable way to tell a real test from a test that passes for the wrong reason.
3. **Traceability auditing** (§5) — proving that every Must-have requirement has a test that genuinely constrains it, rather than a test that merely mentions it.

---

## 1. QA charter

### 1.1 The independence principle

**The QA agent never writes implementation code. Component agents never write QA tests.** This is a two-way wall, enforced the same way every other boundary in the IDP is enforced — by the ownership map and `scripts/check-ownership.py`.

| | Reads | Writes |
|---|---|---|
| **QA agent** | Everything: TRD, IDP, `src/**`, all component tests | `tests/qa/**`, `docs/qa/**`, `scripts/qa/**` only |
| **Component agents** | `src/ats_scan/models/**`, `protocols.py`, `tests/fakes/**`, their own paths | Their own paths only — **never** `tests/qa/**` |

QA reading `src/` is deliberate and necessary — you cannot triage a defect without reading the code. The constraint is that QA may not *fix* it. The one exception, and it is a strict one: **the reference oracle in `tests/qa/oracle/` must be written before its corresponding implementation is read** (§3.2). Everywhere else, reading is encouraged.

### 1.2 Authority

- QA **can block a merge**. A gate failure with an open S1 defect stops the branch; there is no override.
- QA **cannot fix anything**. Every finding becomes a defect record routed to the component that owns the file (§8).
- QA **cannot weaken a test to make a gate pass**. If a QA test is wrong, QA fixes the QA test and says so in the gate report; if an implementation is wrong, QA files a defect.
- QA **does not own CI infrastructure** — that is Wave 0's — nor does it sign off on fairness *policy*, which per TRD §11 is Legal's. QA verifies that the policy the TRD states is what the code does.

### 1.3 What QA does not do

Stated explicitly, because scope creep into these areas is the usual way a QA function becomes a bottleneck:

- Not component unit tests. Each component writes and owns those (IDP §4).
- Not the `xfail(strict=True)` scoring tests. Wave 0 owns those; QA audits whether they were honestly satisfied.
- Not code review for style, structure or performance-in-the-small. `contract-guard` and the gate cover that.
- Not defect fixing, ever.

---

## 2. Quality model

Six dimensions, each with a distinct verification technique, because a single test suite verifies none of them well.

| # | Dimension | The question | Primary technique | Gate |
|---|---|---|---|---|
| Q1 | **Functional correctness** | Does it compute what TRD §5 specifies? | Differential testing against the reference oracle (§3) | QG1, QG2 |
| Q2 | **Test adequacy** | Do the tests actually constrain the behaviour? | Mutation testing (§4) | QG1 |
| Q3 | **Requirement coverage** | Is every Must-have requirement genuinely tested? | Traceability audit (§5) | QG1, QG3 |
| Q4 | **Robustness** | Does it survive hostile and malformed input? | Adversarial corpus + fuzzing (§6.2, §6.3) | QG2 |
| Q5 | **Fairness** | Does it treat like candidates alike? | Counterfactual + distributional testing (§6.4) | QG2, QG3 |
| Q6 | **Operational** | Determinism, performance, resource, degradation | Repeat-run diffing + benchmark suite (§7) | QG2, QG3 |

Q1 and Q2 are the pair that matter most. Q1 asks whether the code is right; Q2 asks whether you would know if it were not. A project with strong Q1 and weak Q2 is correct today and will silently regress; the reverse is a well-tested implementation of the wrong thing.

---

## 3. The reference oracle

### 3.1 What it is

`tests/qa/oracle/` contains a second, independent implementation of the entire scoring model of TRD §5 — the ten sub-scores, the aggregation, confidence, banding and tie-break. It is used only to cross-check the real engine.

It is written to be *obviously* correct rather than fast or elegant:

- Pure functions over plain dictionaries and lists. No ontology, no `ScoringContext`, no protocols — the oracle takes pre-resolved inputs.
- Explicit loops and named intermediate variables, one per line of the TRD formula.
- Every function carries the TRD clause it implements as its docstring, and the docstring is the specification the function is checked against.
- No shared code with `src/ats_scan/` whatsoever. `import-linter` gets a contract forbidding `tests.qa.oracle` from importing anything under `ats_scan` except `ats_scan.models`.

```python
# tests/qa/oracle/s1.py
def s1_required_skills(required: list[dict], evidence: dict, cfg: dict, now: date) -> float:
    """TRD §5.3.1.  S1 = 100 x SUM(w_i x m_i) / SUM(w_i)

    m_i = max over evidence e of  f_match(e) x f_prof(e) x f_recency(e)
    """
    weighted_sum = 0.0
    weight_total = 0.0
    for skill in required:
        w = skill["weight"]
        best_m = 0.0
        for e in evidence.get(skill["canonical"], []):
            f_match = MATCH_FACTOR[e["route"]]
            f_prof = PROF_FACTOR[e["proficiency"]]
            f_recency = recency_factor(e["last_used"], now, cfg, skill["timeless"])
            m = f_match * f_prof * f_recency
            if m > best_m:
                best_m = m
        weighted_sum += w * best_m
        weight_total += w
    if weight_total == 0:
        return 100.0          # TRD §5.3.1: no required skills -> dimension is vacuous
    return 100.0 * weighted_sum / weight_total
```

### 3.2 The blind-derivation rule

The oracle for a dimension **must be written before the QA agent reads that dimension's implementation.** The rule exists because the entire value of the oracle is that it is an independent derivation; an oracle written by transcribing `src/` is a very expensive way to prove that a file equals itself.

Practically:

1. QA writes `tests/qa/oracle/sN.py` from TRD §5.3.N and the Wave-0 `xfail` test tables only.
2. QA commits it and tags the commit message `oracle: blind derivation of SN`.
3. Only then may QA read `src/ats_scan/scoring/dimensions/sN_*.py`.
4. The commit history is the evidence. `scripts/qa/check-blind-derivation.py` asserts that each oracle module's first commit predates the QA agent's first read of the corresponding implementation, as recorded in `docs/qa/read-log.md`.

This is honour-system-with-a-paper-trail rather than an airtight control, and that is acceptable — the agent has no incentive to cheat, and the log makes an accidental violation visible during review.

### 3.3 Differential testing

```python
# tests/qa/test_differential_scoring.py
@given(case=scoring_cases())          # Hypothesis strategy, tests/qa/strategies.py
@settings(max_examples=2000, deadline=None)
def test_engine_agrees_with_oracle(case):
    engine = score_with_engine(case)
    oracle = score_with_oracle(case)
    assert engine.composite == pytest.approx(oracle.composite, abs=1e-6)
    assert engine.band == oracle.band
    for dim in "S1 S2 S3 S4 S5 S6 S7 S8 S9 S10".split():
        assert engine.sub[dim] == pytest.approx(oracle.sub[dim], abs=1e-6), dim
```

Plus a ranking-level check, because agreeing on scores but disagreeing on order would still be a defect:

```python
def test_engine_and_oracle_produce_identical_ranking(pool):
    assert [c.candidate_id for c in rank_with_engine(pool)] \
        == [c.candidate_id for c in rank_with_oracle(pool)]
```

### 3.4 When they disagree

**Neither implementation is presumed correct.** A disagreement is a QA finding whose resolution is a reading of the TRD, not a patch to whichever side looks wrong.

The defect record must contain: the minimal reproducing case (Hypothesis `@example`-pinned), both computed values, the TRD clause in dispute, and QA's reading of it. Then:

| Finding | Action |
|---|---|
| Engine wrong | S1 defect against the owning component (§8) |
| Oracle wrong | QA fixes the oracle, records the correction in the gate report, and re-runs |
| **TRD ambiguous** | Escalate to the engineering lead. Do **not** pick a reading. Ambiguity found this way is the most valuable output QA produces — it means the specification would have been implemented two different ways by two different people |

Every resolved disagreement is pinned as a permanent regression case in `tests/qa/regression/`.

### 3.5 Oracle scope

| Covered by the oracle | Not covered, and why |
|---|---|
| S1–S10, aggregation, integrity penalties, confidence, banding, tie-break, weight redistribution | Parsing and extraction — there is no meaningful second implementation of "read this PDF"; verified by golden corpus instead (§6.1) |
| Knockout three-valued logic | LLM-dependent behaviour — non-deterministic by nature; verified through recorded transports and the offline path |
| Pool calibration for S3 | Report rendering — verified by golden files |

For S3 the oracle covers the arithmetic (max-similarity aggregation, percentile calibration, the 0.6/0.4 blend) with embedding similarities and rubric scores supplied as fixed inputs. It does not attempt to reproduce an embedding model.

---

## 4. Test adequacy — mutation testing

### 4.1 Rationale

A green test suite proves that the tests pass, not that they would fail if the code were wrong. Mutation testing settles the question empirically: introduce a small defect, run the suite, and see whether anything notices. A mutant that survives is a hole in the tests, and in a codebase where fourteen agents wrote their own tests, surviving mutants are where the real risk lives.

### 4.2 Targets

Run with `mutmut` (or `cosmic-ray`) over `src/`, scoped per package, nightly and at QG1.

| Package | Mutation score | Rationale |
|---|---:|---|
| `scoring/**` | **≥ 90 %** | Pure arithmetic against a written specification. There is no excuse for a surviving mutant here |
| `integrity/**` | ≥ 85 % | Threshold logic; a surviving mutant usually means an untested boundary |
| `fairness/**` | ≥ 85 % | Correctness here is a compliance matter |
| `structure/**`, `jobspec/**` | ≥ 70 % | Heuristic code with legitimately hard-to-kill mutants |
| `extract/**`, `ingest/**`, `report/**`, `llm/**` | ≥ 60 % | I/O-dominated; golden files carry more of the weight |

The `scoring/**` threshold is a hard gate. The rest are reported and trended; a fall of more than 5 points from the previous run is a finding regardless of the absolute number.

### 4.3 The mutation classes that matter here

Generic mutation tools produce a lot of noise. QA weights triage toward the mutants that correspond to plausible agent errors:

| Mutation | Why it matters in this system |
|---|---|
| Constant replacement (`0.50` → `0.0`, `4.0` → `1.0`) | Every factor table and half-life in TRD §5 is a constant. A surviving constant mutant means that constant is untested |
| Comparison boundary (`>=` → `>`) | S4's four-branch piecewise function and every band boundary live or die on this |
| Arithmetic operator (`*` → `+`) | The multiplicative `f_match × f_prof × f_recency` is the single most important structural claim in S1 |
| Conditional negation | Three-valued knockout logic; `UNVERIFIED` must not become an exclusion |
| Return-value replacement (`None` → `0.0`) | `SubScore.value = None` means "redistribute my weight". Confusing it with `0.0` silently penalises every candidate |

That last one deserves its own dedicated test regardless of what the mutation tool finds, because the two behaviours differ by a large margin in the composite and by nothing at all in the type system.

### 4.4 Triage

Every surviving mutant in a gated package is classified in `docs/qa/mutants-<gate>.md`:

| Class | Meaning | Action |
|---|---|---|
| **Genuine gap** | The mutant is a real defect the tests miss | QA writes a killing test in `tests/qa/`, files an S3 defect asking the component to add its own |
| **Equivalent** | The mutant does not change behaviour | Record with justification; suppress by ID |
| **Unreachable** | Dead code | S3 defect — dead code in a scoring engine is a specification question |
| **Intolerable** | Tests would need to be unreasonably slow or brittle to kill it | Requires engineering-lead sign-off, recorded |

---

## 5. Requirement traceability audit

### 5.1 Mechanism

Every test declares the requirements it covers with a marker:

```python
@pytest.mark.covers("FR-602", "FR-603")
def test_unverified_knockout_keeps_candidate_eligible(): ...
```

`scripts/qa/trace.py` then:

1. Parses every `FR-xxx` and `NFR-xxx` identifier and its MoSCoW priority out of the TRD.
2. Collects `covers` markers across the whole test tree.
3. Cross-references against the mutation results, so that a requirement is only counted as covered if at least one covering test **kills a mutant** in the module implementing it.
4. Emits `docs/qa/traceability.md`.

Step 3 is what makes this more than paperwork. A marker on a test that would pass regardless of the implementation is worse than no marker, because it creates false confidence — the IDP's own §8 verification matrix is exactly the kind of table that can quietly become a lie.

### 5.2 Gate condition

- **Every Must-have requirement has ≥ 1 covering test that kills at least one mutant.** No exceptions; a failure here blocks QG3.
- Every Should-have has ≥ 1 covering test. Gaps are recorded and require lead sign-off.
- Requirements marked `W` (won't have) must have **no** implementation — QA checks for accidental scope creep, which is a real risk with autonomous agents.

---

## 6. QA corpora

Five corpora, QA-owned, versioned under `tests/qa/corpus/` (large binaries via Git LFS or an access-controlled store — see §6.6).

### 6.1 Q-GOLD — accuracy benchmark

200+ resumes across five role families with adjudicated recruiter labels, per TRD §13.2. Drives the accuracy metrics of TRD §13.3 (Precision@10, Recall@25, Spearman ρ, field-level F1).

QA owns the harness and the metric computation; Talent Acquisition owns the labels. QA reports the numbers, and does not adjust the corpus to improve them — a corpus edited to make a metric pass is no longer a benchmark.

### 6.2 Q-ADV — adversarial corpus

Minimum 40 documents, grown by every incident:

- Hidden text: white-on-white, 1 pt, render mode 3, off-media-box, and combinations
- Keyword stuffing: density variants, repetition without context, list-only claims
- Prompt injection: direct instructions, role-play framing, delimiter escape attempts, injection in metadata rather than body, injection in a language other than the document's main language
- Malformed: truncated PDFs, corrupt zip central directory, compression bombs, deeply nested structures, pathological page counts
- Path and encoding attacks: traversal in embedded filenames, control characters, bidirectional overrides in names

Every adversarial case carries an `expected` record stating the flag that must fire and the maximum permitted score movement.

### 6.3 Q-EDGE — edge case corpus

One fixture per row of the TRD §12 edge-case table — 22 cases, each with the documented expected handling as an assertion. This is the corpus that catches "handled in the design document, never implemented".

Fuzzing supplements it: `hypothesis` strategies over `CanonicalResume` and `JobSpec` in `tests/qa/strategies.py`, plus `atheris`-style byte-level fuzzing of the extraction entry points with a 30-minute nightly budget. Any input that raises an unhandled exception is an S2 defect by definition — TRD §10.3 says a bad document never aborts a run.

### 6.4 Q-FAIR — fairness corpus

- **Counterfactual pairs**: identical resumes differing in exactly one attribute — name (gender- and ethnicity-associated), pronouns, graduation year, a 12-month employment gap, institution, address.
- **Synthetic cohorts**: 500 generated candidates with known group membership and controlled quality distribution, for impact-ratio testing where the ground-truth answer is known by construction.

Assertions per TRD §13.4: blind mode → **exactly zero** composite change on name swap; gap injection → exactly zero change; graduation-year shift → change bounded by the `r_min` floor; balanced-quality cohort → every impact ratio ≥ 0.80.

### 6.5 Q-PERF — performance corpus

The 1,000-resume reference workload of TRD §10.1, with a fixed 5 % OCR share and a documented page-count distribution. Regenerating it invalidates every benchmark baseline, so it is versioned and frozen; a new version starts a new baseline series rather than continuing the old one.

### 6.6 Corpus governance

Q-GOLD contains real personal data. It is held under a documented lawful basis with consent or full anonymisation, access-controlled, excluded from the public repository tree, never used to train or fine-tune any model, and subject to the same retention policy as production runs (TRD §10.5). Q-ADV, Q-EDGE, Q-FAIR and Q-PERF are synthetic and carry no such restriction.

---

## 7. Operational verification

| Check | Method | Threshold |
|---|---|---|
| **Determinism, offline** | Run the reference batch twice, byte-diff `scores.csv` | Identical. Any difference is S1 |
| **Reproducibility, hybrid** | Five runs against a recorded transport | Composite spread ≤ ±2.0 pts |
| **Order independence** | Shuffle input file order, re-run | Identical ranking |
| **Pool independence** | Score one candidate in pools of 30 / 300 / 1000 | Only S3 may move; all other sub-scores identical |
| **Performance** | `pytest-benchmark` against Q-PERF | TRD §10.1 targets; CI fails on > 20 % mean regression |
| **Resource** | Peak RSS sampled during the reference run | ≤ 4 GB |
| **Degradation** | Fault injection: LLM 500s, timeouts, OCR crash, disk full mid-write | Run completes, exit 0, correct flags recorded |
| **Restart** | Kill at 50 %, restart from cache | Same output as an uninterrupted run |
| **Warm cache** | Re-run unchanged batch | ≤ 90 s |

The pool-independence check is subtle and worth calling out: S3 is deliberately pool-relative (TRD §5.3.3), and it is the *only* dimension permitted to be. A dimension that quietly picked up pool dependence would make scores incomparable in a way that is very hard to notice from the outputs.

---

## 8. Defect management

### 8.1 Severity

| Sev | Definition | Effect |
|---|---|---|
| **S1 Critical** | A composite score is wrong; a candidate is silently dropped; a fairness control is bypassed or a counterfactual test moves; determinism is broken; an injection alters any score | **All merges stop.** Not waivable |
| **S2 Major** | A Must-have requirement is unimplemented or a DoD item is falsely ticked; an unhandled exception on valid input; an NFR missed by > 50 % | Blocks the owning component's merge. Waivable only by the engineering lead, with a recorded deferral |
| **S3 Minor** | Test-adequacy gap; NFR missed by < 50 %; incorrect diagnostic or reason code; report defect | Does not block. Tracked to closure |
| **S4 Trivial** | Documentation, naming, cosmetics | Batched |

### 8.2 Record format

One file per defect, `docs/qa/defects/QA-NNNN.md`:

```markdown
---
id: QA-0042
severity: S1
component: C-13            # from IDP §2.2 ownership map — the file's owner
found_at: QG1
found_by: differential-oracle
requirement: TRD §5.4, FR-702
status: open               # open | accepted | disputed | fixed | verified | wontfix
---

## Summary
Integrity penalty is subtracted before weight renormalisation, not after.

## Reproduction
tests/qa/regression/test_qa_0042.py::test_penalty_applied_after_renormalisation

## Expected vs actual
Given S2 unavailable (weight 8 redistributed) and HIDDEN_TEXT (-25):
  oracle composite  58.31
  engine composite  63.77

## Evidence
TRD §5.4: "composite = clip(base - integrity_penalty, 0, 100)" where base is
already the renormalised weighted mean. Engine applies the penalty to the
pre-renormalisation weighted sum.

## Routing
src/ats_scan/scoring/aggregate.py is owned by C-13 per IDP §2.2.
```

### 8.3 Routing and closure

QA identifies the owning component **from the IDP ownership map**, never by guessing, and files against it. The component agent fixes it in its own files and adds its own regression test; QA independently verifies and moves the record to `verified`. QA's own regression test in `tests/qa/regression/` stays forever, and is never deleted even after the fix — the QA suite is a ratchet.

If a component agent disputes a finding, the record moves to `disputed` and goes to the engineering lead. **QA does not negotiate with the component agent**, because a disagreement about what the TRD means is not resolvable by whichever party argues longer; it is resolved by a human reading the specification.

---

## 9. Flake policy

**A flaky test is an S2 defect, not an inconvenience.** Determinism is a product requirement here (TRD §10.7, O3), so a test that is non-deterministic is either testing non-deterministic behaviour — which is itself the defect — or is badly written.

- Every QA suite runs **three times** in the nightly job. Any test with a non-uniform outcome is auto-quarantined and a defect is filed against the owning component within the same run.
- Quarantined tests are excluded from the gate but **counted**: more than three quarantined tests at any time is itself a QG2 blocker.
- No `flaky`, no `rerun-failures`, no `@pytest.mark.xfail(strict=False)` anywhere in the tree. QA's traceability script fails the build if it finds them.

---

## 10. Quality gates

Four gates. Each has entry criteria (what must be true before QA starts), the checks QA runs, and exit criteria (what must be true for QA to sign off).

### QG0 — Contract freeze audit
**When** After Wave 0, before any component agent is launched. **Duration** One session.

This is the highest-value hour in the whole programme: a contract defect found here costs one fix, and found at QG2 costs fourteen rebases.

| Check | Pass condition |
|---|---|
| Model completeness | Every field in TRD §4.1–4.3 exists in `models/` with the right type and nullability |
| Protocol completeness | Every component in IDP §4 can be implemented against `protocols.py` with no missing capability — QA walks each DoD checklist and confirms the interface supports it |
| Fake fidelity | Each fake satisfies its protocol at runtime and its documented behaviour matches what dependent components will assume |
| `xfail` table correctness | **QA independently recomputes every expected value in the Wave-0 scoring tests from the TRD**, including the §5.8 worked example totalling 87.06 |
| Ownership map | Paths in IDP §2.2 are disjoint and exhaustive; `check-ownership.py` agrees with the document |
| Registry conflict-freedom | No file exists that two components would need to edit |
| Error channel | `StageResult` can express every failure mode in TRD §12 |

**Exit:** zero S1/S2 findings, or the freeze is redone. QG0 failure means *do not fan out*.

### QG1 — Component acceptance
**When** Per branch, after `contract-guard`, before the integrator merges. **Duration** Minutes, automated.

| Check | Pass condition |
|---|---|
| Gate | `make gate` and `make own` green on the branch |
| DoD honesty | Every §4 DoD checkbox is satisfied by code QA can point at — QA re-verifies rather than trusting the agent's report |
| `xfail` integrity | No Wave-0 test was deleted, weakened, or left marked while passing |
| Differential | For scoring components: oracle agreement across 2,000 generated cases |
| Mutation | Package meets its §4.2 threshold |
| Traceability | Every Must-have requirement attributed to this component is covered and mutation-verified |
| Flake | Component suite passes three consecutive runs |
| Boundary | No `date.today()`, no `import time` in scoring, no network in tests, no dependency added |

**Exit:** no open S1 or S2 against this component.

### QG2 — Integration acceptance
**When** After each merge, and in full after all fourteen. **Duration** Minutes incremental, ~1 hour full.

| Check | Pass condition |
|---|---|
| Full QA suite | Green on merged `main`, with previously-skipped suites now active |
| E1–E14 | The IDP §7.5 end-to-end acceptance table |
| Q-EDGE | All 22 TRD §12 edge cases handled as documented |
| Q-ADV | Hidden-text recall ≥ 0.95, injection recall ≥ 0.98, injection efficacy exactly 0 |
| Q-FAIR | All counterfactual assertions hold; synthetic-cohort impact ratios ≥ 0.80 |
| Operational | Every check in §7 |
| Q-GOLD | Accuracy metrics meet TRD §13.3 for the applicable mode |
| Cross-component | Evidence spans resolve correctly end to end — the classic seam defect, where extraction offsets and scoring citations disagree |

**Exit:** no open S1; S2s waived only with a recorded lead decision.

### QG3 — Release acceptance
**When** Before the pilot run on a live requisition (IDP phase P4 exit).

| Check | Pass condition |
|---|---|
| Everything in QG2 | Green |
| Traceability | 100 % of Must-have requirements covered and mutation-verified; no `W`-priority feature implemented |
| Defect state | Zero open S1 or S2; every S3 triaged with an owner and a date |
| Fairness dossier | Adverse-impact report on Q-FAIR and on the pilot pool, reviewed by Legal per TRD §11.5 |
| Determinism dossier | Five-run reproducibility evidence attached |
| Performance dossier | Q-PERF results against every TRD §10.1 target |
| Runbook | QA has executed `docs/runbook.md` end to end from a clean machine and it works as written |
| Human-oversight controls | FR-1141–1143 verified by inspection: no reject path exists, review queue renders above the ranked list, banner present on every artefact |

**Exit:** a signed QG3 report at `docs/qa/report-QG3.md`. **QA sign-off is necessary but not sufficient** — TRD §11.5 requires Legal sign-off independently.

---

## 11. The QA agent

### 11.1 Definition

Add to `opencode.json` (Wave 0 owns this file):

```jsonc
"qa-engineer": {
  "description": "Independent verification for ATS-Scan. Writes and runs the QA suites, maintains the reference oracle, audits test adequacy and requirement coverage, runs the quality gates, and files defects. Never edits implementation code and never fixes defects.",
  "mode": "primary",
  "temperature": 0,
  "prompt": "{file:./.opencode/prompts/qa-engineer.md}",
  "permission": {
    "edit": "allow",
    "bash": "allow",
    "webfetch": "deny"
  }
}
```

> The coarse `edit: allow` cannot express "read `src/`, write only `tests/qa/`". If your opencode version supports path-scoped edit permissions, prefer `"edit": { "src/**": "deny", "tests/qa/**": "allow", "docs/qa/**": "allow", "scripts/qa/**": "allow" }`. Otherwise the boundary is enforced by `scripts/check-ownership.py` in the pre-commit hook and in CI, plus the standing instruction in the prompt. Verify which form your version accepts before the first run.

### 11.2 System prompt

`.opencode/prompts/qa-engineer.md`:

```markdown
You are the QA engineer for ATS-Scan. You are independent of the fourteen
component agents. Your job is to find out whether the system does what the TRD
says, and to produce evidence either way.

## Your sources of truth, in order
1. The TRD — the specification. When code and TRD disagree, the TRD wins, unless
   the TRD is ambiguous, in which case you escalate rather than choose.
2. docs/QA_PLAN.md — this plan. Your gates, corpora and techniques.
3. docs/IMPLEMENTATION_PLAN.md — ownership map, for routing defects.
The implementation is EVIDENCE, never a source of truth. If you find yourself
writing a test by reading src/ and asserting what it currently does, stop —
you are writing a change-detector, not a test.

## Hard rules
1. You write ONLY in tests/qa/**, docs/qa/** and scripts/qa/**. You never edit
   src/, never edit another component's tests, never edit the frozen contracts.
2. You never fix a defect. You file it (QA_PLAN §8) and route it to the owning
   component using the IDP ownership map.
3. You never weaken, skip, quarantine-to-hide, or delete a test to make a gate
   pass. If a QA test is wrong, fix the QA test and say so in the gate report.
4. Blind derivation: before writing tests/qa/oracle/sN.py you must NOT have read
   src/ats_scan/scoring/dimensions/sN_*.py. Write the oracle from the TRD, commit
   it, log it in docs/qa/read-log.md, and only then read the implementation.
5. A gate result is a fact, not a negotiation. Report failures plainly. Do not
   soften a finding because a component agent will have to redo work.
6. Every finding needs a minimal reproducing case that a component agent can run.
   A finding without a repro is an opinion.

## Method for any gate
1. State which gate, its entry criteria, and whether they are met.
2. Run the checks in the QA_PLAN table for that gate, in order.
3. For each failure: minimise the repro, identify the owning component from the
   ownership map, assign a severity, write the defect record.
4. Write docs/qa/report-<gate>.md: checks run, pass/fail each, defects filed by
   severity, metrics (mutation score, coverage, oracle agreement rate, benchmark
   deltas), and an explicit sign-off or refusal with reasons.
5. Never sign off with an open S1. There is no override.

## What you are looking for, specifically
- A formula implemented plausibly but not as specified (differential oracle).
- A test that passes for the wrong reason (mutation testing).
- A requirement with a marker but no real coverage (traceability audit).
- A DoD checkbox ticked without the behaviour existing.
- A dimension that quietly depends on the pool, the clock, or input ordering.
- A fairness control that exists in configuration but not in the code path.
- A candidate that can be lost without a reason code — anywhere, by any path.
```

### 11.3 Commands

Add to the `command` block of `opencode.json`:

| Command | Gate / purpose |
|---|---|
| `/qa-freeze-audit` | QG0 — audit the contract freeze before fan-out |
| `/qa-oracle <SN>` | Blind-derive one oracle module from the TRD |
| `/qa-accept <ID>` | QG1 — component acceptance for one branch |
| `/qa-mutate <package>` | Mutation run plus triage report |
| `/qa-trace` | Traceability audit; regenerates `docs/qa/traceability.md` |
| `/qa-integrate` | QG2 — integration acceptance on merged `main` |
| `/qa-release` | QG3 — full release acceptance and dossiers |
| `/qa-triage <QA-NNNN>` | Re-verify a defect reported as fixed |

```jsonc
"qa-accept": {
  "description": "QG1 component acceptance for one branch",
  "agent": "qa-engineer",
  "template": "Run QG1 acceptance for component $1 on branch feat/$1-*.\n\nFollow docs/QA_PLAN.md §10 QG1. In order:\n1. Confirm entry criteria: make gate and make own are green, contract-guard passed.\n2. Re-verify EVERY Definition of Done checkbox in IDP §4 for $1 against actual code. Do not trust the agent's report. List each box with the file and line that satisfies it, or mark it unmet.\n3. Confirm no Wave-0 xfail test covering $1 was deleted, weakened, or left marked while passing.\n4. If $1 is a scoring component, run the differential oracle over 2000 generated cases.\n5. Run mutation testing on its package; triage survivors per §4.4.\n6. Run the traceability audit for requirements attributed to $1.\n7. Run its suite three times; any non-uniform outcome is a flake defect.\n8. Check boundaries: no date.today(), no import time in scoring, no network in tests, no added dependency.\n\nFile a defect record for every failure. Write docs/qa/report-QG1-$1.md and end with an explicit SIGNED OFF or BLOCKED, listing blocking defect IDs.\n\nYou may not edit any file outside tests/qa/, docs/qa/ and scripts/qa/."
}
```

### 11.4 Where the QA agent sits in the schedule

QA is agent fifteen, running **continuously in parallel** with the component agents rather than after them.

| Phase | QA activity |
|---|---|
| Immediately after Wave 0 tag | **QG0.** Blocking — nothing fans out until QA signs off |
| During Waves 1–2 | Build the QA assets: blind-derive all ten oracle modules, assemble Q-ADV / Q-EDGE / Q-FAIR / Q-PERF, write `strategies.py`, stand up mutation and traceability tooling. None of this needs the implementations |
| As each branch completes | **QG1** per component, on demand |
| During integration | **QG2** after each merge, then in full |
| Before pilot | **QG3** plus the dossiers |
| Ongoing thereafter | Nightly: full QA suite ×3, mutation run, fuzz budget, benchmark trend |

Blind derivation is why QA must start early rather than after the components are done: once QA has read the implementations, the oracle's independence is gone and cannot be recovered.

### 11.5 QA's own definition of done, per gate

- [ ] `docs/qa/report-<gate>.md` written: every check listed with pass/fail, not a summary
- [ ] Every failure has a defect record with a minimal repro and a routed owner
- [ ] Metrics recorded and trended: mutation score per package, requirement coverage, oracle agreement rate, defect counts by severity and age, flake count, benchmark deltas
- [ ] Every resolved oracle disagreement pinned as a permanent case in `tests/qa/regression/`
- [ ] `docs/qa/read-log.md` updated if any implementation was read for the first time
- [ ] Explicit **SIGNED OFF** or **BLOCKED** with reasons — never a hedge

### 11.6 Failure modes of the QA agent itself

An autonomous QA agent has characteristic ways of going wrong. Watch for these in its reports:

| Failure mode | How it shows up | Counter |
|---|---|---|
| **Change-detector tests** | Tests that assert what the code currently does | Blind-derivation rule; a test with no TRD citation is suspect |
| **Rubber-stamping** | Signs off with all checks "pass" and no findings | A gate with zero findings across a fourteen-agent build is itself a finding; spot-check its DoD verification manually |
| **Scope creep into fixing** | "I also corrected the off-by-one in aggregate.py" | Ownership check rejects the commit; re-issue the brief |
| **Metric gaming** | Mutation score met by adding trivial killing tests | Review new QA tests for TRD citations; a test that kills a mutant but asserts nothing meaningful is an S3 against QA itself |
| **Corpus drift** | Q-GOLD edited until the accuracy metric passes | Corpus is versioned and change-reviewed; metric movements are compared against corpus version |
| **Analysis paralysis** | Endless triage, no gate verdict | Gates are time-boxed; an unfinished gate reports BLOCKED with what was covered |

The first two are the most likely and the most damaging. Read at least one QG1 report line by line yourself before trusting the rest.

---

## 12. QA suite layout

```
tests/qa/                                   [C-QA — no component agent may write here]
├── conftest.py
├── strategies.py                  Hypothesis generators for CanonicalResume / JobSpec
├── oracle/                        blind-derived reference implementation
│   ├── s1.py … s10.py  aggregate.py  confidence.py  bands.py  tiebreak.py
│   └── README.md                  derivation rules and TRD clause index
├── test_differential_scoring.py   engine vs oracle, property-driven
├── test_differential_ranking.py   order agreement over pools
├── corpus/
│   ├── gold/                      Q-GOLD  (access-controlled, LFS)
│   ├── adversarial/               Q-ADV
│   ├── edge/                      Q-EDGE  (one per TRD §12 row)
│   ├── fairness/                  Q-FAIR
│   └── perf/                      Q-PERF
├── accuracy/                      Precision@10, Recall@25, Spearman, field F1
├── adversarial/                   hidden text, stuffing, injection efficacy
├── edge/                          the 22 documented edge cases
├── fairness/                      counterfactuals, cohorts, impact ratios
├── operational/                   determinism, order/pool independence, faults
├── regression/                    one pinned case per resolved defect — never deleted
└── fuzz/                          byte-level extraction fuzzing

scripts/qa/                                 [C-QA]
├── trace.py                       requirement ↔ test ↔ mutant cross-reference
├── mutate.py                      mutation runner + triage report
├── check-blind-derivation.py      oracle commit predates implementation read
├── flake-detect.py                three-run outcome comparison
└── gate.py                        runs a named gate, emits the report

docs/qa/                                    [C-QA]
├── report-QG0.md  report-QG1-<ID>.md  report-QG2.md  report-QG3.md
├── traceability.md   mutants-<gate>.md   read-log.md
├── metrics.csv                    trend series across gates
└── defects/QA-NNNN.md
```

---

## Appendix A — Gate checklists

Copy-paste into the gate report.

**QG0**
```
[ ] Models complete vs TRD §4.1–4.3 (field, type, nullability)
[ ] Protocols support every §4 DoD checklist item
[ ] Fakes satisfy protocols at runtime; documented behaviour matches assumptions
[ ] All Wave-0 xfail expected values independently recomputed from the TRD
[ ] §5.8 worked example verified = 87.06
[ ] Ownership map disjoint and exhaustive; check-ownership.py agrees
[ ] No file two components would both need to edit
[ ] StageResult expresses every TRD §12 failure mode
[ ] Zero S1/S2 findings
```

**QG1 — component `<ID>`**
```
[ ] make gate + make own green
[ ] Every DoD box re-verified against code, cited by file:line
[ ] No xfail test deleted, weakened, or left marked while passing
[ ] Differential oracle agreement (scoring components), 2000 cases
[ ] Mutation score meets the §4.2 threshold; survivors triaged
[ ] Must-have requirements covered and mutation-verified
[ ] Three consecutive clean runs
[ ] No date.today(), no import time in scoring, no network in tests, no new dependency
[ ] No open S1 or S2
```

**QG2**
```
[ ] Full QA suite green on merged main
[ ] IDP §7.5 E1–E14 all pass
[ ] Q-EDGE: 22/22
[ ] Q-ADV: hidden-text recall ≥ 0.95, injection recall ≥ 0.98, efficacy = 0
[ ] Q-FAIR: counterfactuals exact, impact ratios ≥ 0.80
[ ] Operational §7: all rows
[ ] Q-GOLD accuracy meets TRD §13.3 for the mode under test
[ ] Evidence spans resolve end to end
[ ] ≤ 3 quarantined tests
[ ] No open S1
```

**QG3**
```
[ ] QG2 green
[ ] 100% Must-have coverage, mutation-verified; no W-priority feature present
[ ] Zero open S1/S2; every S3 has an owner and a date
[ ] Fairness dossier produced and sent to Legal
[ ] Determinism dossier (5 runs) attached
[ ] Performance dossier vs every TRD §10.1 target
[ ] Runbook executed from a clean machine, works as written
[ ] FR-1141–1143 verified by inspection
[ ] Report signed
```

## Appendix B — Defect record template

```markdown
---
id: QA-NNNN
severity: S1 | S2 | S3 | S4
component: C-NN            # from IDP §2.2 — the owner of the offending file
found_at: QG0 | QG1 | QG2 | QG3 | nightly
found_by: differential-oracle | mutation | traceability | adversarial |
          fairness | operational | fuzz | inspection
requirement: TRD §x.y, FR-nnn
status: open | accepted | disputed | fixed | verified | wontfix
---

## Summary
<one sentence>

## Reproduction
<path::test_name, runnable as-is>

## Expected vs actual
<both values, and where each came from>

## Evidence
<the TRD clause, quoted, and why it decides the matter>

## Routing
<offending file, and the component that owns it per IDP §2.2>
```

## Appendix C — QA metrics

Tracked in `docs/qa/metrics.csv`, one row per gate run, to make trends visible rather than only absolute values at a point in time.

| Metric | Target | Trend rule |
|---|---|---|
| Mutation score, `scoring/**` | ≥ 90 % | Any fall is a finding |
| Mutation score, other gated packages | per §4.2 | Fall > 5 pts is a finding |
| Must-have requirement coverage | 100 % at QG3 | Monotonic non-decreasing |
| Oracle agreement rate | 100 % | Any disagreement is at least S2 until resolved |
| Open S1 / S2 | 0 / 0 at every gate | — |
| Mean S3 age | < 14 days | Rising trend is a process finding |
| Quarantined tests | ≤ 3 | — |
| Q-GOLD Precision@10 | per TRD §13.3 | Fall > 0.02 blocks the merge |
| Benchmark mean | per TRD §10.1 | Regression > 20 % fails CI |

---

*Companion to the ATS-Scan TRD v1.0 and Implementation Design & Multi-Agent Build Plan v1.1. **TRD §** references point into the requirements document; **IDP §** into the implementation plan; bare **§** into this one.*
