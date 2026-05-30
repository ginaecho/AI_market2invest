"""
Trend detector — identifies emerging topics before they reach the top 10.

Uses Z-score spike detection: if a keyword's frequency today is >2 standard
deviations above its 7-day rolling mean, it is flagged as "spiking".

SECURITY NOTES
--------------
• Purely local computation.
• Reads/writes only within the project outputs directory.
"""

from __future__ import annotations

import json
import logging
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

_TOPIC_HISTORY_FILE = Path("outputs") / "topic_history.json"
_ROLLING_DAYS = 7
_Z_THRESHOLD = 2.0


def _load_history() -> Dict[str, Dict[str, int]]:
    """Load topic frequency history: {date: {topic: count}}."""
    if _TOPIC_HISTORY_FILE.exists():
        try:
            with _TOPIC_HISTORY_FILE.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning("Failed to load topic history: %s", exc)
    return {}


def _save_history(history: Dict[str, Dict[str, int]]) -> None:
    _TOPIC_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _TOPIC_HISTORY_FILE.open("w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)


def detect(
    topics: List[Tuple[str, int]],
) -> List[Dict[str, Any]]:
    """
    Detect spiking topics compared to 7-day rolling average.

    Args:
        topics: Today's (topic, score) pairs from topic_extractor.

    Returns:
        List of spiking topics with z-score and trend direction.
    """
    history = _load_history()
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    today_counts = {topic: score for topic, score in topics}

    # Save today's counts
    history[today] = today_counts
    # Keep only last 30 days to limit file size
    sorted_dates = sorted(history.keys())[-30:]
    history = {d: history[d] for d in sorted_dates}
    _save_history(history)

    # Get rolling window (excluding today)
    past_dates = [d for d in sorted_dates if d != today][-_ROLLING_DAYS:]
    if len(past_dates) < 3:
        logger.info("Not enough history for trend detection (need 3+ days)")
        return []

    spiking: List[Dict[str, Any]] = []
    all_topics = set(today_counts.keys())
    for date in past_dates:
        all_topics.update(history.get(date, {}).keys())

    for topic in all_topics:
        today_count = today_counts.get(topic, 0)
        if today_count == 0:
            continue

        past_values = [
            history.get(date, {}).get(topic, 0)
            for date in past_dates
        ]
        mean = sum(past_values) / len(past_values)
        variance = sum((v - mean) ** 2 for v in past_values) / len(past_values)
        std = math.sqrt(variance) if variance > 0 else 1.0

        z_score = (today_count - mean) / std if std > 0 else 0.0
        if z_score >= _Z_THRESHOLD:
            spiking.append({
                "topic": topic,
                "today_count": today_count,
                "rolling_mean": round(mean, 2),
                "z_score": round(z_score, 2),
                "trend": "spiking",
            })

    spiking.sort(key=lambda x: x["z_score"], reverse=True)
    logger.info("Detected %d spiking topics", len(spiking))
    return spiking
