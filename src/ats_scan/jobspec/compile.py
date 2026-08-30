from __future__ import annotations

import json
import re
from typing import Any

import yaml  # type: ignore[import-untyped]

from ats_scan.jobspec.codes import JobSpecCode
from ats_scan.jobspec.review import write_jobspec
from ats_scan.models.common import Diagnostic, StageResult
from ats_scan.models.jobspec import (
    DomainRequirement,
    EducationRequirement,
    ExperienceRequirement,
    JobSpec,
    KnockoutRule,
    PreferredSkill,
    RequiredSkill,
    ResponsibilityChunk,
)
from ats_scan.models.run import RunContext


class JobSpecCompiler:
    """Deterministic compiler that turns a free-text JD or a hand-authored
    YAML/JSON JobSpec into a validated :class:`JobSpec`.

    Implements the :class:`JobSpecCompiler` protocol from TRD §4.2.
    """

    # Weight phrases ordered by priority (most specific first). Values are the
    # importance weights 1–5 defined by FR-405.
    _WEIGHT_PHRASES: tuple[tuple[str, int], ...] = (
        ("must have", 5),
        ("mandatory", 5),
        ("essential", 5),
        ("required", 5),
        ("strong", 4),
        ("solid", 4),
        ("proficiency", 4),
        ("proficient", 4),
        ("experience with", 3),
        ("familiar", 3),
        ("working knowledge", 3),
        ("knowledge of", 3),
        ("exposure to", 2),
        ("basic", 2),
        ("some", 2),
        ("plus", 1),
    )

    _PROXY_PHRASES: tuple[str, ...] = (
        "digital native",
        "recent graduate",
        "no career gaps",
        "no gaps",
        "young",
        "energetic",
        "native english speaker",
        "american culture",
        "female",
        "male",
        "gender",
        "marital status",
        "married",
        "single",
        "religion",
        "disability",
        "pregnancy",
    )

    _TERMINATOR_HEADINGS: frozenset[str] = frozenset(
        {
            "who you are",
            "success profile",
            "base pay range",
            "benefits",
            "benefits program",
            "benefits overview",
            "pay transparency",
            "equal employment",
            "equal employment opportunity",
            "eeo statement",
            "by applying for this role",
            "by applying",
            "salary ranges",
            "compensation",
            "how to apply",
            "application process",
            "additional information",
            "disclaimer",
            "diversity and inclusion",
            "diversity",
            "inclusion",
            "li-hybrid",
            "li-cm3",
        }
    )

    _TERMINATE: str = "__terminate__"

    _HEADING_MAP: dict[str, str] = {
        "required": "required",
        "requirements": "required",
        "required skills": "required",
        "must have": "required",
        "mandatory": "required",
        "essentials": "required",
        "essential": "required",
        "preferred": "preferred",
        "preferred skills": "preferred",
        "nice to have": "preferred",
        "desired": "preferred",
        "optional": "preferred",
        "experience": "experience",
        "years of experience": "experience",
        "professional experience": "experience",
        "education": "education",
        "qualifications": "education",
        "academic": "education",
        "certifications": "certifications",
        "certificates": "certifications",
        "licenses": "certifications",
        "licences": "certifications",
        "domain": "domain",
        "industry": "domain",
        "knockouts": "knockouts",
        "hard requirements": "knockouts",
        "eligibility": "knockouts",
        "must meet": "knockouts",
        "work authorization": "knockouts",
        "work authorisation": "knockouts",
        "location": "knockouts",
        "work location": "knockouts",
        "responsibilities": "responsibilities",
        "what you'll do": "responsibilities",
        "what you will do": "responsibilities",
        "role expectations": "responsibilities",
        "key responsibilities": "responsibilities",
        "job responsibilities": "responsibilities",
        "what we're looking for": "required",
        "what we are looking for": "required",
        "minimum qualifications": "required",
        "preferred qualifications": "preferred",
        "what will make you stand out": "preferred",
        "stand out": "preferred",
    }

    def __init__(
        self,
        *,
        max_required_skills: int = 12,
        acknowledged_proxies: tuple[str, ...] = (),
        review_mode: bool = False,
        compiled_by: str = "heuristic:rule",
        weight_phrases: tuple[tuple[str, int], ...] | None = None,
    ) -> None:
        self._max_required_skills = max_required_skills
        self._acknowledged_proxies = tuple(p.lower() for p in acknowledged_proxies)
        self._review_mode = review_mode
        self._compiled_by = compiled_by
        self._weight_phrases = (
            weight_phrases if weight_phrases is not None else self._WEIGHT_PHRASES
        )

    def compile(self, source: str, ctx: RunContext) -> StageResult[JobSpec]:
        """Compile *source* into a JobSpec.

        The source may be a free-text JD, a YAML JobSpec, or a JSON JobSpec.
        Compilation failure is fatal per TRD §2.5 / FR-400.
        """
        if not source or not source.strip():
            return _fatal(JobSpecCode.JD_EMPTY, "Job description source is empty.")

        structured = self._parse_structured(source)
        if structured is None:
            spec = self._parse_free_text(source)
        elif isinstance(structured, StageResult):
            return structured
        else:
            spec = structured

        warnings = self._validate_spec(spec)
        if warnings:
            spec = spec.model_copy(update={"warnings": tuple(spec.warnings) + tuple(warnings)})

        if ctx.output_dir is not None:
            try:
                write_jobspec(spec, ctx.output_dir, review_mode=self._review_mode)
            except OSError as exc:
                return _fatal(
                    JobSpecCode.JD_WRITE_FAILED,
                    f"Could not write compiled JobSpec for review: {exc}",
                )

        return StageResult(value=spec)

    def _parse_structured(self, source: str) -> JobSpec | StageResult[JobSpec] | None:
        """Try to parse *source* as YAML or JSON JobSpec.

        Returns the JobSpec, a fatal StageResult on validation or proxy failure,
        or ``None`` if the source does not look structured.
        """
        text = source.strip()
        if not (
            text.startswith("{")
            or text.startswith("[")
            or text.startswith("---")
            or _looks_like_yaml_mapping(text)
        ):
            return None

        try:
            if text.startswith("{") or text.startswith("["):
                data: Any = json.loads(text)
            else:
                data = yaml.safe_load(text)
        except (json.JSONDecodeError, yaml.YAMLError):
            # If it looked structured but failed to parse, treat as free text.
            return None

        if not isinstance(data, dict):
            return None
        if "job_id" not in data and "title" not in data:
            return None

        try:
            spec = JobSpec.model_validate(data)
        except Exception as exc:
            return _fatal(
                JobSpecCode.JD_INVALID_SCHEMA, f"Hand-authored JobSpec failed validation: {exc}"
            )

        fatal = self._check_proxy_knockouts(spec)
        if fatal is not None:
            return fatal

        return spec

    def _check_proxy_knockouts(self, spec: JobSpec) -> StageResult[JobSpec] | None:
        """Enforce FR-407: proxy language in a knockout requires acknowledgement."""
        for rule in spec.knockouts:
            rule_lower = rule.rule.lower()
            for phrase in self._PROXY_PHRASES:
                if phrase in rule_lower and phrase not in self._acknowledged_proxies:
                    return _fatal(
                        JobSpecCode.JD_PROXY_KNOCKOUT_UNACKNOWLEDGED,
                        (
                            f"Knockout rule '{rule.id}' references protected-proxy "
                            f"language '{phrase}' which requires acknowledgement."
                        ),
                    )
        return None

    def _validate_spec(self, spec: JobSpec) -> list[str]:
        """Return warning strings for policy checks such as FR-406."""
        warnings: list[str] = []
        if len(spec.required_skills) > self._max_required_skills:
            warnings.append(
                f"required_skill_count={len(spec.required_skills)} "
                f"(limit {self._max_required_skills})"
            )
        return warnings

    def _parse_free_text(self, source: str) -> JobSpec:
        """Parse a free-text JD into a JobSpec (FR-401)."""
        lines = [line.strip() for line in source.splitlines()]
        title = self._extract_title(lines)
        sections = self._extract_sections(lines)

        required = self._extract_required_skills(sections.get("required", []))
        preferred = self._extract_preferred_skills(sections.get("preferred", []))
        # Experience, education, domain and certifications may appear either
        # under an explicit heading or as a trailing sentence in the JD text.
        experience = self._extract_experience(
            _section_or_full(source, sections.get("experience", []))
        )
        education = self._extract_education(_section_or_full(source, sections.get("education", [])))
        certifications = self._extract_certifications(
            _section_or_full(source, sections.get("certifications", []))
        )
        domain = self._extract_domain(_section_or_full(source, sections.get("domain", [])))
        knockouts = self._extract_knockouts(sections.get("knockouts", []))
        responsibilities = self._extract_responsibilities(sections.get("responsibilities", []))
        proxy_warnings = self._detect_proxy_language(source)

        job_id = self._slugify(title) if title else "unnamed"

        return JobSpec(
            job_id=job_id,
            title=title,
            target_seniority=self._infer_seniority(title),
            required_skills=tuple(required),
            preferred_skills=tuple(preferred),
            experience=experience,
            education=education,
            certifications=tuple(certifications),
            domain=domain,
            knockouts=tuple(knockouts),
            responsibility_chunks=tuple(responsibilities),
            compiled_by=self._compiled_by,
            warnings=tuple(proxy_warnings),
        )

    def _extract_title(self, lines: list[str]) -> str:
        """Return the first non-empty line as the title."""
        for line in lines:
            if line:
                return line.strip("#:- ")
        return ""

    def _infer_seniority(self, title: str) -> str | None:
        """Infer target seniority from title words (TRD §4.2)."""
        lower = title.lower()
        if "senior" in lower:
            return "senior"
        if "junior" in lower or "entry" in lower:
            return "junior"
        if "lead" in lower or "principal" in lower or "staff" in lower:
            return "lead"
        return None

    def _slugify(self, text: str) -> str:
        """Turn a title into a deterministic job id."""
        slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
        return slug or "unnamed"

    def _extract_sections(self, lines: list[str]) -> dict[str, list[str]]:
        """Split a JD into labelled sections by heading lines.

        Skill sections only collect bullet items; trailing prose such as
        ``Minimum 6 years of experience.`` is ignored there and picked up
        by the full-text extractors instead.
        """
        sections: dict[str, list[str]] = {}
        current_key: str | None = None
        for line in lines:
            if not line:
                continue
            heading = self._canonical_heading(line)
            if heading is not None:
                if heading == self._TERMINATE:
                    current_key = None
                    continue
                current_key = heading
                sections.setdefault(current_key, [])
                continue
            if current_key is None:
                continue
            # Required and preferred sections may contain either bullet items or
            # prose paragraphs (common in free-text JDs); collect both.
            sections[current_key].append(line)
        return sections

    def _canonical_heading(self, line: str) -> str | None:
        """Return a canonical section key if *line* is a section heading."""
        text = line.rstrip(":").strip()
        # Drop parenthetical annotations such as "(Minimum Qualifications)" so
        # prose JDs like Zscaler's are matched.
        text = re.sub(r"\s*\([^)]+\)", " ", text).strip()
        text = text.lower().replace("’", "'")
        # Strip trailing plural forms used as headings.
        text = re.sub(r"\s+(skills|requirements|criteria)$", "", text)
        # Qualification headings are ambiguous: the prefix decides whether they
        # are required or preferred, and "qualifications" alone maps to education.
        if text.endswith("minimum qualifications"):
            return "required"
        if text.endswith("preferred qualifications"):
            return "preferred"
        # Job-board metadata tags (e.g., #LI-Hybrid) and common JD footer phrases
        # terminate the current section even if they are not full headings.
        if text.startswith("#li-") or text.startswith("li-"):
            return self._TERMINATE
        if any(phrase in text for phrase in self._TERMINATOR_HEADINGS):
            return self._TERMINATE
        return self._HEADING_MAP.get(text)

    def _extract_required_skills(self, lines: list[str]) -> list[RequiredSkill]:
        """Parse required skills with weights (FR-401, FR-405).

        Handles both bullet items and prose paragraphs by splitting prose into
        candidate phrases and stripping lead-in language.
        """
        skills: list[RequiredSkill] = []
        for line in lines:
            raw = _strip_bullet(line)
            if not raw:
                continue
            for canonical, weight in _skill_candidates(raw, self._weight_phrases):
                skills.append(RequiredSkill(canonical=canonical, weight=weight, knockout=False))
        return skills

    def _extract_preferred_skills(self, lines: list[str]) -> list[PreferredSkill]:
        """Parse preferred skills with a default weight of 2 (FR-401).

        Handles both bullet items and prose paragraphs.
        """
        skills: list[PreferredSkill] = []
        for line in lines:
            raw = _strip_bullet(line)
            if not raw:
                continue
            for canonical, _weight in _skill_candidates(raw, self._weight_phrases):
                skills.append(PreferredSkill(canonical=canonical, weight=2))
        return skills

    def _extract_experience(self, text: str) -> ExperienceRequirement | None:
        """Extract minimum/target years of experience (FR-401)."""
        match = re.search(r"(?i)(?:minimum|min|at least)\s*(\d+)\s*\+?\s*years?", text)
        if not match:
            match = re.search(r"(?i)(\d+)\s*\+?\s*years?\s+(?:of\s+)?experience", text)
        if not match:
            return None

        min_years = int(match.group(1))
        target_match = re.search(r"(?i)(?:target|ideal|ideally|up to)\s*(\d+)\s*\+?\s*years?", text)
        target_years = int(target_match.group(1)) if target_match else min_years + 3
        count_internships = "internship" in text.lower() and (
            "count" in text.lower() or "including" in text.lower()
        )
        return ExperienceRequirement(
            min_years=min_years,
            target_years=target_years,
            count_internships=count_internships,
        )

    def _extract_education(self, text: str) -> EducationRequirement | None:
        """Extract education level, field, and equivalent-experience flag (FR-401)."""
        match = re.search(
            r"(?i)(bachelor'?s?|master'?s?|ph\.?d\.?|doctorate|associate'?s?|high school)"
            r"(?:\s*degree)?",
            text,
        )
        if not match:
            return None

        raw_level = match.group(1).lower().replace(".", "").replace("'", "")
        if raw_level in ("phd", "doctorate"):
            level = "phd"
        elif raw_level in ("master", "masters"):
            level = "masters"
        elif raw_level in ("bachelor", "bachelors"):
            level = "bachelors"
        elif raw_level in ("associate", "associates"):
            level = "associates"
        else:
            level = "high_school"

        # Look for a field phrase only in the immediate vicinity of the degree mention.
        # Handles: "Bachelor's degree in X", "Master's (preferred) degree in X",
        # "Bachelor's or Master's degree in X or equivalent".
        degree_phrase = r"(?:bachelor'?s?|master'?s?|ph\.?d\.?|doctorate|associate'?s?)"
        field_match = re.search(
            r"(?i)(?:"
            + degree_phrase
            + r")(?:\s*degree)?(?:\s+or\s+"
            + degree_phrase
            + r")?(?:\s*degree)?(?:\s*\([^)]+\))?(?:\s*degree)?\s+in\s+"
            + r"([^(,\.]+?)(?=\s+(?:or|and|with|equivalent)|[\.,\)]|$)",
            text,
        )
        fields: tuple[str, ...] = ()
        if field_match:
            field = field_match.group(1).strip()
            if field:
                fields = (field.lower(),)

        equivalent = "equivalent" in text.lower() or "or experience" in text.lower()
        knockout = "degree required" in text.lower() or "must have a degree" in text.lower()
        return EducationRequirement(
            min_level=level,
            fields=fields,
            equivalent_experience_allowed=equivalent,
            knockout=knockout,
        )

    def _extract_certifications(self, text: str) -> list[dict[str, object]]:
        """Extract certification requirements as flexible dicts (FR-401).

        Only lines that explicitly reference a certification, certificate,
        licence, or the word "certified" are treated as certification
        requirements.  This prevents every bullet under a general
        "qualifications" section from being modelled as a certification.
        """
        certs: list[dict[str, object]] = []
        cert_keywords = re.compile(r"(?i)\b(certification|certificate|licence|license|certified)\b")
        for line in text.splitlines():
            raw = _strip_bullet(line)
            if not raw or not cert_keywords.search(raw):
                continue
            cleaned = _clean_skill(raw, self._weight_phrases)
            match = re.search(
                r"(?i)(?:certification|certificate|licence|license|certified)s?\s*(?::|in\s+)?(.+)",
                cleaned,
            )
            name = (match.group(1).strip() if match else cleaned).lower()
            name = re.sub(r"^(?:in|for)\s+", "", name, flags=re.IGNORECASE).strip()
            if name and len(name) > 1:
                certs.append(
                    {
                        "canonical": name,
                        "weight": 2,
                        "required": "required" in raw.lower(),
                    }
                )
        return certs

    def _extract_domain(self, text: str) -> DomainRequirement | None:
        """Extract a domain/industry requirement if present (FR-401)."""
        match = re.search(r"(?i)(?:domain|industry)\s*:\s*([^\n]+)", text)
        if not match:
            return None
        industry = match.group(1).strip().lower()
        required = "required" in text.lower() or "must" in text.lower()
        return DomainRequirement(industry=industry, required=required)

    def _extract_knockouts(self, lines: list[str]) -> list[KnockoutRule]:
        """Parse explicit knockout rules from their own section (FR-401)."""
        rules: list[KnockoutRule] = []
        for line in lines:
            raw = _strip_bullet(line)
            if not raw:
                continue
            rule_id = f"KO_{len(rules):02d}"
            rules.append(KnockoutRule(id=rule_id, rule=raw, evidence_required=True))
        return rules

    def _extract_responsibilities(self, lines: list[str]) -> list[ResponsibilityChunk]:
        """Parse responsibility paragraphs for semantic matching (FR-401)."""
        chunks: list[ResponsibilityChunk] = []
        for idx, line in enumerate(lines, start=1):
            raw = _strip_bullet(line)
            if not raw:
                continue
            chunks.append(ResponsibilityChunk(id=f"r{idx}", text=raw, weight=3))
        return chunks

    def _detect_proxy_language(self, source: str) -> list[str]:
        """Flag protected-proxy language per FR-407."""
        warnings: list[str] = []
        lower = source.lower()
        for phrase in self._PROXY_PHRASES:
            if phrase in lower:
                warnings.append(f"Proxy language detected: '{phrase}'")
        return warnings


