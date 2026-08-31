from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence

from pydantic import BaseModel, Field

from resume_ranker.models.config import ScoringConfig
from resume_ranker.models.scoring import ScoreCard, SubScore


class GroupImpact(BaseModel):
    """Adverse-impact statistics for a single demographic group."""

    group: str
    candidates: int
    selected: int
    selection_rate: float
    impact_ratio: float | None
    impact_ratio_ci_95_low: float | None
    impact_ratio_ci_95_high: float | None
    fisher_exact_p_value: float | None
    small_sample_warning: bool
    mean_composite: float | None
    mean_sub_scores: dict[str, float]
    leave_one_out_composite: dict[str, float]


class AdverseImpactReport(BaseModel):
    """Adverse-impact report as specified in TRD §11.3."""

    reference_group: str | None
    threshold: float | None
    groups: tuple[GroupImpact, ...]
    dimensions: tuple[str, ...]
    weights: dict[str, float] = Field(default_factory=dict)


def compute_adverse_impact_report(
    scorecards: Sequence[ScoreCard],
    demographics: Mapping[str, str],
    weights: Mapping[str, float] | None = None,
    threshold: float | None = None,
    reference_group: str | None = None,
) -> AdverseImpactReport:
    """Compute an adverse-impact report from a set of scorecards and a
    demographics mapping.

    *scorecards* are grouped by the demographic value supplied in
    *demographics* (candidate_id -> group).  Selection is taken from
    :attr:`ScoreCard.selected` unless *threshold* is provided, in which case a
    candidate is selected when ``composite >= threshold``.

    The report provides, per group:

    * selection rate and impact ratio (group rate / reference rate)
    * Fisher exact test p-value and a 95 % CI on the impact ratio
    * mean composite and mean of each sub-score
    * leave-one-dimension-out composite means, recomputed from the weights

    Groups with fewer than 30 candidates are flagged with
    ``small_sample_warning``.

    Implements TRD §11.3.
    """
    if weights is None:
        weights = ScoringConfig().weights

    # Build per-group scorecard lists.
    grouped: dict[str, list[ScoreCard]] = defaultdict(list)
    for card in scorecards:
        group = demographics.get(card.candidate_id)
        if group is None:
            continue
        grouped[group].append(card)

    groups = sorted(grouped.keys())
    if not groups:
        return AdverseImpactReport(
            reference_group=None,
            threshold=threshold,
            groups=(),
            dimensions=(),
            weights=dict(weights),
        )

    # Determine selection for each card.
    selected: dict[str, set[str]] = defaultdict(set)
    for group, cards in grouped.items():
        for card in cards:
            if _is_selected(card, threshold):
                selected[group].add(card.candidate_id)

    rates = {g: _selection_rate(len(selected[g]), len(grouped[g])) for g in groups}

    # Reference group is the group with the highest selection rate, or the
    # supplied reference group.
    ref = reference_group or max(rates, key=lambda group: rates[group])
    ref_rate = rates[ref]
    ref_cards = grouped[ref]
    ref_selected = selected[ref]

    # Collect all dimensions that appear in any scorecard.
    all_dimensions = sorted(
        {dim for cards in grouped.values() for card in cards for dim in card.sub_scores}
    )

    group_impacts: list[GroupImpact] = []
    for group in groups:
        cards = grouped[group]
        n = len(cards)
        s = len(selected[group])
        rate = rates[group]
        impact = _impact_ratio(rate, ref_rate)
        ci_low, ci_high = _impact_ratio_ci(s, n, len(ref_selected), len(ref_cards))
        p_value = _fisher_exact_p_value(
            s, n - s, len(ref_selected), len(ref_cards) - len(ref_selected)
        )

        composites = [c.composite for c in cards if c.composite is not None]
        mean_composite = _mean(composites)

        mean_sub_scores: dict[str, float] = {}
        for dim in all_dimensions:
            values = [
                c.sub_scores[dim].value
                for c in cards
                if dim in c.sub_scores and c.sub_scores[dim].value is not None
            ]
            if values:
                mean_sub_scores[dim] = _mean(values)

        leave_one_out: dict[str, float] = {}
        for dim in all_dimensions:
            values = [_composite_without_dimension(c.sub_scores, weights, dim) for c in cards]
            leave_one_out[dim] = _mean(values)

        group_impacts.append(
            GroupImpact(
                group=group,
                candidates=n,
                selected=s,
                selection_rate=rate,
                impact_ratio=impact,
                impact_ratio_ci_95_low=ci_low,
                impact_ratio_ci_95_high=ci_high,
                fisher_exact_p_value=p_value,
                small_sample_warning=n < 30,
                mean_composite=mean_composite,
                mean_sub_scores=mean_sub_scores,
                leave_one_out_composite=leave_one_out,
            )
        )

    return AdverseImpactReport(
        reference_group=ref,
        threshold=threshold,
        groups=tuple(group_impacts),
        dimensions=tuple(all_dimensions),
        weights=dict(weights),
    )


