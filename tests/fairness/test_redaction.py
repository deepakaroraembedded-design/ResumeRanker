from __future__ import annotations

import json

from hypothesis import given
from hypothesis import strategies as st

from ats_scan.fairness.redaction import (
    BlindRedactor,
    redact_text,
    write_reidentification_sidecar,
)
from ats_scan.models.resume import (
    CanonicalResume,
    DatePrecision,
    DateValue,
    EducationEntry,
    ExperienceEntry,
    Identity,
    Location,
    ProjectEntry,
)
from ats_scan.models.run import ScoringContext
from ats_scan.models.source import SourceDocument
from ats_scan.protocols import Redactor


def _make_resume(
    *,
    name: str = "Alice Doe",
    email: str = "alice.doe@example.com",
    path: str = "/input/resumes/alice_doe.pdf",
) -> CanonicalResume:
    """Build a CanonicalResume with a representative set of identity-bearing fields."""
    return CanonicalResume(
        candidate_id="c_00000001",
        source=SourceDocument(
            path=path,
            content_sha256="a" * 64,
            bytes=1234,
            mtime="2026-08-29T00:00:00Z",
            media_type="application/pdf",
        ),
        identity=Identity(
            full_name=name,
            emails=(email,),
            phones=("+1-555-0100",),
            links={"linkedin": "https://linkedin.com/in/alicedoe"},
            location=Location(city="New York", region="NY", country="USA"),
        ),
        summary={
            "name": name,
            "gender": "female",
            "objective": "Senior engineering role",
        },
        education=(
            EducationEntry(
                institution="Massachusetts Institute of Technology",
                degree_level="Bachelor of Science",
                field="Computer Science",
                start=DateValue(value="2011-09", precision=DatePrecision.YEAR),
                end=DateValue(value="2015-06", precision=DatePrecision.YEAR),
            ),
        ),
        experience=(
            ExperienceEntry(
                employer="Acme Corp",
                title_raw="Software Engineer",
                start=DateValue(value="2015-07", precision=DatePrecision.YEAR),
                end=DateValue(value="2026-08", precision=DatePrecision.YEAR),
                location=Location(city="San Francisco", region="CA", country="USA"),
            ),
        ),
        projects=(
            ProjectEntry(
                title="Open-source parser",
                start=DateValue(value="2020-01", precision=DatePrecision.YEAR),
                end=DateValue(value="2021-01", precision=DatePrecision.YEAR),
                location=Location(city="Austin", region="TX", country="USA"),
            ),
        ),
        parse_completeness=0.95,
    )


def test_blind_redactor_satisfies_protocol() -> None:
    """BlindRedactor is a runtime-checkable Redactor implementation."""
    assert isinstance(BlindRedactor(), Redactor)


def test_redaction_removes_identity() -> None:
    """Identity fields are redacted and stored in the sidecar mapping."""
    resume = _make_resume()
    redactor = BlindRedactor(blind=True)
    redacted, mapping = redactor.redact(resume)

    assert redacted.identity is not None
    assert redacted.identity.full_name is None
    assert mapping["identity.full_name"] == "Alice Doe"
    assert mapping["identity.emails"] == "alice.doe@example.com"
    assert mapping["identity.phones"] == "+1-555-0100"
    assert mapping["identity.links.linkedin"] == "https://linkedin.com/in/alicedoe"
    assert mapping["identity.location.city"] == "New York"
    assert mapping["identity.location.region"] == "NY"
    assert mapping["identity.location.country"] == "USA"

    assert redacted.identity.location is not None
    assert redacted.identity.location.city is None
    assert redacted.identity.location.region is None
    assert redacted.identity.emails == ()
    assert redacted.identity.phones == ()
    assert redacted.identity.links == {}


def test_redaction_removes_source_path() -> None:
    """The source file path is redacted to a candidate-relative placeholder."""
    resume = _make_resume()
    redacted, mapping = BlindRedactor().redact(resume)
    assert mapping["source.path"] == "/input/resumes/alice_doe.pdf"
    assert redacted.source.path == "c_00000001/redacted"


def test_redaction_removes_education_institution_and_graduation() -> None:
    """Education institution and graduation year are redacted; the sidecar
    retains the interval relative to the first role."""
    resume = _make_resume()
    redacted, mapping = BlindRedactor().redact(resume)

    edu = redacted.education[0]
    assert edu.institution is None
    assert mapping["education.0.institution"] == "Massachusetts Institute of Technology"
    assert mapping["education.0.end"] == "2015-06"
    assert mapping["education.0.end_interval_to_first_role"] == "0 years before first role"
    assert edu.end is None or edu.end.value is None


def test_redaction_removes_experience_and_project_locations() -> None:
    """Location details inside experience and project entries are redacted."""
    resume = _make_resume()
    redacted, mapping = BlindRedactor().redact(resume)

    assert redacted.experience[0].location.city is None
    assert mapping["experience.0.location.city"] == "San Francisco"
    assert redacted.projects[0].location.city is None
    assert mapping["projects.0.location.city"] == "Austin"


