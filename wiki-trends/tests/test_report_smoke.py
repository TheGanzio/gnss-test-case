"""End-to-end offline smoke test for chart + PDF generation.

This exercises the exact rendering path (fpdf2 cursor positioning, table
layout, Cyrillic text) without touching the network — it's what caught the
`multi_cell` cursor bug and the unreadable ppm-vs-percent formatting bug
during development.
"""

from scripts.analyze import analyze_series
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
