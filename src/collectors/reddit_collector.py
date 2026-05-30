"""
Reddit collector — fetches hot/top posts from financial subreddits.

Uses Reddit's public JSON endpoint (no API credentials required for public
subreddits).  Optionally upgrades to the authenticated OAuth2 API when
REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET environment variables are set.

NOTE ON 403 BLOCKS
------------------
Reddit aggressively blocks automated requests, especially from cloud/datacenter
IPs. If you see "403 Blocked" errors:

1. **Best fix:** Set REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET in .env
   (create a "script" app at https://www.reddit.com/prefs/apps).
   OAuth2 authentication bypasses most blocks.

2. **Alternative:** Run from a residential IP (e.g., your home laptop rather
   than a cloud server).

3. **Fallback:** The pipeline works fine without Reddit — news RSS + agent
   swarm provide more than enough data for ranking.
"""

from __future__ import annotations

import os
import time
import logging
from typing import List, Dict, Any

import requests

logger = logging.getLogger(__name__)

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

# Rotate through a few realistic browser User-Agents; some IPs pass with these.
_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

_REQUEST_DELAY = 1.5


def _fetch_public(subreddit: str, sort: str = "hot", limit: int = 25, ua_index: int = 0) -> List[Dict[str, Any]]:
    """Fetch posts via the unauthenticated public JSON endpoint."""
    url = f"https://www.reddit.com/r/{subreddit}/{sort}.json?limit={limit}"
    headers = {"User-Agent": _USER_AGENTS[ua_index % len(_USER_AGENTS)]}
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
        logger.info("Fetched %d posts from r/%s", len(posts), subreddit)
        return posts
    except requests.RequestException as exc:
        logger.warning("Failed to fetch r/%s: %s", subreddit, exc)
        return []
    except (KeyError, ValueError) as exc:
        logger.warning("Failed to parse r/%s JSON: %s", subreddit, exc)
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
            headers={"User-Agent": _USER_AGENTS[0]},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception as exc:
        logger.warning("Reddit OAuth failed: %s", exc)
        return None


def _fetch_authenticated(token: str, subreddit: str, sort: str = "hot", limit: int = 50) -> List[Dict[str, Any]]:
    """Fetch posts via the authenticated OAuth2 API (higher rate limits, fewer blocks)."""
    url = f"https://oauth.reddit.com/r/{subreddit}/{sort}?limit={limit}"
    headers = {"User-Agent": _USER_AGENTS[0], "Authorization": f"bearer {token}"}
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
        List of post dicts ordered by score descending.
    """
    if subreddits is None:
        subreddits = DEFAULT_SUBREDDITS

    token = _get_oauth_token()
    all_posts: List[Dict[str, Any]] = []

    for i, sub in enumerate(subreddits):
        if token:
            posts = _fetch_authenticated(token, sub, sort=sort, limit=limit_per_sub)
        else:
            posts = _fetch_public(sub, sort=sort, limit=limit_per_sub, ua_index=i)
        all_posts.extend(posts)
        time.sleep(_REQUEST_DELAY)

    all_posts.sort(key=lambda p: p["score"], reverse=True)
    logger.info("Total Reddit posts collected: %d", len(all_posts))
    return all_posts
