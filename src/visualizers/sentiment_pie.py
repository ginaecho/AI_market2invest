"""
Sentiment pie chart — bullish / neutral / bearish breakdown for top-10 picks.

SECURITY NOTES
--------------
• Purely local computation.
• Reads/writes only within the project outputs directory.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def generate(
    ranked: List[Dict[str, Any]],
    output_path: Path | None = None,
) -> Path | None:
    """
    Generate a pie chart of sentiment distribution among top-10 picks.

    Args:
        ranked: Output from top10_ranker.rank.

    Returns:
        Path to the saved PNG file.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        logger.error("matplotlib not installed — cannot generate sentiment pie")
        return None

    counts = {"bullish": 0, "neutral": 0, "bearish": 0}
    for item in ranked:
        label = item.get("avg_sentiment_label", "neutral")
        counts[label] = counts.get(label, 0) + 1

    labels = [k.capitalize() for k in counts.keys() if counts[k] > 0]
    sizes = [counts[k] for k in counts.keys() if counts[k] > 0]
    colors = {"Bullish": "#2ecc71", "Neutral": "#f1c40f", "Bearish": "#e74c3c"}
    slice_colors = [colors.get(l, "#95a5a6") for l in labels]

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.pie(
        sizes,
        labels=labels,
        autopct="%1.0f%%",
        startangle=90,
        colors=slice_colors,
        explode=[0.02] * len(labels),
    )
    ax.set_title("Top-10 Sentiment Distribution")

    out = output_path or (Path("outputs") / "sentiment_pie.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Sentiment pie chart saved to %s", out)
    return out
