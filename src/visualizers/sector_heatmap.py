"""
Sector heatmap — average composite score per sector.

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
    ticker_data: Dict[str, Dict[str, Any]],
    output_path: Path | None = None,
) -> Path | None:
    """
    Generate a heatmap of average composite score per sector.

    Args:
        ticker_data: Enriched ticker dicts from composite_scorer.

    Returns:
        Path to the saved PNG file.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import seaborn as sns
        import numpy as np
    except ImportError:
        logger.error("matplotlib/seaborn not installed — cannot generate sector heatmap")
        return None

    from src.analyzers.stock_mapper import SECTOR_MAP

    # Reverse map: ticker -> sector
    ticker_to_sector: Dict[str, str] = {}
    for sector, tickers in SECTOR_MAP.items():
        for t in tickers:
            ticker_to_sector[t] = sector

    # Compute average score per sector
    sector_scores: Dict[str, List[float]] = {}
    for ticker, data in ticker_data.items():
        score = data.get("composite_score", 0)
        sector = ticker_to_sector.get(ticker, "Other")
        sector_scores.setdefault(sector, []).append(score)

    if not sector_scores:
        logger.warning("No sector data for heatmap")
        return None

    sectors = sorted(sector_scores.keys())
    avg_scores = [sum(sector_scores[s]) / len(sector_scores[s]) for s in sectors]

    fig, ax = plt.subplots(figsize=(10, 4))
    data_matrix = np.array(avg_scores).reshape(1, -1)
    sns.heatmap(
        data_matrix,
        annot=True,
        fmt=".1f",
        cmap="RdYlGn",
        vmin=0,
        vmax=100,
        xticklabels=sectors,
        yticklabels=["Avg Score"],
        ax=ax,
        cbar_kws={"label": "Composite Score"},
    )
    ax.set_title("Sector Heatmap — Average Investment Signal Score")
    plt.xticks(rotation=45, ha="right")

    out = output_path or (Path("outputs") / "sector_heatmap.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Sector heatmap saved to %s", out)
    return out
