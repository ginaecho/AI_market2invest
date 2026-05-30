"""
Scheduler — runs the pipeline on a configurable schedule.

Uses the pure-Python ``schedule`` library for cross-platform cron-like
scheduling.  Reads configuration from ``config.yaml``.

SECURITY NOTES
--------------
• Only runs the local pipeline function — no shell commands.
• No eval/exec of dynamic content.
• Config is loaded via yaml.safe_load (no arbitrary object construction).
"""

from __future__ import annotations

import logging
import signal
import sys
import time
from pathlib import Path
from typing import Any, Dict

import yaml

logger = logging.getLogger(__name__)


def _load_config(config_path: Path) -> Dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _parse_time(time_str: str) -> tuple[int, int]:
    """Parse 'HH:MM' into (hour, minute)."""
    parts = time_str.strip().split(":")
    return int(parts[0]), int(parts[1])


def _schedule_job(schedule_cfg: Dict[str, Any], frequency_override: str | None) -> None:
    """Configure the schedule library based on config.yaml."""
    import schedule

    frequency = frequency_override or schedule_cfg.get("frequency", "daily")
    time_str = schedule_cfg.get("time", "09:00")
    hour, minute = _parse_time(time_str)

    if frequency == "daily":
        schedule.every().day.at(f"{hour:02d}:{minute:02d}").do(_run_pipeline)
        logger.info("Scheduled daily run at %02d:%02d", hour, minute)
    elif frequency == "weekly":
        schedule.every().monday.at(f"{hour:02d}:{minute:02d}").do(_run_pipeline)
        logger.info("Scheduled weekly run on Monday at %02d:%02d", hour, minute)
    else:
        logger.warning("Unknown frequency '%s' — defaulting to daily", frequency)
        schedule.every().day.at(f"{hour:02d}:{minute:02d}").do(_run_pipeline)


def _run_pipeline() -> None:
    """Wrapper that calls the pipeline and logs results."""
    logger.info("Scheduled pipeline run starting …")
    try:
        from src.pipeline import run
        result = run()
        logger.info(
            "Scheduled run complete — %d tickers, report: %s, dashboard: %s",
            len(result.get("ticker_data", {})),
            result.get("report_path", "none"),
            result.get("dashboard_path", "none"),
        )
    except Exception as exc:
        logger.error("Scheduled pipeline run failed: %s", exc)


def start_scheduler(
    config_path: Path = Path("config.yaml"),
    frequency_override: str | None = None,
) -> None:
    """
    Start the scheduler daemon.

    Args:
        config_path:        Path to config.yaml.
        frequency_override: Override the frequency setting (daily/weekly).
    """
    config = _load_config(config_path)
    schedule_cfg = config.get("schedule", {})

    _schedule_job(schedule_cfg, frequency_override)

    # Run once immediately so the user sees immediate feedback
    logger.info("Running initial pipeline …")
    _run_pipeline()

    logger.info("Scheduler running. Press Ctrl+C to stop.")

    # Graceful shutdown on SIGINT / SIGTERM
    shutdown_requested = False

    def _signal_handler(signum: int, frame: Any) -> None:
        nonlocal shutdown_requested
        shutdown_requested = True
        logger.info("Shutdown signal received — stopping scheduler …")

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    import schedule
    while not shutdown_requested:
        schedule.run_pending()
        time.sleep(60)  # check every minute

    logger.info("Scheduler stopped.")
    sys.exit(0)
