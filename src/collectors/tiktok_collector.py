"""
TikTok collector — STUB.

Honest status of TikTok data access in 2026
--------------------------------------------
**There is no reliable, free, public API for TikTok trending content.**

Options available:
1. **TikTok Research API** — Free but requires academic/business approval (4+ weeks,
   non-commercial use only). Most individual developers are denied.
2. **Third-party data APIs** — No approval needed, instant access, but paid:
   • CreatorCrawl — 250 free credits, then pay-per-use (~$0.006/request)
   • SociaVault — 50 free credits, then from $29/month
   • ContentStats.io — from $0.015/snapshot
3. **DIY scraping** — Playwright/Puppeteer-based scraping breaks constantly due to
   TikTok's aggressive anti-bot measures. High maintenance, against ToS.

Recommended workaround
----------------------
Since TikTok trends rapidly cross-post to YouTube Shorts and Twitter/X, the
pipeline already captures TikTok-driven sentiment indirectly through:
  • YouTube collector (viral TikToks appear as Shorts)
  • Twitter/X collector (TikTok hashtags and trends are discussed)
  • Reddit collector (r/TikTokCringe, r/viral, etc. often surface trending products)

To activate a third-party API (if you obtain a key):
  1. Sign up at one of the providers above.
  2. Set TIKTOK_API_KEY in your .env file.
  3. Implement the fetch logic in the TODO section below.

SECURITY
--------
• No network requests are made in stub mode.
• When activated, all requests use HTTPS with timeouts.
• No browser automation or anti-bot circumvention.
"""

from __future__ import annotations

import logging
import os
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def collect(queries: List[str] | None = None) -> List[Dict[str, Any]]:
    """
    Collect TikTok posts (stub — returns empty unless API key is configured).

    Args:
        queries: List of search terms / hashtags.

    Returns:
        Flat list of post dicts (empty in stub mode).
    """
    api_key = os.getenv("TIKTOK_API_KEY")
    if not api_key:
        logger.info(
            "TIKTOK_API_KEY not set — skipping TikTok. "
            "See src/collectors/tiktok_collector.py for honest options."
        )
        return []

    # TODO: Implement authenticated third-party API fetch here.
    # Example using a generic REST endpoint (replace with actual provider):
    #
    # import requests
    # url = "https://api.sociavault.com/v1/scrape/tiktok/trending"
    # headers = {"Authorization": f"Bearer {api_key}"}
    # params = {"region": "US", "limit": 10}
    # resp = requests.get(url, headers=headers, params=params, timeout=10)
    # resp.raise_for_status()
    # data = resp.json()
    # ...normalize to pipeline format...
    #
    logger.warning(
        "TikTok API key is set but no provider implementation is active. "
        "Edit src/collectors/tiktok_collector.py to add your provider."
    )
    return []
