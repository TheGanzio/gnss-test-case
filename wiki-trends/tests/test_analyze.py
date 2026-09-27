from scripts.analyze import analyze_series


def _series(start_date="2024-01-01", n=120, base=100, daily_growth=0.5, spike_at=None, spike_mult=20):
    from datetime import date, timedelta

    d0 = date.fromisoformat(start_date)
    points = []
    for i in range(n):
        views = base + i * daily_growth
        if spike_at is not None and i == spike_at:
            views *= spike_mult
        points.append(((d0 + timedelta(days=i)).isoformat(), int(views)))
    return points


def test_steady_growth_is_high_confidence():
    points = _series(daily_growth=2.0)
    stats = analyze_series(
        lang="en", project="en.wikipedia", article="Test",
        points=points, start=points[0][0], end=points[-1][0], granularity="daily",
    )
    assert stats.growth_pct is not None
    assert stats.growth_pct > 0
    assert stats.confidence in ("high", "medium")
    assert stats.trend_r2 > 0.8


def test_flat_series_has_no_growth():
    points = _series(daily_growth=0.0, base=500)
    stats = analyze_series(
        lang="en", project="en.wikipedia", article="Test",
        points=points, start=points[0][0], end=points[-1][0], granularity="daily",
    )
    assert abs(stats.growth_pct) < 5


def test_single_spike_is_flagged_and_lowers_confidence():
    points = _series(daily_growth=0.0, base=50, spike_at=60, spike_mult=50)
    stats = analyze_series(
        lang="en", project="en.wikipedia", article="Test",
        points=points, start=points[0][0], end=points[-1][0], granularity="daily",
    )
    assert stats.spike_days >= 1
    assert stats.spike_view_share_pct > 25
    assert any("outlier" in r or "event" in r for r in stats.confidence_reasons)


def test_empty_series_returns_none_confidence():
    stats = analyze_series(
        lang="en", project="en.wikipedia", article="Test",
        points=[], start="2024-01-01", end="2024-02-01", granularity="daily",
    )
    assert stats.confidence == "none"
    assert stats.growth_pct is None


def test_incomplete_data_is_flagged():
    points = _series(n=10)  # far fewer points than the 32-day requested range
    stats = analyze_series(
        lang="en", project="en.wikipedia", article="Test",
        points=points, start="2024-01-01", end="2024-02-01", granularity="daily",
    )
    assert stats.data_points < stats.expected_points
    assert any("Incomplete" in r for r in stats.confidence_reasons)


def test_normalization_uses_project_aggregate():
    points = _series(daily_growth=0.0, base=100, n=60)
    agg_points = [(p[0], 1_000_000) for p in points]
    stats = analyze_series(
        lang="en", project="en.wikipedia", article="Test",
        points=points, start=points[0][0], end=points[-1][0], granularity="daily",
        project_aggregate_points=agg_points,
    )
    assert stats.normalized_share_start_pct is not None
    assert stats.normalized_share_start_pct == stats.normalized_share_end_pct
    assert 0 < stats.normalized_share_end_pct < 1
