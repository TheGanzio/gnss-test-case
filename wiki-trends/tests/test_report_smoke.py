"""End-to-end offline smoke test for chart + PDF generation.

This exercises the exact rendering path (fpdf2 cursor positioning, table
layout, Cyrillic text) without touching the network — it's what caught the
`multi_cell` cursor bug, the unreadable ppm-vs-percent formatting bug, and
the silent-row-loss pagination bug during development.
"""

from scripts.analyze import SeriesStats, analyze_series
from scripts.charts import plot_comparison
from scripts.report import build_report


def test_report_renders_one_page_with_cyrillic_question(tmp_path):
    points = [(f"2025-01-{d:02d}", 100 + d) for d in range(1, 29)]
    stats = [
        analyze_series(
            lang="uk", project="uk.wikipedia", article="Тест",
            points=points, start=points[0][0], end=points[-1][0], granularity="daily",
        )
    ]

    chart_path = tmp_path / "chart.png"
    plot_comparison({"uk": points}, title="Test topic", out_path=chart_path)
    assert chart_path.exists()

    report_path = tmp_path / "report.pdf"
    build_report(
        out_path=report_path,
        topic="Test topic",
        start=points[0][0],
        end=points[-1][0],
        chart_path=chart_path,
        stats=stats,
        unresolved_langs=["pl"],
        user_question="Чи зростає інтерес до цієї теми в україномовній Wikipedia?",
        next_steps=["Do the next thing.", "Then the thing after that."],
    )

    assert report_path.exists()
    assert report_path.stat().st_size > 1000

    from pypdf import PdfReader

    reader = PdfReader(str(report_path))
    assert len(reader.pages) == 1


def _synthetic_stats(lang: str) -> SeriesStats:
    return SeriesStats(
        lang=lang, project=f"{lang}.wikipedia", article="Test",
        total_views=100_000, mean_daily_views=200.0,
        start_window_avg=180.0, end_window_avg=220.0,
        growth_pct=12.3, trend_slope_per_day=0.5, trend_r2=0.4,
        volatility_cv=0.9, spike_days=2, spike_view_share_pct=10.0,
        data_points=700, expected_points=700,
        normalized_share_start_pct=0.001, normalized_share_end_pct=0.0012,
        confidence="medium",
        confidence_reasons=[
            "High day-to-day volatility (CV=0.90) - single events may "
            "dominate the average, and this reason is deliberately long to "
            "stress the row-height estimate used for pagination."
        ],
    )


def test_many_languages_do_not_lose_rows(tmp_path):
    """Regression test: an earlier version used a fixed-size single-page PDF
    (auto_page_break=False, no overflow handling). Past roughly the 10th
    language, rows were drawn below the physical page boundary and silently
    vanished — no exception, no page 2, just missing data. This asserts
    every requested language actually appears somewhere in the rendered
    PDF, however many pages that takes."""
    langs = [f"la{i}" for i in range(25)]
    stats = [_synthetic_stats(l) for l in langs]

    points = [(f"2024-01-{d:02d}", 100 + d) for d in range(1, 29)]
    chart_path = tmp_path / "chart.png"
    plot_comparison({l: points for l in langs[:3]}, title="Stress test", out_path=chart_path)

    report_path = tmp_path / "report.pdf"
    build_report(
        out_path=report_path,
        topic="Stress Test Topic", start="2024-01-01", end="2024-01-28",
        chart_path=chart_path, stats=stats, unresolved_langs=["xx", "yy"],
        next_steps=["step one", "step two"],
    )

    from pypdf import PdfReader

    reader = PdfReader(str(report_path))
    full_text = "".join(page.extract_text() for page in reader.pages)

    missing = [l for l in langs if l not in full_text]
    assert not missing, f"languages dropped from report: {missing}"
    assert "xx" in full_text and "yy" in full_text
    assert "step one" in full_text and "step two" in full_text
