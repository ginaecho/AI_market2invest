#!/usr/bin/env python3
"""
Entry-point script for the AI Market-to-Invest pipeline.

Usage
-----
    python run_pipeline.py                         # default settings
    python run_pipeline.py --sort top --limit 50   # top posts, 50 per sub
    python run_pipeline.py --no-save               # skip writing report file
    python run_pipeline.py --subreddits stocks investing wallstreetbets
    python run_pipeline.py --schedule              # start scheduler daemon
    python run_pipeline.py --frequency daily       # override schedule frequency
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path when run directly
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Load .env file if present (silently skip if missing)
from dotenv import load_dotenv  # noqa: E402
load_dotenv(Path(__file__).resolve().parent / ".env")

from src.pipeline import run  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect market news and social media to surface investment ideas.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--subreddits",
        nargs="+",
        metavar="SUB",
        default=None,
        help="Override the list of subreddits to monitor.",
    )
    parser.add_argument(
        "--sort",
        choices=["hot", "top", "new", "rising"],
        default="hot",
        help="Reddit post sort order (default: hot).",
    )
    parser.add_argument(
        "--reddit-limit",
        type=int,
        default=25,
        metavar="N",
        help="Max posts per subreddit (default: 25).",
    )
    parser.add_argument(
        "--news-limit",
        type=int,
        default=20,
        metavar="N",
        help="Max articles per news feed (default: 20).",
    )
    parser.add_argument(
        "--top-topics",
        type=int,
        default=30,
        metavar="N",
        help="Number of trending topics to surface (default: 30).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        metavar="DIR",
        help="Directory to save the report (default: outputs/).",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not write the report to disk; only print summary.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress the summary table output.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO).",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Start the scheduler daemon instead of running once.",
    )
    parser.add_argument(
        "--frequency",
        choices=["daily", "weekly"],
        default=None,
        help="Override the schedule frequency from config.yaml.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="Path to config.yaml (default: ./config.yaml).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if args.schedule:
        from src.scheduler import start_scheduler
        start_scheduler(
            config_path=args.config,
            frequency_override=args.frequency,
        )
        return

    result = run(
        subreddits=args.subreddits,
        reddit_sort=args.sort,
        reddit_limit=args.reddit_limit,
        news_limit=args.news_limit,
        top_topics=args.top_topics,
        output_dir=args.output_dir,
        save=not args.no_save,
        verbose=not args.quiet,
        config_path=args.config,
    )

    if result.get("report_path"):
        print(f"\n✅ Report saved to: {result['report_path']}")
    if result.get("html_report_path"):
        print(f"✅ HTML report saved to: {result['html_report_path']}")
    if result.get("dashboard_path"):
        print(f"✅ Dashboard saved to: {result['dashboard_path']}")
    if not result.get("report_path"):
        print(result["report"])


if __name__ == "__main__":
    main()
