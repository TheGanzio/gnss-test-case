"""One-page shareable PDF report generator (fpdf2, pure Python, no system deps)."""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from .analyze import SeriesStats

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"


def _block_multicell(pdf: FPDF, h: float, text: str) -> None:
    """multi_cell(w=0, ...) that returns the cursor to the left margin
    afterward (fpdf2's default leaves it at the block's right edge)."""
    pdf.multi_cell(0, h, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)


GLOBAL_ASSUMPTIONS = [
    "Traffic excludes automated/bot requests (agent=user), but still includes "
    "all human causes of a page view, not just genuine topical interest "
    "(e.g. a person landing on the page by mistake, or via an unrelated link).",
    "Cross-language comparisons use each article's share of its own Wikipedia "
    "edition's total traffic, not raw view counts, so a small-edition language "
    "isn't penalized just for having fewer total readers.",
    "A Wikipedia pageview signals curiosity about a topic, not willingness to "
    "pay for a product about it — treat this as a prioritization signal, not "
    "validation.",
    "If a language edition has no dedicated article for the topic (see "
    "'unresolved languages' below), it is excluded rather than guessed.",
]


def _fmt_pct(x: float | None) -> str:
    if x is None:
        return "n/a"
    sign = "+" if x >= 0 else ""
    return f"{sign}{x:.1f}%"


def _fmt_share_ppm(pct: float | None) -> str:
    """Article views as a share of its edition's total traffic, expressed as
    parts-per-million — plain percentages round to 0.000% at this scale."""
    if pct is None:
        return "n/a"
    return f"{pct * 1e4:.1f} ppm"


def build_report(
    out_path: str | Path,
    topic: str,
    start: str,
    end: str,
    chart_path: str | Path,
    stats: list[SeriesStats],
    unresolved_langs: list[str],
    user_question: str | None = None,
    next_steps: list[str] | None = None,
) -> Path:
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=False)
    pdf.add_font("DejaVu", "", str(FONT_DIR / "DejaVuSans.ttf"))
    pdf.add_font("DejaVu", "B", str(FONT_DIR / "DejaVuSans-Bold.ttf"))
    pdf.add_font("DejaVu", "I", str(FONT_DIR / "DejaVuSans-Oblique.ttf"))
    pdf.add_page()
    pdf.set_margins(14, 12, 14)

    pdf.set_font("DejaVu", "B", 16)
    pdf.cell(0, 8, "Wikipedia Interest Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("DejaVu", "", 11)
    pdf.cell(0, 6, f"Topic: {topic}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("DejaVu", "", 9)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(0, 5, f"Period: {start} to {end}   |   Source: Wikimedia Pageviews API", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if user_question:
        _block_multicell(pdf, 5, f"Question: {user_question}")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)

    if Path(chart_path).exists():
        pdf.image(str(chart_path), x=14, w=182)
    pdf.ln(2)

    pdf.set_font("DejaVu", "B", 10)
    col_w = [16, 20, 20, 26, 26, 70]  # sums to 178mm, fits inside A4 minus 14mm margins
    headers = ["Lang", "Growth", "Trend fit", "Start (ppm)", "End (ppm)", "Confidence & why"]
    for w, h in zip(col_w, headers):
        pdf.cell(w, 6, h, border=1)
    pdf.ln()

    pdf.set_font("DejaVu", "", 8)
    ranked = sorted(stats, key=lambda s: -(s.growth_pct or -1e9))
    for s in ranked:
        share_start = _fmt_share_ppm(s.normalized_share_start_pct)
        share_end = _fmt_share_ppm(s.normalized_share_end_pct)
        reason = s.confidence_reasons[0] if s.confidence_reasons else ""
        row = [
            s.lang,
            _fmt_pct(s.growth_pct),
            f"R2={s.trend_r2:.2f}",
            share_start,
            share_end,
            f"{s.confidence}: {reason}",
        ]
        y_before = pdf.get_y()
        x = pdf.get_x()
        x_last = x + sum(col_w[:-1])
        pdf.set_xy(x_last, y_before)
        pdf.multi_cell(col_w[-1], 4, row[-1], border=1)
        y_after = pdf.get_y()
        row_h = max(4, y_after - y_before)
        pdf.set_xy(x, y_before)
        for w, val in zip(col_w[:-1], row[:-1]):
            pdf.cell(w, row_h, str(val), border=1)
        pdf.set_xy(x, y_after)

    if unresolved_langs:
        pdf.set_font("DejaVu", "I", 8)
        pdf.set_text_color(150, 60, 0)
        _block_multicell(
            pdf, 4.5,
            f"No matching article found for: {', '.join(unresolved_langs)} — "
            f"excluded from comparison.",
        )
        pdf.set_text_color(0, 0, 0)

    pdf.ln(1)
    pdf.set_font("DejaVu", "B", 10)
    pdf.cell(0, 6, "Assumptions & limitations", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("DejaVu", "", 8)
    for a in GLOBAL_ASSUMPTIONS:
        _block_multicell(pdf, 4, f"- {a}")

    if next_steps:
        pdf.ln(1)
        pdf.set_font("DejaVu", "B", 10)
        pdf.cell(0, 6, "Suggested next steps", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("DejaVu", "", 8)
        for n in next_steps:
            _block_multicell(pdf, 4, f"- {n}")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out_path))
    return out_path
