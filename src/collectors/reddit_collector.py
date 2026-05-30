"""
Reddit collector — fetches hot/top posts from financial subreddits.

Uses Reddit's public JSON endpoint (no API credentials required for public
subreddits).  Optionally upgrades to the authenticated OAuth2 API when
REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET environment variables are set.
"""

from __future__ import annotations

import os
import time
import logging
from typing import List, Dict, Any

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default subreddits to monitor
# ---------------------------------------------------------------------------
DEFAULT_SUBREDDITS = [
    "stocks",
    "investing",
    "wallstreetbets",
    "finance",
    "economics",
    "StockMarket",
    "options",
    "SecurityAnalysis",
    "dividends",
    "ETFs",
]

_HEADERS = {"User-Agent": "AI_market2invest/1.0 (research bot)"}
_REQUEST_DELAY = 1.5  # seconds between requests to respect rate limits


def _fetch_public(subreddit: str, sort: str = "hot", limit: int = 25) -> List[Dict[str, Any]]:
    """Fetch posts via the unauthenticated public JSON endpoint."""
    url = f"https://www.reddit.com/r/{subreddit}/{sort}.json?limit={limit}"
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        children = resp.json()["data"]["children"]
        posts = []
        for child in children:
            p = child["data"]
            posts.append({
                "title": p.get("title", ""),
                "text": p.get("selftext", ""),
                "score": p.get("score", 0),
                "num_comments": p.get("num_comments", 0),
                "url": "https://reddit.com" + p.get("permalink", ""),
                "subreddit": subreddit,
                "author": p.get("author", ""),
                "created_utc": p.get("created_utc", 0),
                "source": "reddit",
            })
        logger.info("Fetched %d posts from r/%s", len(posts), subreddit)
        return posts
    except requests.RequestException as exc:
        logger.warning("Failed to fetch r/%s: %s", subreddit, exc)
        return []


def _get_oauth_token() -> str | None:
    """Obtain a Reddit OAuth2 bearer token using app credentials."""
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    if not (client_id and client_secret):
        return None
    try:
        resp = requests.post(
            "https://www.reddit.com/api/v1/access_token",
            auth=(client_id, client_secret),
            data={"grant_type": "client_credentials"},
            headers=_HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception as exc:
        logger.warning("Reddit OAuth failed: %s", exc)
        return None


def _fetch_authenticated(token: str, subreddit: str, sort: str = "hot", limit: int = 50) -> List[Dict[str, Any]]:
    """Fetch posts via the authenticated OAuth2 API (higher rate limits)."""
    url = f"https://oauth.reddit.com/r/{subreddit}/{sort}?limit={limit}"
    headers = {**_HEADERS, "Authorization": f"bearer {token}"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        children = resp.json()["data"]["children"]
        posts = []
        for child in children:
            p = child["data"]
            posts.append({
                "title": p.get("title", ""),
                "text": p.get("selftext", ""),
                "score": p.get("score", 0),
                "num_comments": p.get("num_comments", 0),
                "url": "https://reddit.com" + p.get("permalink", ""),
                "subreddit": subreddit,
                "author": p.get("author", ""),
                "created_utc": p.get("created_utc", 0),
                "source": "reddit",
            })
        logger.info("Fetched %d posts from r/%s (authenticated)", len(posts), subreddit)
        return posts
    except requests.RequestException as exc:
        logger.warning("Authenticated fetch failed for r/%s: %s", subreddit, exc)
        return []


def collect(
    subreddits: List[str] | None = None,
    sort: str = "hot",
    limit_per_sub: int = 25,
) -> List[Dict[str, Any]]:
    """
    Collect posts from the given subreddits.

    Args:
        subreddits: List of subreddit names; defaults to DEFAULT_SUBREDDITS.
        sort:       Reddit sort order — "hot", "top", "new", "rising".
        limit_per_sub: Maximum posts to fetch per subreddit.

    Returns:
        List of post dicts ordered by (subreddit, score desc).
    """
    if subreddits is None:
        subreddits = DEFAULT_SUBREDDITS

    token = _get_oauth_token()
    all_posts: List[Dict[str, Any]] = []

    for sub in subreddits:
        if token:
            posts = _fetch_authenticated(token, sub, sort=sort, limit=limit_per_sub)
        else:
            posts = _fetch_public(sub, sort=sort, limit=limit_per_sub)
        all_posts.extend(posts)
        time.sleep(_REQUEST_DELAY)

    # Sort by score descending so the most-upvoted items appear first
    all_posts.sort(key=lambda p: p["score"], reverse=True)
    logger.info("Total Reddit posts collected: %d", len(all_posts))
    return all_posts
