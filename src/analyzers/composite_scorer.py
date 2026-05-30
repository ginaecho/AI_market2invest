"""
Composite scorer — computes a 0-100 Investment Signal Score per ticker.

Formula
-------
Score = min(100,
    news_volume      × w1  +
    social_engagement × w2  +
    sentiment_score   × w3  +
    price_momentum    × w4  +
    ai_rationale      × w5
)

All inputs are normalised to 0-100 before weighting.

SECURITY NOTES
--------------
• Purely local computation — no network calls.
• No eval/exec; all math is explicit.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def _norm_news_volume(count: int, all_counts: List[int]) -> float:
    """Normalise news mention count to 0-100 using log scale."""
    if not all_counts or max(all_counts) == 0:
        return 0.0
    max_val = max(all_counts)
    # Cap at 95th percentile to reduce outlier impact
    pct_95 = sorted(all_counts)[int(len(all_counts) * 0.95)] if len(all_counts) >= 20 else max_val
    capped = min(count, pct_95)
    return min(100.0, (math.log1p(capped) / math.log1p(pct_95 or 1)) * 100)


def _norm_social_engagement(score: int, all_scores: List[int]) -> float:
    """Normalise social engagement score to 0-100 using log scale."""
    if not all_scores or max(all_scores) == 0:
        return 0.0
    max_val = max(all_scores)
    pct_95 = sorted(all_scores)[int(len(all_scores) * 0.95)] if len(all_scores) >= 20 else max_val
    capped = min(score, pct_95)
    return min(100.0, (math.log1p(capped) / math.log1p(pct_95 or 1)) * 100)


def _norm_sentiment(compound: float) -> float:
    """Convert VADER compound (-1 to +1) to 0-100."""
    return (compound + 1.0) * 50.0


def _norm_price_momentum(change_pct: float) -> float:
    """Convert absolute price change % to 0-100 via sigmoid."""
    # Sigmoid: 1% change -> ~73, 5% -> ~96, 10% -> ~99
    return 100.0 / (1.0 + math.exp(-0.8 * abs(change_pct)))


def _norm_ai_signal(signal: str) -> float:
    """Convert AI signal to a numeric score."""
    mapping = {
        "BUY": 90.0,
        "HOLD": 60.0,
        "WATCH": 40.0,
        "SELL": 20.0,
    }
    return mapping.get(signal.upper(), 40.0)


def score_tickers(
    ticker_data: Dict[str, Dict[str, Any]],
    stock_prices: Dict[str, Dict[str, Any]],
    weights: Dict[str, float] | None = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Compute composite scores for all tickers.

    Args:
        ticker_data: Output from stock_mapper.map_topics_to_stocks.
        stock_prices: Output from stock_price_collector.collect.
        weights: Dict of factor weights.  Defaults from config.yaml.

    Returns:
        Enriched ticker_data with ``composite_score`` and ``score_breakdown``.
    """
    if weights is None:
        weights = {
            "news_volume": 0.25,
            "social_engagement": 0.25,
            "sentiment": 0.25,
            "price_momentum": 0.15,
            "ai_rationale": 0.10,
        }

    # Collect all values for normalisation
    all_news_counts = [d.get("news_count", 0) for d in ticker_data.values()]
    all_social_scores = [d.get("score", 0) for d in ticker_data.values()]

    for ticker, data in ticker_data.items():
        # 1. News volume
        news_count = data.get("news_count", len(data.get("news_snippets", [])))
        nv = _norm_news_volume(news_count, all_news_counts)

        # 2. Social engagement
        social_score = data.get("score", 0)
        se = _norm_social_engagement(social_score, all_social_scores)

        # 3. Sentiment
        compound = data.get("avg_sentiment", 0.0)
        sent = _norm_sentiment(compound)

        # 4. Price momentum
        price_info = stock_prices.get(ticker, {})
        change_pct = price_info.get("change_pct", 0.0) or 0.0
        pm = _norm_price_momentum(change_pct)

        # 5. AI rationale
        ai_signal = data.get("kimi_signal", "")
        if not ai_signal:
            ai_signal = data.get("ai_analysis", {}).get("signal", "WATCH")
        ai = _norm_ai_signal(ai_signal)

        composite = (
            nv * weights.get("news_volume", 0.25)
            + se * weights.get("social_engagement", 0.25)
            + sent * weights.get("sentiment", 0.25)
            + pm * weights.get("price_momentum", 0.15)
            + ai * weights.get("ai_rationale", 0.10)
        )

        data["composite_score"] = round(min(100.0, composite), 2)
        data["score_breakdown"] = {
            "news_volume": round(nv, 2),
            "social_engagement": round(se, 2),
            "sentiment": round(sent, 2),
            "price_momentum": round(pm, 2),
            "ai_rationale": round(ai, 2),
        }
        data["price"] = price_info.get("price")
        data["change_pct"] = price_info.get("change_pct")
        data["volume"] = price_info.get("volume")

    logger.info("Composite scores computed for %d tickers", len(ticker_data))
    return ticker_data
