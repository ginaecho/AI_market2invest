"""
News collector — fetches articles from financial RSS feeds.

Parses standard Atom/RSS feeds using *feedparser*.  No API keys are needed
for the default sources.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Any

import feedparser

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default RSS / Atom feeds to monitor
# ---------------------------------------------------------------------------
DEFAULT_FEEDS: Dict[str, str] = {
    "Yahoo Finance – Top Stories": "https://finance.yahoo.com/rss/topstories",
    "Yahoo Finance – Markets": "https://finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US",
    "Reuters – Business": "https://feeds.reuters.com/reuters/businessNews",
    "CNBC – Top News": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "CNBC – Finance": "https://www.cnbc.com/id/10001147/device/rss/rss.html",
    "MarketWatch – Top Stories": "http://feeds.marketwatch.com/marketwatch/topstories/",
    "Investopedia – News": "https://www.investopedia.com/feedbuilder/feed/getfeed/?feedName=rss_headline",
    "Seeking Alpha – Market News": "https://seekingalpha.com/market_news.xml",
    "CNBC – Economy": "https://www.cnbc.com/id/20910258/device/rss/rss.html",
}

_REQUEST_DELAY = 0.5  # seconds between feed requests


def _parse_feed(name: str, url: str, max_items: int = 20) -> List[Dict[str, Any]]:
    """Parse a single RSS/Atom feed and return a list of article dicts."""
    try:
        feed = feedparser.parse(url)
        articles = []
        for entry in feed.entries[:max_items]:
            articles.append({
                "title": entry.get("title", ""),
                "summary": entry.get("summary", entry.get("description", "")),
                "url": entry.get("link", ""),
                "published": entry.get("published", ""),
                "source": name,
                "feed_url": url,
                "tags": [t.get("term", "") for t in entry.get("tags", [])],
            })
        logger.info("Fetched %d articles from '%s'", len(articles), name)
        return articles
    except Exception as exc:
        logger.warning("Failed to parse feed '%s' (%s): %s", name, url, exc)
        return []


def collect(
    feeds: Dict[str, str] | None = None,
    max_items_per_feed: int = 20,
) -> List[Dict[str, Any]]:
    """
    Collect articles from financial RSS/Atom feeds.

    Args:
        feeds:               Dict of {name: url}; defaults to DEFAULT_FEEDS.
        max_items_per_feed:  Maximum articles to pull per feed.

    Returns:
        Flat list of article dicts from all feeds.
    """
    if feeds is None:
        feeds = DEFAULT_FEEDS

    all_articles: List[Dict[str, Any]] = []
    for name, url in feeds.items():
        articles = _parse_feed(name, url, max_items=max_items_per_feed)
        all_articles.extend(articles)
        time.sleep(_REQUEST_DELAY)

    logger.info("Total news articles collected: %d", len(all_articles))
    return all_articles
