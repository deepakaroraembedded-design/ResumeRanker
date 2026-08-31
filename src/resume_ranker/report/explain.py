from __future__ import annotations

from resume_ranker.models.scoring import ScoreCard


def format_explanation_text(scorecard: ScoreCard) -> str:
    """Return the candidate explanation text, capped at 120 words.

    TRD §6.1 / FR-906: G-EXPL produces a natural-language explanation of at most
    120 words. The report modules only render the already-produced text; this
    helper enforces the cap for deterministic/templated fallbacks.
    """
    text = scorecard.explanation or "No explanation available."
    words = text.split()
    if len(words) <= 120:
        return text
    return " ".join(words[:120]) + "..."


def format_score_derivation(scorecard: ScoreCard) -> str:
    """Return a multi-line text summary of a ScoreCard for the ``explain`` command."""
    lines: list[str] = [
        f"Candidate: {scorecard.candidate_id}",
        f"Composite: {scorecard.composite:.2f}"
        if scorecard.composite is not None
        else "Composite: n/a",
        f"Band: {scorecard.band.value if scorecard.band else 'n/a'}",
        f"Rank: {scorecard.rank}" if scorecard.rank is not None else "Rank: n/a",
        f"Selected: {scorecard.selected}",
        f"Eligible: {scorecard.eligible}",
        f"Confidence: {scorecard.confidence:.4f}"
        if scorecard.confidence is not None
        else "Confidence: n/a",
        "Sub-scores:",
    ]
    for dimension in (f"S{i}" for i in range(1, 11)):
        sub = scorecard.sub_scores.get(dimension)
        value = sub.value if sub is not None else None
        lines.append(f"  {dimension}: {value:.2f}" if value is not None else f"  {dimension}: n/a")

    lines.append("Matches:")
    for match in scorecard.matched:
        lines.append(f"  - {match.criterion}")

    lines.append("Gaps:")
    for gap in scorecard.gaps:
        lines.append(f"  - {gap.criterion}")

    if scorecard.flags:
        lines.append(f"Flags: {', '.join(scorecard.flags)}")
    if scorecard.reason_codes:
        lines.append(f"Reason codes: {', '.join(scorecard.reason_codes)}")

    lines.append("")
    lines.append(format_explanation_text(scorecard))
    return "\n".join(lines)
