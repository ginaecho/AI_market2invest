"""
Twitter / X collector — fetches public tweets via the X API v2 or legacy RSS mirrors.

STATUS IN 2026
--------------
**Nitter (the primary free RSS mirror) is effectively dead.**  X Corp has shut
down most public mirrors through legal pressure and rate-limiting.  The only
reliable way to collect Twitter/X data now is via the official X API v2 with a
Bearer Token.

Free tier
~~~~~~~~~
X offers a free "Basic" tier with limited monthly tweet reads (enough for this
pipeline's daily usage).  Apply at https://developer.twitter.com/.

Fallback
~~~~~~~~
If no X_BEARER_TOKEN is configured, the collector returns an empty list and
logs a clear explanation.  The pipeline still works fully without Twitter —
news RSS + Reddit + agent swarm provide sufficient data.

SECURITY NOTES
--------------
• Only reads public tweets (read-only, no posting).
• Uses short timeouts and polite User-Agent.
• Bearer token is read from environment only.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Dict, List, Any

import requests

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "AI_market2invest/1.0 (research bot; read-only)"}
_REQUEST_DELAY = 1.0
_MAX_RESULTS_PER_QUERY = 15


def _fetch_x_api_v2(bearer_token: str, query: str) -> List[Dict[str, Any]]:
    """Fetch tweets via the official X API v2 recent search endpoint."""
    url = "https://api.twitter.com/2/tweets/search/recent"
    headers = {
        **_HEADERS,
        "Authorization": f"Bearer {bearer_token}",
    }
    params = {
        "query": query,
        "max_results": min(_MAX_RESULTS_PER_QUERY, 100),
        "tweet.fields": "created_at,author_id,public_metrics",
    }
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        tweets = []
        for t in data.get("data", []):
            tweets.append({
                "text": t.get("text", ""),
                "url": f"https://twitter.com/i/web/status/{t.get('id', '')}",
                "published": t.get("created_at", ""),
                "author_id": t.get("author_id", ""),
                "source": "twitter",
                "query": query,
            })
        logger.info("Fetched %d tweets from X API for query '%s'", len(tweets), query)
        return tweets
    except requests.RequestException as exc:
        logger.debug("X API v2 failed for '%s': %s", query, exc)
        return []


def collect(
    queries: List[str] | None = None,
) -> List[Dict[str, Any]]:
    """
    Collect tweets for the given search queries.

    Args:
        queries: List of search terms (e.g. ["Trump tariff", "oil price"]).
                 Defaults to a curated set of trending finance queries.

    Returns:
        Flat list of tweet dicts (empty if X_BEARER_TOKEN is not set).
    """
    bearer_token = os.getenv("X_BEARER_TOKEN")
    if not bearer_token:
        logger.info(
            "X_BEARER_TOKEN not set — skipping Twitter/X collection. "
            "Nitter mirrors are dead in 2026; get a free Bearer Token at "
            "https://developer.twitter.com/ to enable this source."
        )
        return []

    if queries is None:
        queries = [
            "Trump",
            "geopolitics",
            "energy",
            "stock market",
            "tariff",
        ]

    all_tweets: List[Dict[str, Any]] = []
    for query in queries:
        tweets = _fetch_x_api_v2(bearer_token, query)
        all_tweets.extend(tweets)
        time.sleep(_REQUEST_DELAY)

    logger.info("Total tweets collected: %d", len(all_tweets))
    return all_tweets
