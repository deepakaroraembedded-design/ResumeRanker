.PHONY: gate fmt lint types imports test schema own e2e bench clean

gate: fmt lint types imports test schema

UV := uv run --group dev

fmt:
	$(UV) ruff format --check src tests

lint:
	$(UV) ruff check src tests

types:
	$(UV) mypy --strict src

imports:
	$(UV) lint-imports

test:
	$(UV) pytest -m "not slow" --cov=ats_scan --cov-fail-under=85

schema:
	$(UV) python scripts/validate_schemas.py docs/contracts src

own:
	$(UV) python scripts/check-ownership.py --base main

e2e:
	$(UV) pytest tests/e2e -m e2e -v

bench:
	$(UV) pytest tests/benchmark --benchmark-compare=tests/benchmark/baseline.json --benchmark-compare-fail=mean:20%

clean:
	rm -rf .pytest_cache .mypy_cache .coverage htmlcov

# QA targets — owned by C-QA, see docs/QA_PLAN.md
qa-gate:
	$(UV) python scripts/qa/gate.py --gate QG2 --incremental

qa-diff:
	$(UV) pytest tests/qa/test_differential_scoring.py -q

qa-mutate:
	$(UV) python scripts/qa/mutate.py --package $(PKG)

qa-trace:
	$(UV) python scripts/qa/trace.py --out docs/qa/traceability.md

qa-flake:
	$(UV) python scripts/qa/flake-detect.py --runs 3

qa-full:
	$(UV) pytest tests/qa -q
