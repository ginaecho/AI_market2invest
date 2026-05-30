"""
Score trend chart — line chart showing top-10 score history over time.

SECURITY NOTES
--------------
• Purely local computation.
• Reads/writes only within the project outputs directory.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_HISTORY_FILE = Path("outputs") / "top10_history.json"


def generate(output_path: Path | None = None) -> Path | None:
    """
    Generate a line chart of top-10 composite scores over the last 30 days.

    Returns:
        Path to the saved PNG file.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from datetime import datetime
    except ImportError:
        logger.error("matplotlib not installed — cannot generate score trend chart")
        return None

    if not _HISTORY_FILE.exists():
        logger.warning("No history file found — skipping trend chart")
        return None

    try:
        with _HISTORY_FILE.open("r", encoding="utf-8") as f:
            history: Dict[str, List[Dict[str, Any]]] = json.load(f)
    except Exception as exc:
        logger.warning("Failed to load history: %s", exc)
        return None

    if not history:
        return None

    dates = sorted(history.keys())[-30:]
    if len(dates) < 2:
        logger.info("Need at least 2 days of history for trend chart")
        return None

    # Collect all tickers that ever appeared in top 10
    all_tickers = set()
    for date in dates:
        for item in history.get(date, []):
            all_tickers.add(item["ticker"])

    fig, ax = plt.subplots(figsize=(12, 6))
    for ticker in sorted(all_tickers):
        scores = []
        x_dates = []
        for date in dates:
            for item in history.get(date, []):
                if item["ticker"] == ticker:
                    scores.append(item.get("composite_score", 0))
                    x_dates.append(datetime.strptime(date, "%Y-%m-%d"))
                    break
            else:
                # Ticker not in top 10 that day — skip or use None
                pass
        if scores:
            ax.plot(x_dates, scores, marker="o", label=ticker, linewidth=1.5)

    ax.set_title("Top-10 Investment Signal Score Trend (30 Days)")
    ax.set_xlabel("Date")
    ax.set_ylabel("Composite Score")
    ax.legend(loc="upper left", fontsize="small", ncol=2)
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    fig.autofmt_xdate()

    out = output_path or (Path("outputs") / "score_trend.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Score trend chart saved to %s", out)
    return out