def _strip_bullet(line: str) -> str:
    """Remove a leading bullet or number marker from a line."""
    return re.sub(r"^(\s*[-*•]\s+|\s*\d+\.\s+|\s*\(?\d+\)\.?\s*)", "", line).strip()


def _is_bullet(line: str) -> bool:
    """Return True if *line* begins with a recognised bullet or number marker."""
    return bool(re.match(r"^(\s*[-*•]\s+|\s*\d+\.\s+|\s*\(?\d+\)\.?\s*)", line))


def _section_or_full(source: str, section_lines: list[str]) -> str:
    """Return the joined section text if present, otherwise the whole source."""
    if section_lines:
        return "\n".join(section_lines)
    return source


def _infer_weight(line: str, phrases: tuple[tuple[str, int], ...]) -> int:
    """Return the highest-priority weight whose phrase appears in *line*."""
    lower = line.lower()
    for phrase, weight in phrases:
        if phrase in lower:
            return weight
    return 3


def _clean_skill(line: str, phrases: tuple[tuple[str, int], ...]) -> str:
    """Remove weight markers and stray punctuation from a skill line."""
    text = line
    for phrase, _ in phrases:
        text = re.sub(re.escape(phrase), "", text, flags=re.IGNORECASE)
    text = re.sub(r"(?i)\b(must|required|preferred|optional)\b", "", text)
    text = re.sub(r"[:;,\.\-]+$", "", text.strip())
    return text.strip()


