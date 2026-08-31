from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from jinja2 import Template

from resume_ranker.models.common import StageResult
from resume_ranker.models.run import RunResult
from resume_ranker.models.scoring import ScoreCard
from resume_ranker.protocols import ReportWriter
from resume_ranker.report._helpers import (
    DECISION_SUPPORT_BANNER,
    _candidate_name,
    format_score,
    sub_score_value,
)

_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>RESUME-RANKER Report</title>
<style>
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 2rem; background: #f5f7fa; color: #222; }
.banner { background: #fff3cd; border: 1px solid #ffc107; border-radius: 6px; padding: 1rem; margin-bottom: 1.5rem; font-weight: 600; }
.review-queue { background: #f8d7da; border: 1px solid #dc3545; border-radius: 6px; padding: 1rem; margin-bottom: 1.5rem; }
.card { background: #fff; border: 1px solid #dee2e6; border-radius: 8px; padding: 1.25rem; margin-bottom: 1rem; }
.card-header { display: flex; justify-content: space-between; align-items: baseline; border-bottom: 1px solid #e9ecef; padding-bottom: 0.75rem; margin-bottom: 0.75rem; }
.rank { font-size: 1.5rem; font-weight: 700; color: #495057; }
.score { font-size: 1.5rem; font-weight: 700; }
.band { font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; padding: 0.2rem 0.5rem; border-radius: 4px; font-weight: 600; }
.band-strong { background: #d4edda; color: #155724; }
.band-good { background: #d1ecf1; color: #0c5460; }
.band-borderline { background: #fff3cd; color: #856404; }
.band-weak { background: #f8d7da; color: #721c24; }
.band-not_a_match { background: #e2e3e5; color: #383d41; }
.sub-scores { margin: 1rem 0; }
.sub-score { display: flex; align-items: center; margin-bottom: 0.4rem; }
.sub-score-label { width: 2.5rem; font-weight: 600; }
.sub-score-bar-bg { flex: 1; height: 1.25rem; background: #e9ecef; border-radius: 4px; overflow: hidden; margin: 0 0.75rem; }
.sub-score-bar { height: 100%; background: #0d6efd; border-radius: 4px; }
.sub-score-value { width: 3.5rem; text-align: right; font-variant-numeric: tabular-nums; }
.evidence { background: #f8f9fa; border-left: 3px solid #0d6efd; padding: 0.5rem 0.75rem; margin: 0.5rem 0; }
.gap { background: #fff3cd; border-left: 3px solid #ffc107; padding: 0.5rem 0.75rem; margin: 0.5rem 0; }
.flag { display: inline-block; background: #f8d7da; color: #721c24; padding: 0.15rem 0.4rem; border-radius: 4px; font-size: 0.8rem; margin-right: 0.4rem; }
.pool-context { background: #fff; border: 1px solid #dee2e6; border-radius: 8px; padding: 1.25rem; margin-top: 1.5rem; }
.histogram { display: flex; align-items: flex-end; height: 120px; gap: 2px; margin-top: 0.75rem; }
.histogram-bar { flex: 1; background: #0d6efd; min-height: 2px; border-radius: 2px 2px 0 0; }
.small { font-size: 0.85rem; color: #6c757d; }
</style>
</head>
<body>
<div class="banner">{{ banner }}</div>

<h1>RESUME-RANKER Report</h1>

{% if review_queue %}
<section class="review-queue">
<h2>Review Queue</h2>
<p>The following candidates require mandatory human review before any decision is made.</p>
<table>
<tr><th>Candidate</th><th>Flags</th><th>Composite</th></tr>
{% for card in review_queue %}
<tr>
<td>{{ card.candidate_id }}</td>
<td>{% for flag in card.flags %}<span class="flag">{{ flag }}</span>{% endfor %}</td>
<td>{{ format_score(card.composite) }}</td>
</tr>
{% endfor %}
</table>
</section>
{% endif %}

<section>
<h2>Ranked Candidates</h2>
{% for card in scorecards %}
<div class="card" id="{{ card.candidate_id }}">
<div class="card-header">
<div>
<span class="rank">#{{ card.rank }}</span>
{% set name = candidate_name(card, run) %}
{% if name %}<strong>{{ name }}</strong> {% endif %}
<span class="small">{{ card.candidate_id }}</span>
</div>
<div>
<span class="score">{{ format_score(card.composite) }}</span>
{% if card.band %}<span class="band band-{{ card.band.value }}">{{ card.band.value }}</span>{% endif %}
</div>
</div>
<p class="small">Selected: {{ card.selected }} | Eligible: {{ card.eligible }} | Confidence: {{ format_score(card.confidence) }}</p>

<div class="sub-scores">
{% for dim in dimensions %}
{% set val = sub_score_value(card, dim) %}
<div class="sub-score">
<div class="sub-score-label">{{ dim }}</div>
<div class="sub-score-bar-bg">
<div class="sub-score-bar" style="width: {{ val or 0 }}%"></div>
</div>
<div class="sub-score-value">{{ format_score(val) }}</div>
</div>
{% endfor %}
</div>

{% if card.matched %}
<h3>Matched Requirements</h3>
{% for match in card.matched %}
<div class="evidence">
<strong>{{ match.criterion }}</strong> (match {{ match.match }})<br>
{% for ev in match.evidence %}
<blockquote>{{ ev.quote }}</blockquote>
<p class="small">page {{ ev.page or 'n/a' }} | span {{ ev.span }}</p>
{% endfor %}
</div>
{% endfor %}
{% endif %}

{% if card.gaps %}
<h3>Missing Requirements</h3>
{% for gap in card.gaps %}
<div class="gap">
<strong>{{ gap.criterion }}</strong> (weight {{ gap.weight }})<br>
<span class="small">Searched: {{ gap.searched | join(', ') or 'n/a' }}</span>
</div>
{% endfor %}
{% endif %}

{% if card.flags %}
<p>{% for flag in card.flags %}<span class="flag">{{ flag }}</span>{% endfor %}</p>
{% endif %}

<p class="small">{{ card.explanation }}</p>
</div>
{% endfor %}
</section>

<section class="pool-context">
<h2>Pool Context</h2>
<h3>Composite Histogram</h3>
<div class="histogram">
{% for bin in histogram %}
<div class="histogram-bar" style="height: {{ bin.max_height }}%" title="{{ bin.label }}: {{ bin.count }}"></div>
{% endfor %}
</div>
<h3>Band Counts</h3>
<ul>
{% for band, count in band_counts.items() %}
<li>{{ band }}: {{ count }}</li>
{% endfor %}
</ul>
<h3>Knockout Exclusions</h3>
<ul>
{% for rule, count in knockout_counts.items() %}
<li>{{ rule }}: {{ count }}</li>
{% endfor %}
</ul>
</section>
</body>
</html>
"""


class HtmlReportWriter(ReportWriter):
    """Write a self-contained ``report.html``.

    TRD §9.3 / FR-904: no external assets, no network requests, review queue
    rendered above the ranked list, and a decision-support banner on every page.
    """

    artefact: ClassVar[str] = "report.html"

    def write(self, run: RunResult, out_dir: Path) -> StageResult[Path]:
        path = out_dir / self.artefact
        template = Template(_HTML_TEMPLATE, autoescape=True)

        scorecards = list(run.scorecards)
        review_ids = {c.candidate_id for c in scorecards if c.flags}

        html_text = template.render(
            banner=DECISION_SUPPORT_BANNER,
            review_queue=[c for c in scorecards if c.candidate_id in review_ids],
            scorecards=scorecards,
            dimensions=[f"S{i}" for i in range(1, 11)],
            format_score=format_score,
            sub_score_value=sub_score_value,
            candidate_name=_candidate_name,
            run=run,
            histogram=_histogram(scorecards),
            band_counts=_band_counts(scorecards),
            knockout_counts=_knockout_counts(scorecards),
        )

        from resume_ranker.report._helpers import atomic_write_text

        atomic_write_text(path, html_text)
        return StageResult(value=path)


def _histogram(scorecards: list[ScoreCard], bins: int = 10) -> list[dict[str, object]]:
    """Build a histogram of composite scores over *bins* equal-width buckets."""
    counts = [0] * bins
    for card in scorecards:
        if card.composite is None:
            continue
        idx = min(int(card.composite / (100 / bins)), bins - 1)
        counts[idx] += 1
    max_count = max(counts) if counts else 1
    return [
        {
            "label": f"{i * (100 // bins)}-{(i + 1) * (100 // bins)}",
            "count": count,
            "max_height": (count / max_count) * 100 if max_count else 0,
        }
        for i, count in enumerate(counts)
    ]


def _band_counts(scorecards: list[ScoreCard]) -> dict[str, int]:
    """Count scorecards by band."""
    counts: dict[str, int] = {}
    for card in scorecards:
        band = card.band.value if card.band else "unknown"
        counts[band] = counts.get(band, 0) + 1
    return counts


def _knockout_counts(scorecards: list[ScoreCard]) -> dict[str, int]:
    """Count knockout exclusions per rule."""
    counts: dict[str, int] = {}
    for card in scorecards:
        for ko in card.knockout_results:
            if ko.verdict == "FAIL":
                counts[ko.id] = counts.get(ko.id, 0) + 1
    return counts
