"""Turn a raw pageviews time series into a data-driven, trust-scored trend.

Design goals (see references/DATA_NOTES.md for the full rationale):
- Compare *interest*, not raw traffic: article views are normalized against
  the total traffic of their own language edition, because "10k views/day"
  means something very different on English vs Ukrainian Wikipedia.
- Growth is computed by comparing the start and end windows (not a single
  day), and also fit with a linear trend, to avoid one viral day skewing
  the read.
- Every trend gets an explicit confidence label plus the reasons behind it,
  so the report never states a conclusion without its caveats.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class SeriesStats:
    lang: str
    project: str
    article: str
    total_views: int
    mean_daily_views: float
    start_window_avg: float
    end_window_avg: float
    growth_pct: float | None
    trend_slope_per_day: float
    trend_r2: float
    volatility_cv: float
    spike_days: int
    spike_view_share_pct: float
    data_points: int
    expected_points: int
    normalized_share_start_pct: float | None
    normalized_share_end_pct: float | None
    confidence: str
    confidence_reasons: list[str] = field(default_factory=list)


def _linear_trend(y: np.ndarray) -> tuple[float, float]:
    """Fit views ~ day_index. Returns (slope, r2)."""
    if len(y) < 3:
        return 0.0, 0.0
    x = np.arange(len(y), dtype=float)
    x_mean, y_mean = x.mean(), y.mean()
    ss_xy = np.sum((x - x_mean) * (y - y_mean))
    ss_xx = np.sum((x - x_mean) ** 2)
    if ss_xx == 0:
        return 0.0, 0.0
    slope = ss_xy / ss_xx
    intercept = y_mean - slope * x_mean
    y_pred = slope * x + intercept
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - y_mean) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return float(slope), float(max(0.0, r2))


def _window_avg(values: np.ndarray, frac: float = 0.15, edge: str = "start") -> float:
    n = max(1, int(round(len(values) * frac)))
    return float(values[:n].mean()) if edge == "start" else float(values[-n:].mean())


def _expected_points(start: str, end: str, granularity: str) -> int:
    from datetime import date

    d0 = date.fromisoformat(start)
    d1 = date.fromisoformat(end)
    days = (d1 - d0).days + 1
    if granularity == "daily":
        return max(days, 1)
    return max(1, round(days / 30.4))


def analyze_series(
    lang: str,
    project: str,
    article: str,
    points: list[tuple[str, int]],
    start: str,
    end: str,
    granularity: str,
    project_aggregate_points: list[tuple[str, int]] | None = None,
    min_reliable_total_views: int = 1000,
) -> SeriesStats:
    dates = [p[0] for p in points]
    views = np.array([p[1] for p in points], dtype=float)

    reasons: list[str] = []

    if len(views) == 0:
        return SeriesStats(
            lang=lang,
            project=project,
            article=article,
            total_views=0,
            mean_daily_views=0.0,
            start_window_avg=0.0,
            end_window_avg=0.0,
            growth_pct=None,
            trend_slope_per_day=0.0,
            trend_r2=0.0,
            volatility_cv=0.0,
            spike_days=0,
            spike_view_share_pct=0.0,
            data_points=0,
            expected_points=_expected_points(start, end, granularity),
            normalized_share_start_pct=None,
            normalized_share_end_pct=None,
            confidence="none",
            confidence_reasons=["No data returned for this article/period."],
        )

    total_views = int(views.sum())
    mean_views = float(views.mean())
    start_avg = _window_avg(views, edge="start")
    end_avg = _window_avg(views, edge="end")
    growth_pct = ((end_avg - start_avg) / start_avg * 100) if start_avg > 0 else None

    slope, r2 = _linear_trend(views)

    std = float(views.std())
    cv = (std / mean_views) if mean_views > 0 else 0.0

    z = (views - mean_views) / std if std > 0 else np.zeros_like(views)
    spike_mask = z > 3
    spike_days = int(spike_mask.sum())
    spike_share = float(views[spike_mask].sum() / total_views * 100) if total_views > 0 else 0.0

    expected = _expected_points(start, end, granularity)
    completeness = len(points) / expected if expected > 0 else 0.0

    norm_start = norm_end = None
    if project_aggregate_points:
        agg_by_date = dict(project_aggregate_points)
        agg_vals = list(agg_by_date.values())
        if agg_vals:
            agg_start = _window_avg(np.array(agg_vals, dtype=float), edge="start")
            agg_end = _window_avg(np.array(agg_vals, dtype=float), edge="end")
            if agg_start > 0:
                norm_start = start_avg / agg_start * 100
            if agg_end > 0:
                norm_end = end_avg / agg_end * 100

    # --- confidence scoring ---
    score = 0
    if total_views >= min_reliable_total_views:
        score += 1
    else:
        reasons.append(
            f"Low total traffic ({total_views} views) — trend may be noise, "
            f"not signal."
        )

    if completeness >= 0.95:
        score += 1
    else:
        reasons.append(
            f"Incomplete data: got {len(points)}/{expected} expected data "
            f"points ({completeness:.0%})."
        )

    if cv < 0.6:
        score += 1
    else:
        reasons.append(
            f"High day-to-day volatility (CV={cv:.2f}) — single events may "
            f"dominate the average."
        )

    if spike_share < 25:
        score += 1
    else:
        reasons.append(
            f"{spike_share:.0f}% of all views came from {spike_days} outlier "
            f"day(s) — likely a news event, not sustained interest."
        )

    if r2 >= 0.3:
        score += 1
    else:
        reasons.append(
            f"Weak linear trend fit (R²={r2:.2f}) — growth/decline is not "
            f"consistent across the period."
        )

    if score >= 4:
        confidence = "high"
    elif score >= 2:
        confidence = "medium"
    else:
        confidence = "low"

    if not reasons:
        reasons.append("No data quality issues detected for this series.")

    return SeriesStats(
        lang=lang,
        project=project,
        article=article,
        total_views=total_views,
        mean_daily_views=mean_views,
        start_window_avg=start_avg,
        end_window_avg=end_avg,
        growth_pct=growth_pct,
        trend_slope_per_day=slope,
        trend_r2=r2,
        volatility_cv=cv,
        spike_days=spike_days,
        spike_view_share_pct=spike_share,
        data_points=len(points),
        expected_points=expected,
        normalized_share_start_pct=norm_start,
        normalized_share_end_pct=norm_end,
        confidence=confidence,
        confidence_reasons=reasons,
    )


def rank_by_growth(all_stats: list[SeriesStats]) -> list[SeriesStats]:
    """Sort languages by growth, pushing unreliable (low-confidence) results
    to the bottom regardless of how dramatic their growth number looks."""
    conf_rank = {"high": 0, "medium": 1, "low": 2, "none": 3}
    return sorted(
        all_stats,
        key=lambda s: (conf_rank[s.confidence], -(s.growth_pct or -1e9)),
    )
