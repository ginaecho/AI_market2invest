"""
Top-10 ranker — selects the best investment picks and tracks day-over-day
changes.

SECURITY NOTES
--------------
• Purely local computation.
• Reads/writes only within the project outputs directory.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_HISTORY_FILE = Path("outputs") / "top10_history.json"
_TICKER_HISTORY_FILE = Path("outputs") / "ticker_score_history.json"


def rank(
    ticker_data: Dict[str, Dict[str, Any]],
    top_n: int = 10,
) -> List[Dict[str, Any]]:
    """
    Sort tickers by composite score and annotate with rank changes.

    Args:
        ticker_data: Enriched ticker dicts from composite_scorer.
        top_n: Number of top picks to return.

    Returns:
        List of the top-N ticker dicts, sorted by composite_score descending.
    """
    sorted_tickers = sorted(
        ticker_data.values(),
        key=lambda x: x.get("composite_score", 0),
        reverse=True,
    )

    # Load previous day's top-10 for comparison
    prev_top10: Dict[str, int] = {}
    if _HISTORY_FILE.exists():
        try:
            with _HISTORY_FILE.open("r", encoding="utf-8") as f:
                history = json.load(f)
            if history:
                latest = max(history.keys())
                prev_top10 = {item["ticker"]: item["rank"] for item in history[latest]}
        except Exception as exc:
            logger.warning("Failed to load top-10 history: %s", exc)

    ranked: List[Dict[str, Any]] = []
    for i, data in enumerate(sorted_tickers[:top_n], start=1):
        data["rank"] = i
        prev_rank = prev_top10.get(data["ticker"])
        if prev_rank is None:
            data["rank_change"] = "new"
        elif prev_rank > i:
            data["rank_change"] = f"↑{prev_rank - i}"
        elif prev_rank < i:
            data["rank_change"] = f"↓{i - prev_rank}"
        else:
            data["rank_change"] = "—"
        ranked.append(data)

    logger.info("Top-%d ranked; %d new entrants", top_n, sum(1 for r in ranked if r["rank_change"] == "new"))
    return ranked


def save_history(ranked: List[Dict[str, Any]]) -> None:
    """Persist today's top-10 to JSON history for trend tracking."""
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    history: Dict[str, Any] = {}

    if _HISTORY_FILE.exists():
        try:
            with _HISTORY_FILE.open("r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            pass

    history[today] = [
        {
            "ticker": r["ticker"],
            "rank": r["rank"],
            "composite_score": r.get("composite_score"),
            "price": r.get("price"),
            "change_pct": r.get("change_pct"),
            "sentiment_label": r.get("avg_sentiment_label", "neutral"),
        }
        for r in ranked
    ]

    _HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _HISTORY_FILE.open("w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)
    logger.info("Top-10 history saved to %s", _HISTORY_FILE)


def save_ticker_history(ticker_data: Dict[str, Dict[str, Any]]) -> None:
    """Persist per-ticker composite scores for sparkline trend tracking."""
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    ticker_history: Dict[str, Any] = {}

    if _TICKER_HISTORY_FILE.exists():
        try:
            with _TICKER_HISTORY_FILE.open("r", encoding="utf-8") as f:
                ticker_history = json.load(f)
        except Exception:
            pass

    for ticker, data in ticker_data.items():
        if ticker not in ticker_history:
            ticker_history[ticker] = []
        # Avoid duplicate entries for the same day
        ticker_history[ticker] = [
            entry for entry in ticker_history[ticker]
            if entry.get("date") != today
        ]
        ticker_history[ticker].append({
            "date": today,
            "composite_score": data.get("composite_score"),
            "price": data.get("price"),
            "change_pct": data.get("change_pct"),
            "sentiment_label": data.get("avg_sentiment_label", "neutral"),
        })
        # Keep only last 90 days to prevent unbounded growth
        ticker_history[ticker] = ticker_history[ticker][-90:]

    _TICKER_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _TICKER_HISTORY_FILE.open("w", encoding="utf-8") as f:
        json.dump(ticker_history, f, indent=2)
    logger.info("Ticker history saved for %d tickers", len(ticker_history))


def load_ticker_history(ticker: str) -> List[Dict[str, Any]]:
    """Load score history for a specific ticker."""
    if not _TICKER_HISTORY_FILE.exists():
        return []
    try:
        with _TICKER_HISTORY_FILE.open("r", encoding="utf-8") as f:
            history = json.load(f)
        return history.get(ticker, [])
    except Exception:
        return []