def test_redaction_scrubs_summary_identity_keys() -> None:
    """Known identity keys in the summary dict are replaced."""
    resume = _make_resume()
    redacted, mapping = BlindRedactor().redact(resume)

    assert mapping["summary.name"] == "Alice Doe"
    assert mapping["summary.gender"] == "female"
    assert redacted.summary["name"] == "[REDACTED]"
    assert redacted.summary["gender"] == "[REDACTED]"
    assert redacted.summary["objective"] == "Senior engineering role"


def test_redaction_non_blind_passes_through() -> None:
    """In non-blind mode the resume and the sidecar are unchanged."""
    resume = _make_resume()
    redactor = BlindRedactor(blind=False)
    redacted, mapping = redactor.redact(resume)
    assert redacted is resume
    assert mapping == {}


def test_counterfactual_name_swap_blind_mode() -> None:
    """Blind name swaps produce identical redacted resumes."""
    r1 = _make_resume(name="Alice Doe", email="alice.doe@example.com")
    r2 = _make_resume(name="Bob Smith", email="bob.smith@example.com")
    redactor = BlindRedactor(blind=True)
    red1, map1 = redactor.redact(r1)
    red2, map2 = redactor.redact(r2)

    assert red1 == red2
    assert map1["identity.full_name"] != map2["identity.full_name"]


def test_counterfactual_name_swap_non_blind_mode() -> None:
    """Non-blind name swaps preserve identity in the redacted resume."""
    r1 = _make_resume(name="Alice Doe", email="alice.doe@example.com")
    r2 = _make_resume(name="Bob Smith", email="bob.smith@example.com")
    redactor = BlindRedactor(blind=False)
    red1, _ = redactor.redact(r1)
    red2, _ = redactor.redact(r2)

    assert red1.identity.full_name == "Alice Doe"
    assert red2.identity.full_name == "Bob Smith"


def test_redact_text_scrubs_prompts() -> None:
    """redact_text removes sidecar values from arbitrary prompt strings."""
    resume = _make_resume()
    _, mapping = BlindRedactor().redact(resume)
    prompt = (
        "Evaluate Alice Doe (alice.doe@example.com) from New York, "
        "who graduated from Massachusetts Institute of Technology."
    )
    redacted = redact_text(prompt, mapping)

    assert "Alice Doe" not in redacted
    assert "alice.doe@example.com" not in redacted
    assert "New York" not in redacted
    assert "Massachusetts Institute of Technology" not in redacted
    assert "[REDACTED]" in redacted


def test_redact_text_with_empty_mapping() -> None:
    """redact_text returns the original text when the mapping is empty."""
    prompt = "No redactions here."
    assert redact_text(prompt, {}) == prompt


def test_redact_text_ignores_redacted_marker() -> None:
    """redact_text does not loop on the literal redacted marker."""
    mapping = {"identity.full_name": "[REDACTED]"}
    assert redact_text("Hello [REDACTED]", mapping) == "Hello [REDACTED]"


def test_write_reidentification_sidecar(tmp_path) -> None:
    """The sidecar is written as JSON with restrictive file permissions."""
    mapping = {"identity.full_name": "Alice Doe", "identity.emails": "alice.doe@example.com"}
    path = tmp_path / "sidecar.json"
    write_reidentification_sidecar(mapping, path)

    assert path.exists()
    assert (path.stat().st_mode & 0o777) == 0o600
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == {
        "identity.emails": "alice.doe@example.com",
        "identity.full_name": "Alice Doe",
    }


def test_scoring_context_has_no_reidentification_path() -> None:
    """The scoring path cannot receive the re-identification sidecar."""
    assert "reidentification_map" not in ScoringContext.model_fields


def test_scoring_context_has_no_demographics_path() -> None:
    """Demographics are supplied only to the audit path, never to scoring."""
    assert "demographics" not in ScoringContext.model_fields
    assert "demographics_path" not in ScoringContext.model_fields


def test_redaction_preserves_non_identity_fields() -> None:
    """Non-identity fields such as skills, bullets, and completeness are untouched."""
    resume = _make_resume()
    redacted, _ = BlindRedactor().redact(resume)
    assert redacted.candidate_id == "c_00000001"
    assert redacted.parse_completeness == 0.95
    assert redacted.experience[0].employer == "Acme Corp"
    assert redacted.experience[0].title_raw == "Software Engineer"


@given(st.booleans())
def test_redaction_is_idempotent_under_same_mode(blind: bool) -> None:
    """Redacting an already-redacted resume again yields the same redacted resume."""
    resume = _make_resume()
    redactor = BlindRedactor(blind=blind)
    red1, _ = redactor.redact(resume)
    red2, _ = redactor.redact(red1)
    assert red1 == red2


def test_redaction_does_not_bring_scorecard_data() -> None:
    """ScoreCard-like fields are not required for redaction; it works on a minimal resume."""
    minimal = CanonicalResume(
        candidate_id="c_min",
        source=SourceDocument(
            path="/tmp/min.pdf",
            content_sha256="b" * 64,
            bytes=10,
            mtime="2026-08-29T00:00:00Z",
            media_type="application/pdf",
        ),
    )
    redacted, mapping = BlindRedactor().redact(minimal)
    assert mapping == {"source.path": "/tmp/min.pdf"}
    assert redacted.source.path == "c_min/redacted"
