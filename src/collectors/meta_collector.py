"""
Meta (Facebook / Instagram) collector — STUB.

Meta platforms require a valid App ID + App Secret and app review for most
search/use cases.  This module is a pluggable stub: it returns an empty list
when no credentials are configured, and will be activated once Meta API
credentials are provided in .env.

To activate:
  1. Create a Meta app at https://developers.facebook.com/.
  2. Complete app review for the required permissions.
  3. Set META_APP_ID and META_APP_SECRET in your .env file.
  4. Implement the authenticated fetch logic below.

SECURITY NOTES
--------------
• No network requests are made in stub mode.
• When activated, all requests use HTTPS with timeouts.
• Credentials are read from environment variables only.
"""

from __future__ import annotations

import logging
import os
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def collect(
    facebook_queries: List[str] | None = None,
    instagram_queries: List[str] | None = None,
) -> List[Dict[str, Any]]:
    """
    Collect Facebook/Instagram posts (stub — returns empty unless credentials configured).

    Args:
        facebook_queries:  List of search terms for Facebook.
        instagram_queries: List of hashtag or search terms for Instagram.

    Returns:
        Flat list of post dicts (empty in stub mode).
    """
    app_id = os.getenv("META_APP_ID")
    app_secret = os.getenv("META_APP_SECRET")
    if not (app_id and app_secret):
        logger.info(
            "META_APP_ID / META_APP_SECRET not set — skipping Meta collection (stub)"
        )
        return []

    # TODO: Implement authenticated Meta Graph API fetch here.
    logger.warning(
        "Meta credentials are set but authenticated fetch is not yet implemented"
    )
    return []
