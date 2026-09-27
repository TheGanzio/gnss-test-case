"""Chart generation for comparison reports. Matplotlib, headless (Agg)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import date


def plot_comparison(
    series_by_lang: dict[str, list[tuple[str, int]]],
    title: str,
    out_path: str | Path,
    smoothing_window: int = 7,
) -> Path:
    """One line per language, lightly smoothed so daily noise doesn't hide
    the trend. Raw daily points are NOT dropped from the underlying data —
    only the plotted line is smoothed."""
    fig, ax = plt.subplots(figsize=(7.5, 3.6), dpi=150)

    for lang, points in series_by_lang.items():
        if not points:
            continue
        dates_ = [date.fromisoformat(p[0]) for p in points]
        views = [p[1] for p in points]
        smoothed = _rolling_mean(views, smoothing_window)
        ax.plot(dates_, smoothed, label=lang, linewidth=1.8)

    ax.set_title(title, fontsize=11)
    ax.set_ylabel("Views/day (smoothed)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.legend(loc="upper left", fontsize=8, frameon=False)
    ax.grid(alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)
    return out_path


def _rolling_mean(values: list[float], window: int) -> list[float]:
    if window <= 1 or len(values) < window:
        return values
    out = []
    for i in range(len(values)):
        lo = max(0, i - window + 1)
        chunk = values[lo : i + 1]
        out.append(sum(chunk) / len(chunk))
    return out
