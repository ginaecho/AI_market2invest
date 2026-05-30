"""
YouTube collector — fetches recent video metadata via public channel RSS feeds.

YouTube exposes RSS feeds for every channel at::

    https://www.youtube.com/feeds/videos.xml?channel_id=<CHANNEL_ID>

This is official, public, and requires no API key.  We monitor a curated list
of financial news channels and aggregate their latest uploads.

To add channels, find the channel ID (e.g. from the channel's page source)
and add it to _CHANNELS below.

SECURITY NOTES
--------------
• Only reads public RSS feeds (read-only).
• Uses polite timeouts and browser-like User-Agent headers.
• No credentials required.
"""

from __future__ import annotations

import logging
import time
from typing import List, Dict, Any

import feedparser
import requests

logger = logging.getLogger(__name__)

# Curated financial news channels on YouTube.
# Format: (channel_id, display_name)
_CHANNELS: List[tuple[str, str]] = [
    ("UCrp_UI8XtuYfpiqluWLD7Lw", "CNBC"),
    ("UChoFur1j9sh3L8G2cTcG6ng", "Bloomberg"),
    ("UCzB3BqUB-DRqB0l1wKEE_uw", "Yahoo Finance"),
    ("UCckHqySbfy5FcPPaMDSIdww", "Wall Street Journal"),
]

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
_REQUEST_DELAY = 0.5


def _fetch_channel(channel_id: str, name: str, max_videos: int = 10) -> List[Dict[str, Any]]:
    """Fetch recent videos from a YouTube channel via RSS."""
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=10)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
        videos = []
        for entry in feed.entries[:max_videos]:
            videos.append({
                "title": entry.get("title", ""),
                "description": entry.get("summary", ""),
                "url": entry.get("link", ""),
                "published": entry.get("published", ""),
                "author": entry.get("author", ""),
                "source": f"youtube:{name}",
            })
        logger.info("Fetched %d videos from %s", len(videos), name)
        return videos
    except requests.RequestException as exc:
        logger.debug("YouTube RSS fetch failed for %s: %s", name, exc)
        return []


def collect(
    channels: List[tuple[str, str]] | None = None,
    max_per_channel: int = 10,
) -> List[Dict[str, Any]]:
    """
    Collect recent videos from financial YouTube channels.

    Args:
        channels: List of (channel_id, name) tuples; defaults to _CHANNELS.
        max_per_channel: Max videos to fetch per channel.

    Returns:
        Flat list of video dicts.
    """
    if channels is None:
        channels = _CHANNELS

    all_videos: List[Dict[str, Any]] = []
    for channel_id, name in channels:
        videos = _fetch_channel(channel_id, name, max_per_channel)
        all_videos.extend(videos)
        time.sleep(_REQUEST_DELAY)

    logger.info("Total YouTube videos collected: %d", len(all_videos))
    return all_videos
