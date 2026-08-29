# QA gate report — QG0
## make gate: FAIL
Command: make gate

```
uv run --group dev ruff format --check src tests
192 files already formatted
uv run --group dev ruff check src tests
I001 [*] Import block is un-sorted or un-formatted
  --> tests/test_fakes_satisfy_protocols.py:1:1
   |
 1 | / from __future__ import annotations
 2 | |
 3 | | import pytest
 4 | | from tests.fakes import (
 5 | |     FakeEmbeddingClient,
 6 | |     FakeIntegrityDetector,
 7 | |     FakeJobSpecCompiler,
 8 | |     FakeLLMClient,
 9 | |     FakeOntology,
10 | |     FakeRedactor,
11 | |     FakeReportWriter,
12 | |     FakeStructurer,
13 | |     FakeTextExtractor,
14 | |     FakeTitleTaxonomy,
15 | |     StubDimension,
16 | | )
17 | |
18 | | from ats_scan.protocols import (
19 | |     Dimension,
20 | |     EmbeddingClient,
21 | |     IntegrityDetector,
22 | |     JobSpecCompiler,
23 | |     LLMClient,
24 | |     OntologyIndex,
25 | |     Redactor,
26 | |     ReportWriter,
27 | |     Structurer,
28 | |     TextExtractor,
29 | |     TitleTaxonomy,
30 | | )
   | |_^
help: Organize imports
   |
3  | import pytest
   - from tests.fakes import (
   -     FakeEmbeddingClient,
   -     FakeIntegrityDetector,
   -     FakeJobSpecCompiler,
   -     FakeLLMClient,
   -     FakeOntology,
   -     FakeRedactor,
   -     FakeReportWriter,
   -     FakeStructurer,
   -     FakeTextExtractor,
   -     FakeTitleTaxonomy,
   -     StubDimension,
   - )
4  |
--------------------------------------------------------------------------------
17 | )
18 + from tests.fakes import (
19 +     FakeEmbeddingClient,
20 +     FakeIntegrityDetector,
21 +     FakeJobSpecCompiler,
22 +     FakeLLMClient,
23 +     FakeOntology,
24 +     FakeRedactor,
25 +     FakeReportWriter,
26 +     FakeStructurer,
27 +     FakeTextExtractor,
28 +     FakeTitleTaxonomy,
29 +     StubDimension,
30 + )
31 |
   |

Found 1 error.
[*] 1 fixable with the `--fix` option.

```

```stderr
make: *** [Makefile:11: lint] Error 1

```
## make own: FAIL
Command: make own

```
uv run --group dev python scripts/check-ownership.py --base contracts-frozen

```

```stderr
Unknown component: C
make: *** [Makefile:26: own] Error 1

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

## Verdict

BLOCKED
