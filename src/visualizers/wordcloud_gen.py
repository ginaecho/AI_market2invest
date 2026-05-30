"""
Word cloud generator — visual representation of trending keywords.

SECURITY NOTES
--------------
• Purely local computation.
• Reads/writes only within the project outputs directory.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


def generate(
    topics: List[Tuple[str, int]],
    output_path: Path | None = None,
) -> Path | None:
    """
    Generate a word cloud image from trending topics.

    Args:
        topics: (keyword, score) pairs from topic_extractor.

    Returns:
        Path to the saved PNG file.
    """
    try:
        from wordcloud import WordCloud
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        logger.error("wordcloud/matplotlib not installed — cannot generate word cloud")
        return None

    if not topics:
        logger.warning("No topics for word cloud")
        return None

    # Build frequency dict
    freq: Dict[str, int] = {word: score for word, score in topics}

    wc = WordCloud(
        width=1200,
        height=600,
        background_color="white",
        colormap="viridis",
        max_words=100,
    ).generate_from_frequencies(freq)

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    ax.set_title("Trending Topics Word Cloud")

    out = output_path or (Path("outputs") / "wordcloud.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Word cloud saved to %s", out)
    return out
