from __future__ import annotations

import pytest
from tests.fakes import (
    FakeEmbeddingClient,
    FakeIntegrityDetector,
    FakeJobSpecCompiler,
    FakeLLMClient,
    FakeOntology,
    FakeRedactor,
    FakeReportWriter,
    FakeStructurer,
    FakeTextExtractor,
    FakeTitleTaxonomy,
    StubDimension,
)

from ats_scan.protocols import (
    Dimension,
    EmbeddingClient,
    IntegrityDetector,
    JobSpecCompiler,
    LLMClient,
    OntologyIndex,
    Redactor,
    ReportWriter,
    Structurer,
    TextExtractor,
    TitleTaxonomy,
)


@pytest.mark.parametrize(
    ("cls", "protocol"),
    [
        (FakeTextExtractor, TextExtractor),
        (FakeStructurer, Structurer),
        (FakeJobSpecCompiler, JobSpecCompiler),
        (FakeOntology, OntologyIndex),
        (FakeTitleTaxonomy, TitleTaxonomy),
        (FakeLLMClient, LLMClient),
        (FakeEmbeddingClient, EmbeddingClient),
        (FakeIntegrityDetector, IntegrityDetector),
        (FakeRedactor, Redactor),
        (FakeReportWriter, ReportWriter),
        (StubDimension, Dimension),
    ],
)
def test_fake_satisfies_protocol(cls: type, protocol: type) -> None:
    assert isinstance(cls(), protocol)
