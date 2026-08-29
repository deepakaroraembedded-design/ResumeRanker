# ATS-Scan — rules for all agents

You are implementing ONE component of ATS-Scan. Read `docs/IMPLEMENTATION_PLAN.md`
§2.2 (ownership) and your own block in §4 before writing any code.

## Hard rules

1. Write ONLY inside your component's owned paths. Creating or editing a file outside
them fails the build and the branch is rejected.

2. NEVER modify `src/ats_scan/models/`, `protocols.py`, `errors.py`, `codes.py`,
`pyproject.toml`, `uv.lock`, `Makefile`, `.importlinter`, or anything under `tests/fakes/`.
These are frozen. If one is wrong, write `docs/contract-change/<ID>-NNN.md` describing
the problem and STOP. Do not work around it by editing it.

3. Depend on protocols, never on another component's implementation. Test against
`tests/fakes/`.

4. Do not add third-party dependencies. Everything you need is already pinned.
If something is genuinely missing, record it in `docs/dep-requests/<ID>.md`.

5. Scoring code takes the current date from `ScoringContext.now`. Never call
`date.today()` or import `time`.

6. Stages return `StageResult` with diagnostics on bad input. Raising is reserved for
programmer errors only. Never let a bad document abort a run.

7. Every positive scoring claim carries an `Evidence` span, and `Evidence.quote` must
equal `text[span[0]:span[1]]`.

## Definition of done

`make gate` passes, plus every checkbox in your §4 block. Tests marked
`xfail(strict=True)` that cover your component must now pass — remove the marker, do
not delete or weaken the test.

## Style

Python 3.12, `from __future__ import annotations`, full type annotations,
`mypy --strict` clean. Small pure functions. Docstrings state the TRD section each
formula comes from.
