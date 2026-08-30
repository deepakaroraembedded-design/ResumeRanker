from __future__ import annotations

import asyncio
import concurrent.futures
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Any, Protocol, cast

from ats_scan.models.config import ProficiencyFactors, RecencyFactors, ScoringConfig
from ats_scan.models.embeddings import Vector
from ats_scan.models.jobspec import PreferredSkill, RequiredSkill
from ats_scan.models.resume import (
    Bullet,
    CanonicalResume,
    DateValue,
    SkillMention,
)
from ats_scan.models.scoring import Evidence, GapDetail, MatchDetail, MatchRoute
from ats_scan.protocols import EmbeddingClient, OntologyIndex

# Semantic skill-matching thresholds.  These are module constants because the
# frozen ScoringConfig model does not expose knobs for this enhancement.
_SEMANTIC_MATCH_THRESHOLD: float = 0.55
_SEMANTIC_MATCH_MAX_FACTOR: float = 0.55
_SEMANTIC_MIN_TARGET_LENGTH: int = 10
_SEMANTIC_STOP_WORDS: frozenset[str] = frozenset(
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


# Keyword skill-matching thresholds.  Used when the ontology cascade misses a
# target that appears in the resume's own skill list (e.g., acronyms and phrases
# not yet in the ontology data).
_KEYWORD_STOP_WORDS: frozenset[str] = frozenset(
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


class ProficiencyKind(StrEnum):
    """Evidence type for the f_prof table in TRD §5.3.1."""

    APPLIED_LONG = "applied_long"
    APPLIED_SHORT = "applied_short"
    LISTED_CORROBORATED = "listed_corroborated"
    LISTED_ONLY = "listed_only"
    INCIDENTAL = "incidental"


class _HasSkillEvidence(Protocol):
    """Common shape of experience and project entries for skill harvesting."""

    skills_evidenced: tuple[str, ...]
    bullets: tuple[Bullet, ...]
    span: tuple[int, int] | None
    end: DateValue | None


@dataclass(frozen=True)
class SkillEvidence:
    """Internal record of one piece of skill evidence.

    This is not a model type; it is an intermediate value used by the
    evidence dimensions S1, S2 and S8.
    """

    raw: str
    canonical: str | None
    route: MatchRoute
    span: tuple[int, int]
    quote: str
    kind: ProficiencyKind
    last_used: date | None
    cosine: float | None = None  # only used for EMBEDDING semantic matches


def parse_iso_date(value: str | None) -> date | None:
    """Parse a partial ISO-8601 date string into a date.

    Supports ``YYYY-MM-DD``, ``YYYY-MM`` (first of month) and ``YYYY``
    (first of year).  Returns ``None`` for missing or unparseable input.
    """
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        pass
    for fmt in ("%Y-%m", "%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def years_since(last: date, now: date) -> float:
    """Return the elapsed time in years, using month-level precision.

    Month-level precision avoids penalising a candidate whose most recent
    evidence is from the same calendar month as the scoring date.
    """
    if last > now:
        return 0.0
    months = (now.year - last.year) * 12 + (now.month - last.month)
    return max(0.0, months / 12.0)


def f_match(route: MatchRoute, cosine: float | None = None) -> float:
    """Return the match factor for a skill route (TRD §5.3.1).

    The deterministic cascade produces ``EXACT``, ``ALIAS``, ``CASE``,
    ``CHILD``, ``PARENT``, ``FUZZY`` or ``EMBEDDING``.  ``TRANSFERABLE`` is
    only used after LLM adjudication.  ``NONE`` yields zero.
    """
    if route in (MatchRoute.EXACT, MatchRoute.ALIAS, MatchRoute.CASE):
        return 1.0
    if route == MatchRoute.CHILD:
        return 0.90
    if route == MatchRoute.PARENT:
        return 0.70
    if route == MatchRoute.FUZZY:
        return 0.85
    if route == MatchRoute.EMBEDDING:
        if cosine is None:
            return 0.0
        return min(0.85, 0.60 + 0.75 * (cosine - 0.82))
    if route == MatchRoute.TRANSFERABLE:
        return 0.50
    return 0.0


def f_prof(kind: ProficiencyKind, factors: ProficiencyFactors) -> float:
    """Return the proficiency factor for an evidence kind (TRD §5.3.1)."""
    if kind == ProficiencyKind.APPLIED_LONG:
        return factors.applied_long
    if kind == ProficiencyKind.APPLIED_SHORT:
        return factors.applied_short
    if kind == ProficiencyKind.LISTED_CORROBORATED:
        return factors.listed_corroborated
    if kind == ProficiencyKind.LISTED_ONLY:
        return factors.listed_only
    return factors.incidental


def f_recency(years_since: float, half_life_years: float, floor: float) -> float:
    """Return the recency factor, clamped at the configured floor (TRD §5.3.1).

    ``f_recency = clamp( exp( -ln(2) * dt / H ), r_min, 1.0 )``.
    """
    if half_life_years <= 0:
        return 1.0
    factor = math.exp(-math.log(2) * years_since / half_life_years)
    return max(floor, min(1.0, factor))


def _route_for(target: str, candidate: str | None, ontology: OntologyIndex) -> MatchRoute:
    """Map a candidate canonical skill to the target relation."""
    if candidate is None:
        return MatchRoute.NONE
    if candidate.lower().strip() == target.lower().strip():
        return MatchRoute.EXACT
    relation = ontology.relation(candidate, target)
    try:
        return MatchRoute(relation.value)
    except ValueError:
        return MatchRoute.NONE


def _proficiency_from_mention(skill: SkillMention) -> ProficiencyKind:
    """Classify a SkillMention into the f_prof table."""
    sections = {s.lower() for s in skill.sections}
    if "experience" in sections and "skills" in sections:
        return ProficiencyKind.LISTED_CORROBORATED
    if "experience" in sections:
        return (
            ProficiencyKind.LISTED_CORROBORATED
            if skill.mentions > 0
            else ProficiencyKind.INCIDENTAL
        )
    return ProficiencyKind.LISTED_ONLY


def _evidence_from_mention(
    target: str, skill: SkillMention, ontology: OntologyIndex
) -> SkillEvidence | None:
    """Turn a SkillMention into evidence if it matches the target skill."""
    canonical = skill.canonical
    if canonical is None:
        match = ontology.canonicalise(skill.raw)
        if match is None:
            return None
        canonical = match.canonical

    route = _route_for(target, canonical, ontology)
    if route == MatchRoute.NONE:
        return None

    span = skill.evidence_spans[0] if skill.evidence_spans else (0, len(skill.raw))
    return SkillEvidence(
        raw=skill.raw,
        canonical=canonical,
        route=route,
        span=span,
        quote=skill.raw,
        kind=_proficiency_from_mention(skill),
        last_used=parse_iso_date(skill.last_used),
    )


def _evidence_from_entry(
    target: str,
    entry: _HasSkillEvidence,
    raw_skill: str,
    ontology: OntologyIndex,
) -> SkillEvidence | None:
    """Turn a skill listed in an experience/project entry into evidence."""
    match = ontology.canonicalise(raw_skill)
    if match is None:
        return None
    canonical = match.canonical

    route = _route_for(target, canonical, ontology)
    if route == MatchRoute.NONE:
        return None

    span = entry.span
    quote = raw_skill
    if entry.bullets and span is None:
        bullet = entry.bullets[0]
        span = bullet.span or (0, len(bullet.text))
        quote = bullet.text
    if span is None:
        span = (0, len(quote))

    last_used: date | None = None
    if entry.end is not None and entry.end.value is not None:
        last_used = parse_iso_date(entry.end.value)

    return SkillEvidence(
        raw=raw_skill,
        canonical=canonical,
        route=route,
        span=span,
        quote=quote,
        kind=ProficiencyKind.LISTED_CORROBORATED,
        last_used=last_used,
    )


def _run_embed_sync(client: EmbeddingClient, texts: Sequence[str]) -> Sequence[Vector]:
    """Run an async embedding call from a synchronous scoring context."""
    coro = client.embed(texts)
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coro).result()


def _cosine(a: Vector, b: Vector) -> float:
    """Cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _has_semantic_overlap(a: str, b: str) -> bool:
    """Return True if two skill phrases share a meaningful token or stem."""
    a_words = set(re.findall(r"[a-z0-9]+", a.lower())) - _SEMANTIC_STOP_WORDS
    b_words = set(re.findall(r"[a-z0-9]+", b.lower())) - _SEMANTIC_STOP_WORDS
    if a_words & b_words:
        return True
    for aw in a_words:
        for bw in b_words:
            if len(aw) >= 4 and (aw in bw or bw in aw):
                return True
    return False


def _semantic_skill_evidence(
    resume: CanonicalResume, target: str, ctx: Any
) -> tuple[SkillEvidence, ...]:
    """Embeddings-based semantic fallback for skill coverage (S1/S2/S8).

    Only used when the deterministic ontology cascade finds no evidence. It
    compares the target skill phrase to raw skill mentions in the resume and
    returns partial-credit EMBEDDING evidence when cosine similarity and a
    token overlap are both high enough.
    """
    embeddings = getattr(ctx, "embeddings", None)
    if embeddings is None:
        return ()
    try:
        client = cast(EmbeddingClient, embeddings)
    except Exception:
        return ()

    # Avoid semantic-matching short, ambiguous terms such as "Go", "AWS", "C".
    if " " not in target and len(target) < _SEMANTIC_MIN_TARGET_LENGTH:
        return ()

    # Collect all raw skill mentions with their provenance.
    candidates: list[tuple[str, tuple[int, int], str, ProficiencyKind, date | None]] = []
    for skill in resume.skills:
        raw = skill.raw or skill.canonical or ""
        if not raw:
            continue
        span = skill.evidence_spans[0] if skill.evidence_spans else (0, len(raw))
        candidates.append((raw, span, raw, _proficiency_from_mention(skill), None))

    for entry in resume.experience:
        for raw in entry.skills_evidenced:
            if not raw:
                continue
            entry_span = entry.span
            quote = raw
            if entry.bullets and entry_span is None:
                bullet = entry.bullets[0]
                entry_span = bullet.span or (0, len(bullet.text))
                quote = bullet.text
            if entry_span is None:
                entry_span = (0, len(quote))
            last_used: date | None = None
            if entry.end is not None and entry.end.value is not None:
                last_used = parse_iso_date(entry.end.value)
            candidates.append(
                (raw, entry_span, quote, ProficiencyKind.LISTED_CORROBORATED, last_used)
            )

    for project in resume.projects:
        for raw in project.skills_evidenced:
            if not raw:
                continue
            project_span = project.span
            quote = raw
            if project.bullets and project_span is None:
                bullet = project.bullets[0]
                project_span = bullet.span or (0, len(bullet.text))
                quote = bullet.text
            if project_span is None:
                project_span = (0, len(quote))
            last_used = None
            if project.end is not None and project.end.value is not None:
                last_used = parse_iso_date(project.end.value)
            candidates.append(
                (raw, project_span, quote, ProficiencyKind.LISTED_CORROBORATED, last_used)
            )

    if not candidates:
        return ()

    unique_texts = list({c[0] for c in candidates})
    try:
        vectors = _run_embed_sync(client, unique_texts)
    except Exception:
        return ()
    vector_map = dict(zip(unique_texts, vectors, strict=True))

    try:
        target_vec = _run_embed_sync(client, [target])[0]
    except Exception:
        return ()

    found: list[SkillEvidence] = []
    for raw, span, quote, kind, last_used in candidates:
        cosine = _cosine(target_vec, vector_map[raw])
        if cosine < _SEMANTIC_MATCH_THRESHOLD:
            continue
        if not _has_semantic_overlap(target, raw):
            continue
        factor = min(_SEMANTIC_MATCH_MAX_FACTOR, f_match(MatchRoute.EMBEDDING, cosine))
        if factor <= 0.0:
            continue
        found.append(
            SkillEvidence(
                raw=raw,
                canonical=None,
                route=MatchRoute.EMBEDDING,
                span=span,
                quote=quote,
                kind=kind,
                last_used=last_used,
                cosine=cosine,
            )
        )
    return tuple(found)


def _keyword_match_score(target: str, candidate: str) -> float | None:
    """Score a keyword match between a JD target and a resume skill phrase.

    Returns a coarse score used only to pick the route: 1.0 = exact match,
    0.85 = substring, 0.55 = token overlap.  None means no credible match.
    """
    target_norm = re.sub(r"[^a-z0-9+#]", "", target.lower())
    cand_norm = re.sub(r"[^a-z0-9+#]", "", candidate.lower())
    if not target_norm or not cand_norm:
        return None
    if target_norm == cand_norm:
        return 1.0
    # Substring matches only for meaningful phrases (>= 4 chars) to avoid single
    # letters like "C" or short targets like "Go" matching unrelated words.
    if (
        len(target_norm) >= 4
        and len(cand_norm) >= 4
        and (target_norm in cand_norm or cand_norm in target_norm)
    ):
        return 0.85
    target_tokens = set(re.findall(r"[a-z0-9]+", target.lower())) - _KEYWORD_STOP_WORDS
    cand_tokens = set(re.findall(r"[a-z0-9]+", candidate.lower())) - _KEYWORD_STOP_WORDS
    if not target_tokens:
        return None
    overlap = len(target_tokens & cand_tokens) / len(target_tokens)
    # Short acronyms (e.g. "ai/ml", "ipsec") must match all tokens to avoid
    # matching unrelated phrases that share only one token (e.g. "ai" in
    # "AI governance"). Longer phrases tolerate a single missing token.
    if len(target_tokens) <= 2:
        threshold = 1.0
    elif len(target_tokens) == 3:
        threshold = 2.0 / 3.0
    else:
        threshold = 0.75
    if overlap >= threshold:
        return 0.55
    return None


def _keyword_skill_evidence(resume: CanonicalResume, target: str) -> tuple[SkillEvidence, ...]:
    """Keyword fallback for skill coverage.

    When the ontology cascade misses a target, this scans the structured skill
    phrases already extracted from the resume and awards partial credit for
    exact, substring or token-overlap matches.
    """
    found: list[SkillEvidence] = []
    seen: set[str] = set()

    for skill in resume.skills:
        raw = skill.raw
        score = _keyword_match_score(target, raw)
        if score is None or raw in seen:
            continue
        seen.add(raw)
        route = MatchRoute.EXACT if score >= 1.0 else MatchRoute.FUZZY
        span = skill.evidence_spans[0] if skill.evidence_spans else (0, len(raw))
        found.append(
            SkillEvidence(
                raw=raw,
                canonical=skill.canonical,
                route=route,
                span=span,
                quote=raw,
                kind=_proficiency_from_mention(skill),
                last_used=parse_iso_date(skill.last_used),
            )
        )

    for entry in resume.experience:
        for raw in entry.skills_evidenced:
            score = _keyword_match_score(target, raw)
            if score is None or raw in seen:
                continue
            seen.add(raw)
            route = MatchRoute.EXACT if score >= 1.0 else MatchRoute.FUZZY
            span = entry.span or (0, len(raw))
            last_used: date | None = None
            if entry.end is not None and entry.end.value is not None:
                last_used = parse_iso_date(entry.end.value)
            found.append(
                SkillEvidence(
                    raw=raw,
                    canonical=None,
                    route=route,
                    span=span,
                    quote=raw,
                    kind=ProficiencyKind.LISTED_CORROBORATED,
                    last_used=last_used,
                )
            )

    for project in resume.projects:
        for raw in project.skills_evidenced:
            score = _keyword_match_score(target, raw)
            if score is None or raw in seen:
                continue
            seen.add(raw)
            route = MatchRoute.EXACT if score >= 1.0 else MatchRoute.FUZZY
            span = project.span or (0, len(raw))
            last_used = None
            if project.end is not None and project.end.value is not None:
                last_used = parse_iso_date(project.end.value)
            found.append(
                SkillEvidence(
                    raw=raw,
                    canonical=None,
                    route=route,
                    span=span,
                    quote=raw,
                    kind=ProficiencyKind.LISTED_CORROBORATED,
                    last_used=last_used,
                )
            )

    return tuple(found)


def collect_skill_evidence(
    resume: CanonicalResume, target: str, ontology: OntologyIndex, ctx: Any | None = None
) -> tuple[SkillEvidence, ...]:
    """Gather all evidence that could support a required/preferred skill.

    Sources are the deterministic ontology cascade, the structured ``skills``
    list, the ``skills_evidenced`` tuples on experience and project entries, and
    (if no evidence is found) keyword and semantic fallbacks for partial credit.
    """
    found: list[SkillEvidence] = []
    for skill in resume.skills:
        ev = _evidence_from_mention(target, skill, ontology)
        if ev is not None:
            found.append(ev)
    for exp in resume.experience:
        for raw_skill in exp.skills_evidenced:
            ev = _evidence_from_entry(target, exp, raw_skill, ontology)
            if ev is not None:
                found.append(ev)
    for project in resume.projects:
        for raw_skill in project.skills_evidenced:
            ev = _evidence_from_entry(target, project, raw_skill, ontology)
            if ev is not None:
                found.append(ev)
    found.extend(_keyword_skill_evidence(resume, target))
    if not found and ctx is not None:
        found.extend(_semantic_skill_evidence(resume, target, ctx))
    return tuple(found)


def _best_match_value(
    evidence: tuple[SkillEvidence, ...],
    now: date | None,
    config: ScoringConfig,
    ontology: OntologyIndex,
) -> tuple[float, SkillEvidence | None]:
    """Return the best ``m = f_match * f_prof * f_recency`` and the evidence that produced it."""
    best_m = 0.0
    best_ev: SkillEvidence | None = None
    for ev in evidence:
        half_life = (
            config.recency.half_life_timeless_years
            if ev.canonical and ontology.is_timeless(ev.canonical)
            else config.recency.half_life_years
        )
        last_date = ev.last_used or now
        dt = years_since(last_date, now) if now and last_date else 0.0
        rec = f_recency(dt, half_life, config.recency.floor)
        prof = f_prof(ev.kind, config.factors)
        match_factor = f_match(ev.route, ev.cosine)
        m = match_factor * prof * rec
        if m > best_m:
            best_m = m
            best_ev = ev
    return best_m, best_ev


def _to_evidence(ev: SkillEvidence | None) -> tuple[Evidence, ...]:
    """Convert the best internal evidence into the public Evidence type."""
    if ev is None:
        return ()
    return (Evidence(span=ev.span, quote=ev.quote, page=None, source="resume"),)


def score_skill_coverage(
    resume: CanonicalResume,
    skills: tuple[RequiredSkill | PreferredSkill, ...],
    ctx: Any,
) -> tuple[float, tuple[Evidence, ...], tuple[MatchDetail, ...], tuple[GapDetail, ...]]:
    """Score a weighted list of skills (S1 or S2).

    ``m_i = max over evidence of f_match * f_prof * f_recency``.
    The score is the weighted mean over skills that have at least one
    evidence match; unmatched skills contribute a gap entry and their weight
    is excluded from the denominator (TRD §5.3.1 worked example).
    """
    ontology = cast(OntologyIndex, ctx.ontology)
    now = parse_iso_date(ctx.now)
    config = cast(ScoringConfig, ctx.config)

    evidence_out: list[Evidence] = []
    match_details: list[MatchDetail] = []
    gap_details: list[GapDetail] = []
    weighted_sum = 0.0
    weight_sum = 0.0

    for skill in skills:
        target = skill.canonical
        evidence = collect_skill_evidence(resume, target, ontology, ctx)
        if not evidence:
            gap_details.append(
                GapDetail(
                    criterion=target,
                    weight=skill.weight,
                    match=0.0,
                    searched=(target,),
                    note="no evidence found",
                )
            )
            continue

        best_m, best_ev = _best_match_value(evidence, now, config, ontology)
        weighted_sum += skill.weight * best_m
        weight_sum += skill.weight

        evidence_out.extend(_to_evidence(best_ev))
        match_details.append(
            MatchDetail(
                criterion=target,
                weight=skill.weight,
                match=best_m,
                route=best_ev.route if best_ev else None,
                evidence=_to_evidence(best_ev),
            )
        )

    if weight_sum == 0:
        return 0.0, (), (), tuple(gap_details)
    score = 100.0 * weighted_sum / weight_sum
    return score, tuple(evidence_out), tuple(match_details), tuple(gap_details)


def recency_for_skill(
    resume: CanonicalResume,
    target: str,
    now: date | None,
    config: RecencyFactors,
    ontology: OntologyIndex,
    ctx: Any | None = None,
) -> tuple[float, SkillEvidence | None]:
    """Best recency factor for a single skill (used by S8)."""
    evidence = collect_skill_evidence(resume, target, ontology, ctx)
    best_rec = 0.0
    best_ev: SkillEvidence | None = None
    for ev in evidence:
        half_life = (
            config.half_life_timeless_years
            if ev.canonical and ontology.is_timeless(ev.canonical)
            else config.half_life_years
        )
        last_date = ev.last_used or now
        dt = years_since(last_date, now) if now and last_date else 0.0
        rec = f_recency(dt, half_life, config.floor)
        if rec > best_rec:
            best_rec = rec
            best_ev = ev
    return best_rec, best_ev