_SKILL_LEAD_PHRASES: tuple[str, ...] = (
    "expertise in",
    "proficiency in",
    "proficient in",
    "experience in",
    "experience with",
    "experienced with",
    "knowledge of",
    "understanding of",
    "familiarity with",
    "familiar with",
    "working knowledge of",
    "exposure to",
    "competency in",
    "competent in",
    "skills in",
    "skill in",
    "strong",
    "solid",
    "basic",
    "some",
    "foundational",
    "proven",
    "deep",
    "extensive",
    "hands-on",
)

_SKILL_TRAIL_PHRASES: tuple[str, ...] = (
    "skills",
    "skill",
    "experience",
    "knowledge",
)

_SKILL_STOP_WORDS: frozenset[str] = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "in",
        "on",
        "at",
        "with",
        "of",
        "to",
        "for",
        "as",
        "is",
        "are",
        "such",
        "like",
        "including",
    }
)

_SKILL_NOISE_PHRASES: tuple[str, ...] = (
    "years of",
    "year of",
    "problem-solving",
    "communication",
    "collaboration",
    "leadership",
    "teamwork",
    "excellent",
    "outstanding",
    "proven ability",
    "ability to",
    "designing",
    "developing",
    "optimizing",
    "debugging",
    "leveraging",
    "securing",
    "positioning",
)


