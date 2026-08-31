from __future__ import annotations

import time

import pytest

from resume_ranker.ontology import SkillOntology


@pytest.mark.slow
class TestSkillOntologyBenchmark:
    def test_ten_thousand_lookups_under_200ms(self) -> None:
        """Warm-cache lookup throughput: 10,000 canonicalisations < 200 ms."""
        ontology = SkillOntology()
        lookups = ["python", "py", "sql", "apache-spark", "spark"] * 2000

        # Warm the lookup path.
        for raw in lookups:
            ontology.canonicalise(raw)

        start = time.perf_counter()
        for raw in lookups:
            ontology.canonicalise(raw)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 200.0
