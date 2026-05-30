"""
Sentiment analyzer — scores text as bullish, bearish, or neutral.

Two-tier approach
-----------------
1. **VADER** (always available):  Fast, local, no API key.  Good for social
   media text.
2. **LLM API** (optional):  When an API key is configured, uses the chosen
   LLM provider for nuanced financial sentiment on the most-discussed tickers.

SECURITY NOTES
--------------
• VADER runs entirely locally — no network calls.
• LLM API uses HTTPS only; key is read from environment variables.
• No eval/exec of dynamic content.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from src.utils.llm_client import get_llm_config, is_llm_configured, llm_chat

logger = logging.getLogger(__name__)


def _init_vader() -> Any:
    """Lazy-import VADER to avoid heavy import at module load."""
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer  # type: ignore[import]
        return SentimentIntensityAnalyzer()
    except ImportError:
        logger.error("vaderSentiment not installed — sentiment analysis disabled")
        return None


# Lazy singleton
_vader_analyzer: Any | None = None


def _get_vader() -> Any:
    global _vader_analyzer
    if _vader_analyzer is None:
        _vader_analyzer = _init_vader()
    return _vader_analyzer


def analyze_text(text: str) -> Dict[str, float]:
    """
    Run VADER sentiment analysis on a single string.

    Returns:
        Dict with keys: compound, pos, neu, neg (all floats, -1 to +1).
    """
    analyzer = _get_vader()
    if analyzer is None:
        return {"compound": 0.0, "pos": 0.0, "neu": 1.0, "neg": 0.0}

    scores = analyzer.polarity_scores(text)
    return {
        "compound": scores["compound"],
        "pos": scores["pos"],
        "neu": scores["neu"],
        "neg": scores["neg"],
    }


def analyze_posts(posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Analyze sentiment for a list of posts/tweets/articles.

    Each post dict should have at least a "text" or "title" key.
    Returns the same list with an added ``sentiment`` key.
    """
    analyzer = _get_vader()
    if analyzer is None:
        for post in posts:
            post["sentiment"] = {"compound": 0.0, "label": "neutral"}
        return posts

    for post in posts:
        text = post.get("text", "") or post.get("title", "") or ""
        summary = post.get("summary", "") or post.get("description", "")
        full_text = f"{text} {summary}".strip()
        scores = analyzer.polarity_scores(full_text)
        compound = scores["compound"]
        if compound >= 0.05:
            label = "bullish"
        elif compound <= -0.05:
            label = "bearish"
        else:
            label = "neutral"
        post["sentiment"] = {
            "compound": compound,
            "pos": scores["pos"],
            "neu": scores["neu"],
            "neg": scores["neg"],
            "label": label,
        }
    return posts


# ---------------------------------------------------------------------------
# Generic LLM enrichment
# ---------------------------------------------------------------------------

def enrich_tickers_with_llm(
    ticker_data: Dict[str, Dict[str, Any]],
    posts: List[Dict[str, Any]],
    articles: List[Dict[str, Any]],
    tracker: Any = None,
    config: Dict[str, Any] | None = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Use the configured LLM to generate nuanced sentiment and rationale
    for each ticker.  Only runs when an API key is available.
    """
    if not is_llm_configured(config):
        logger.info("No LLM API key configured — skipping LLM sentiment enrichment")
        return ticker_data

    cfg = get_llm_config(config)

    # Build context from top posts and articles
    top_posts = [p for p in posts if p.get("title")][:10]
    top_articles = [a for a in articles if a.get("title")][:10]
    context = (
        "Recent social media posts:\n"
        + "\n".join(f"- {p['title']}" for p in top_posts)
        + "\n\nRecent news headlines:\n"
        + "\n".join(f"- {a['title']}" for a in top_articles)
    )

    tickers = list(ticker_data.keys())[:15]
    if not tickers:
        return ticker_data

    system_prompt = (
        "You are a senior equity analyst. For each stock ticker provided, "
        "analyze the sentiment of recent news and social media. "
        "Return a JSON object where each key is a ticker and the value is an object with: "
        "sentiment_score (float -1.0 to +1.0), signal (BUY/HOLD/SELL/WATCH), "
        "and a one-sentence rationale. Be factual and concise."
    )
    user_prompt = (
        f"Analyze these tickers: {', '.join(tickers)}\n\n"
        f"Context:\n{context}\n\n"
        "Respond as JSON only."
    )

    content = llm_chat(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        config=config,
        response_format_json=True,
        temperature=0.3,
        max_tokens=2000,
        tracker=tracker,
        stage="llm_enrichment",
        description=f"{cfg['provider']} sentiment enrichment",
    )

    if not content:
        return ticker_data

    try:
        analysis: Dict[str, Any] = json.loads(content)
        for ticker, info in analysis.items():
            if ticker in ticker_data:
                ticker_data[ticker]["llm_sentiment"] = info.get("sentiment_score", 0.0)
                ticker_data[ticker]["llm_signal"] = info.get("signal", "WATCH")
                ticker_data[ticker]["llm_rationale"] = info.get("rationale", "")
        logger.info("LLM sentiment enrichment complete for %d tickers", len(analysis))
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM sentiment JSON")

    return ticker_data


# ---------------------------------------------------------------------------
# Backward-compatible aliases
# ---------------------------------------------------------------------------

def enrich_tickers_with_kimi(
    ticker_data: Dict[str, Dict[str, Any]],
    posts: List[Dict[str, Any]],
    articles: List[Dict[str, Any]],
    tracker: Any = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Backward-compatible alias that forces the **Kimi** provider.

    New code should call :func:`enrich_tickers_with_llm` directly.
    """
    return enrich_tickers_with_llm(
        ticker_data=ticker_data,
        posts=posts,
        articles=articles,
        tracker=tracker,
        config={"provider": "kimi"},
    )