def _strip_skill_noise(text: str) -> str:
    """Remove leading and trailing fluff from a skill phrase."""
    lower = text.lower()
    for phrase in _SKILL_LEAD_PHRASES:
        if lower.startswith(phrase + " "):
            text = text[len(phrase) :].strip()
            lower = text.lower()
    for phrase in _SKILL_TRAIL_PHRASES:
        if lower.endswith(" " + phrase):
            text = text[: -len(" " + phrase)].strip()
            lower = text.lower()
    # Remove a trailing parenthetical size or acronym set if it dominates the phrase.
    text = re.sub(r"\s*\([^)]{15,}\)\s*$", "", text).strip()
    # Strip leftover conjunctions/prepositions at the start or end of a split fragment.
    text = re.sub(r"^(?:and|or|in|with|for|of|such|like)\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+(?:and|or|in|with|for|of|such|like)$", "", text, flags=re.IGNORECASE)
    return text.strip()


def _is_valid_skill(text: str) -> bool:
    """Return True if *text* looks like a genuine skill phrase."""
    if not text or len(text) < 2:
        return False
    lower = text.lower()
    # Exclude education, experience-duration and generic soft-skill statements.
    if any(phrase in lower for phrase in _SKILL_NOISE_PHRASES):
        return False
    if re.search(r"\b(degree|bachelor|master|phd|doctorate)\b", lower):
        return False
    if re.search(r"\b\d+\s*\+?\s*years?\b", lower):
        return False
    if "minimum" in lower:
        return False
    # Must contain at least one non-stop word longer than 1 char.
    words = re.findall(r"[a-z0-9/+#-]+", lower)
    content = [w for w in words if w not in _SKILL_STOP_WORDS and len(w) > 1]
    return len(content) >= 1