def _is_selected(card: ScoreCard, threshold: float | None) -> bool:
    """Return True if *card* is selected."""
    return bool(
        card.selected
        or (threshold is not None and card.composite is not None and card.composite >= threshold)
    )


def _selection_rate(selected: int, total: int) -> float:
    """selection_rate(g) = selected(g) / candidates(g)."""
    if total == 0:
        return 0.0
    return selected / total


def _impact_ratio(group_rate: float, reference_rate: float) -> float | None:
    """impact_ratio(g) = selection_rate(g) / selection_rate(reference group)."""
    if reference_rate <= 0:
        return None
    return group_rate / reference_rate


def _impact_ratio_ci(
    selected_group: int,
    total_group: int,
    selected_ref: int,
    total_ref: int,
) -> tuple[float | None, float | None]:
    """Approximate 95 % confidence interval for the impact ratio.

    Uses the delta method on log(impact_ratio).  If the reference group has no
    selections the interval is unbounded.  To avoid degenerate log values when a
    cell is zero, a Haldane-Anscombe correction of 0.5 is added to all four cells
    before the delta method is applied.  This is a conservative approximation
    suitable for a monitoring report; legal review may require a more exact
    interval.
    """
    if total_group == 0 or total_ref == 0 or selected_ref == 0:
        return (None, None)

    # Apply a small correction if any cell is zero so the log interval stays finite.
    sg = float(selected_group)
    tg = float(total_group)
    sr = float(selected_ref)
    tr = float(total_ref)

    if (
        selected_group == 0
        or selected_group == total_group
        or selected_ref == 0
        or selected_ref == total_ref
    ):
        sg += 0.5
        tg += 1.0
        sr += 0.5
        tr += 1.0

    p1 = sg / tg
    p2 = sr / tr

    ratio = p1 / p2
    se_log = math.sqrt((1 - p1) / (tg * p1) + (1 - p2) / (tr * p2))
    log_low = math.log(ratio) - 1.96 * se_log
    log_high = math.log(ratio) + 1.96 * se_log
    # Clamp to the finite double range to guard against pathological inputs.
    return (math.exp(max(log_low, -700.0)), math.exp(min(log_high, 700.0)))


def _fisher_exact_p_value(a: int, b: int, c: int, d: int) -> float | None:
    """Two-sided Fisher exact p-value for a 2x2 table.

    Table layout::

                selected   not_selected
        group       a          b
        reference   c          d

    The p-value is the sum of probabilities of all tables with probability
    less than or equal to the observed table.  Returns None if either row or
    column margin is zero.
    """
    if a < 0 or b < 0 or c < 0 or d < 0:
        return None
    if a + b == 0 or c + d == 0:
        return None
    if a + c == 0 or b + d == 0:
        # All candidates are selected or all are not selected: no variation to test.
        return 1.0

    row1 = a + b
    row2 = c + d
    col1 = a + c
    total = a + b + c + d

    observed = _hypergeometric_probability(a, row1, row2, col1, total)
    if observed is None:
        return None

    p_value = 0.0
    # All possible values for the top-left cell.
    lo = max(0, col1 - row2)
    hi = min(row1, col1)
    for x in range(lo, hi + 1):
        prob = _hypergeometric_probability(x, row1, row2, col1, total)
        if prob is not None and prob <= observed + 1e-15:
            p_value += prob

    return p_value


def _hypergeometric_probability(
    x: int, row1: int, row2: int, col1: int, total: int
) -> float | None:
    """Probability of a 2x2 table with given margins and top-left cell *x*."""
    col2 = row1 - x
    row2_x = col1 - x
    bottom_right = row2 - row2_x
    if col2 < 0 or row2_x < 0 or bottom_right < 0 or bottom_right > row2:
        return None

    try:
        numerator = math.comb(row1, x) * math.comb(row2, row2_x)
        denominator = math.comb(total, col1)
        return numerator / denominator
    except (ValueError, OverflowError):
        return None


def _mean(values: Sequence[float | None]) -> float:
    """Arithmetic mean of a non-empty sequence of floats, ignoring None."""
    present = [v for v in values if v is not None]
    if not present:
        return 0.0
    return sum(present) / len(present)


def _composite_without_dimension(
    sub_scores: Mapping[str, SubScore],
    weights: Mapping[str, float],
    drop_dim: str,
) -> float:
    """Compute a weighted composite score excluding *drop_dim*.

    Dimensions whose SubScore is missing or has value None are treated as
    unavailable and their weights are redistributed, mirroring the aggregation
    rule from TRD §5.4.
    """
    weighted = 0.0
    total = 0.0
    for dim, weight in weights.items():
        if dim == drop_dim:
            continue
        sub = sub_scores.get(dim)
        if sub is None or sub.value is None:
            continue
        if weight <= 0:
            continue
        weighted += weight * sub.value
        total += weight
    if total == 0:
        return 0.0
    return weighted / total
