"""
Pipeline orchestrator — wires together collectors, analyzers, and the
reporter into a single callable ``run()`` function.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.collectors import news_collector, reddit_collector
from src.analyzers import stock_mapper, topic_extractor
from src.reporters import investment_reporter

logger = logging.getLogger(__name__)


def run(
    subreddits: Optional[List[str]] = None,
    news_feeds: Optional[Dict[str, str]] = None,
    reddit_sort: str = "hot",
    reddit_limit: int = 25,
    news_limit: int = 20,
    top_topics: int = 30,
    output_dir: Optional[Path] = None,
    save: bool = True,
    verbose: bool = True,
) -> Dict[str, Any]:
    """
    Run the full market-intelligence pipeline.

    Stages
    ------
    1. Collect Reddit posts from financial subreddits.
    2. Collect news articles from financial RSS feeds.
    3. Extract trending topics from both sources.
    4. Map topics to investable stock tickers.
    5. Optionally enrich with OpenAI analysis.
    6. Generate and save a Markdown report.

    Args:
        subreddits:    Override the default list of subreddits.
        news_feeds:    Override the default dict of RSS feed {name: url}.
        reddit_sort:   Reddit sort order ("hot", "top", "new", "rising").
        reddit_limit:  Max posts to fetch per subreddit.
        news_limit:    Max articles to fetch per news feed.
        top_topics:    Number of top topics to surface.
        output_dir:    Directory for saving the report.
        save:          Whether to write the report to disk.
        verbose:       Whether to print a summary table to stdout.

    Returns:
        Dict with keys:
            - ``posts``: raw Reddit posts
            - ``articles``: raw news articles
            - ``topics``: merged topic list
            - ``ticker_data``: per-ticker analysis dict
            - ``report``: Markdown report string
            - ``report_path``: Path object (if saved) or None
    """
    run_ts = datetime.now(tz=timezone.utc)
    logger.info("=== Pipeline started at %s ===", run_ts.isoformat())

    # ── Stage 1: Reddit ──────────────────────────────────────────────────
    logger.info("Stage 1/5 — Collecting Reddit posts …")
    posts = reddit_collector.collect(
        subreddits=subreddits,
        sort=reddit_sort,
        limit_per_sub=reddit_limit,
    )

    # ── Stage 2: News ────────────────────────────────────────────────────
    logger.info("Stage 2/5 — Collecting news articles …")
    articles = news_collector.collect(
        feeds=news_feeds,
        max_items_per_feed=news_limit,
    )

    # ── Stage 3: Topic extraction ────────────────────────────────────────
    logger.info("Stage 3/5 — Extracting trending topics …")
    topics: List[Tuple[str, int]] = topic_extractor.extract(
        posts=posts,
        articles=articles,
        top_n=top_topics,
    )

    # ── Stage 4: Stock mapping ────────────────────────────────────────────
    logger.info("Stage 4/5 — Mapping topics to stocks …")
    ticker_data = stock_mapper.map_topics_to_stocks(
        topics=topics,
        posts=posts,
        articles=articles,
    )

    # ── Stage 4b: Optional OpenAI enrichment ────────────────────────────
    ticker_data = stock_mapper.enrich_with_openai(
        ticker_data=ticker_data,
        topics=topics,
        articles=articles,
    )

    # ── Stage 5: Report generation ───────────────────────────────────────
    logger.info("Stage 5/5 — Generating report …")
    report = investment_reporter.build_report(
        topics=topics,
        posts=posts,
        articles=articles,
        ticker_data=ticker_data,
        run_timestamp=run_ts,
    )

    report_path: Optional[Path] = None
    if save:
        report_path = investment_reporter.save_report(report, output_dir=output_dir)

    if verbose:
        investment_reporter.print_summary(ticker_data)

    logger.info("=== Pipeline finished — %d tickers identified ===", len(ticker_data))

    return {
        "posts": posts,
        "articles": articles,
        "topics": topics,
        "ticker_data": ticker_data,
        "report": report,
        "report_path": report_path,
    }