def _skill_candidates(
    raw: str, weight_phrases: tuple[tuple[str, int], ...]
) -> list[tuple[str, int]]:
    """Split a raw skill line into candidate canonical phrases with weights.

    Bullet lines are returned as a single candidate; prose lines are split on
    commas, semicolons, and coordinating conjunctions.
    """
    weight = _infer_weight(raw, weight_phrases)
    cleaned = _clean_skill(raw, weight_phrases).lower()
    if not cleaned:
        return []
    # Short bullet-like lines without list separators are a single skill.
    if len(cleaned) < 60 and not re.search(r"[,;]|\band\b|\bor\b", cleaned):
        cleaned = _strip_skill_noise(cleaned)
        if _is_valid_skill(cleaned):
            return [(cleaned, weight)]
        return []
    # Split prose into candidate phrases.
    parts = re.split(r"\s*[,;]\s*|\s+\band\b\s+|\s+\bor\b\s+", cleaned)
    result: list[tuple[str, int]] = []
    for part in parts:
        part = _strip_skill_noise(part.strip())
        if _is_valid_skill(part):
            result.append((part, weight))
    return result


def _looks_like_yaml_mapping(text: str) -> bool:
    """Heuristic: does the first non-empty line look like a YAML key?"""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return ":" in stripped and not stripped.startswith(("-", "*"))
    return False


def _fatal(code: str, message: str) -> StageResult[JobSpec]:
    """Build a fatal JobSpec compilation diagnostic.

    JobSpec compilation is the only fatal stage per TRD §2.5.
    """
    return StageResult(
        value=None,
        diagnostics=(Diagnostic(stage="S5", code=code, message=message, fatal=True),),
    )
