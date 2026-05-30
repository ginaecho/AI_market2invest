"""
Pipeline orchestrator — wires together collectors, analyzers, visualizers,
and reporters into a single callable ``run()`` function.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from src.collectors import (
    news_collector,
    reddit_collector,
    stock_price_collector,
    twitter_collector,
    youtube_collector,
    tiktok_collector,
    meta_collector,
)
from src.analyzers import (
    stock_mapper,
    topic_extractor,
    sentiment_analyzer,
    composite_scorer,
    top10_ranker,
    trend_detector,
)
from src.visualizers import (
    score_trend_chart,
    sentiment_pie,
    sector_heatmap,
    wordcloud_gen,
    daily_dashboard,
)
from src.reporters import investment_reporter, html_reporter
from src.agents import coordinator as agent_coordinator
from src.utils.cost_tracker import reset_tracker
from src.utils.llm_client import get_llm_config, is_llm_configured

logger = logging.getLogger(__name__)


def _load_config(config_path: Path | None = None) -> Dict[str, Any]:
    """Load config.yaml and return parsed dict."""
    if config_path is None:
        config_path = Path("config.yaml")
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


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
    config_path: Path | None = None,
) -> Dict[str, Any]:
    """
    Run the full market-intelligence pipeline.

    Stages
    ------
    1. Collect data from all enabled sources (Reddit, news, Twitter, YouTube, ...).
    2. Run sentiment analysis on all text.
    3. Extract trending topics.
    4. Map topics to investable stock tickers.
    5. Fetch live stock prices.
    6. Enrich with LLM analysis (configurable provider).
    7. Compute composite scores and rank top 10.
    8. Detect spiking topics.
    9. Generate visualisations.
    10. Generate Markdown + HTML reports.

    Args:
        subreddits:    Override the default list of subreddits.
        news_feeds:    Override the default dict of RSS feed {name: url}.
        reddit_sort:   Reddit sort order ("hot", "top", "new", "rising").
        reddit_limit:  Max posts to fetch per subreddit.
        news_limit:    Max articles to fetch per news feed.
        top_topics:    Number of top topics to surface.
        output_dir:    Directory for saving reports.
        save:          Whether to write reports to disk.
        verbose:       Whether to print a summary table to stdout.
        config_path:   Path to config.yaml.

    Returns:
        Dict with keys:
            - posts, articles, tweets, videos: raw collected data
            - topics: merged topic list
            - ticker_data: per-ticker analysis dict
            - ranked: top-10 ranked list
            - spiking_topics: detected spiking topics
            - report: Markdown report string
            - report_path: Path object (if saved) or None
            - dashboard_path: Path to HTML dashboard (if saved) or None
            - cost: cost breakdown dict
            - verification: checklist of achieved goals
    """
    run_ts = datetime.now(tz=timezone.utc)
    logger.info("=== Pipeline started at %s ===", run_ts.isoformat())

    config = _load_config(config_path)
    social_cfg = config.get("social_sources", {})
    topic_cfg = config.get("topic_filters", {})
    scoring_cfg = config.get("scoring", {})
    output_cfg = config.get("output", {})
    cost_cfg = config.get("cost_rates", {})
    llm_cfg = config.get("llm", {})
    top_n = output_cfg.get("top_n", 10)
    out_dir = output_dir or Path(output_cfg.get("directory", "outputs"))

    # ── Cost Tracker ─────────────────────────────────────────────────────
    tracker = reset_tracker(rates=cost_cfg)

    # Pre-flight cost estimate
    swarm_cfg = config.get("agent_swarm", {})
    num_agents = len(swarm_cfg.get("agents", [])) if swarm_cfg.get("enabled") else 0
    has_llm = is_llm_configured(llm_cfg)
    resolved_llm = get_llm_config(llm_cfg)
    provider = resolved_llm["provider"]

    # Rough estimates per call
    est_agent_queries = num_agents * swarm_cfg.get("max_queries_per_agent", 5)
    est_agent_enrichment = (num_agents * 8) // 5  # batches of 5 articles
    est_llm_sentiment = 1 if has_llm else 0
    est_llm_ticker = 1 if has_llm else 0

    if has_llm:
        tracker.add_estimate(
            provider,
            input_tokens=est_agent_queries * 500
            + est_agent_enrichment * 2000
            + est_llm_sentiment * 3000
            + est_llm_ticker * 3000,
            output_tokens=est_agent_queries * 200
            + est_agent_enrichment * 500
            + est_llm_sentiment * 1000
            + est_llm_ticker * 1000,
        )

    estimate = tracker.total_estimate()
    if config.get("confirm_cost", False):
        print(f"\n💰 Estimated API cost: ${estimate['estimated_cost_usd']}")
        print(
            f"   Estimated calls: {estimate['calls']} | Input: {estimate['input_tokens']:,} tokens | Output: {estimate['output_tokens']:,} tokens"
        )
        confirm = input("Proceed? [Y/n]: ").strip().lower()
        if confirm and confirm not in ("y", "yes"):
            logger.info("Pipeline aborted by user due to cost.")
            return {"aborted": True, "reason": "cost_confirmation_denied"}
    else:
        logger.info(
            "Estimated API cost: $%s (%d calls)",
            estimate["estimated_cost_usd"],
            estimate["calls"],
        )

    # ── Stage 1: Collectors ──────────────────────────────────────────────
    logger.info("Stage 1/6 — Collecting data from all sources …")

    # Reddit
    posts = []
    if social_cfg.get("reddit", True):
        posts = reddit_collector.collect(
            subreddits=subreddits,
            sort=reddit_sort,
            limit_per_sub=reddit_limit,
        )

    # News
    articles = news_collector.collect(
        feeds=news_feeds,
        max_items_per_feed=news_limit,
    )

    # Agent Swarm (LLM-powered active collection)
    if swarm_cfg.get("enabled", True):
        logger.info("Stage 1b/6 — Running agent swarm (%s) …", provider if has_llm else "static")
        try:
            swarm_articles = agent_coordinator.run_swarm(
                enabled_agents=swarm_cfg.get("agents"),
                max_workers=swarm_cfg.get("max_workers", 5),
                max_queries_per_agent=swarm_cfg.get("max_queries_per_agent"),
                tracker=tracker,
                llm_config=llm_cfg,
            )
            # Normalize swarm articles to match news_collector format
            for sa in swarm_articles:
                sa.setdefault("summary", sa.get("text", "")[:500])
                sa.setdefault("source", sa.get("source", "Agent Swarm"))
                sa.setdefault("tags", [])
            articles.extend(swarm_articles)
            logger.info("Agent swarm contributed %d articles", len(swarm_articles))
        except Exception as exc:
            logger.warning("Agent swarm failed: %s", exc)

    # Twitter
    tweets = []
    if social_cfg.get("twitter", True):
        queries = ["Trump", "geopolitics", "energy", "stock market"]
        if topic_cfg.get("trump"):
            queries.append("Trump tariff")
        if topic_cfg.get("geopolitics"):
            queries.append("geopolitical")
        if topic_cfg.get("energy"):
            queries.append("oil price")
        tweets = twitter_collector.collect(queries=list(set(queries)))

    # YouTube
    videos = []
    if social_cfg.get("youtube", True):
        videos = youtube_collector.collect()

    # TikTok (stub)
    tiktok_posts = []
    if social_cfg.get("tiktok", False):
        tiktok_posts = tiktok_collector.collect()

    # Meta (stub)
    meta_posts = []
    if social_cfg.get("facebook", False) or social_cfg.get("instagram", False):
        meta_posts = meta_collector.collect()

    # Merge all text sources for sentiment and topic extraction
    all_posts = posts + tweets + videos + tiktok_posts + meta_posts

    # ── Stage 2: Sentiment Analysis ──────────────────────────────────────
    logger.info("Stage 2/6 — Running sentiment analysis …")
    all_posts = sentiment_analyzer.analyze_posts(all_posts)
    articles = sentiment_analyzer.analyze_posts(articles)

    # ── Stage 3: Topic Extraction ────────────────────────────────────────
    logger.info("Stage 3/6 — Extracting trending topics …")
    topics: List[Tuple[str, int]] = topic_extractor.extract(
        posts=all_posts,
        articles=articles,
        top_n=top_topics,
    )

    # ── Stage 4: Stock Mapping ───────────────────────────────────────────
    logger.info("Stage 4/6 — Mapping topics to stocks …")
    ticker_data = stock_mapper.map_topics_to_stocks(
        topics=topics,
        posts=posts,
        articles=articles,
        tweets=tweets,
        videos=videos,
    )

    # ── Stage 4b: LLM Enrichment ─────────────────────────────────────────
    logger.info("Stage 4b/6 — Enriching with LLM analysis …")
    ticker_data = stock_mapper.enrich_with_llm(
        ticker_data=ticker_data,
        topics=topics,
        articles=articles,
        tracker=tracker,
        config=llm_cfg,
    )
    ticker_data = sentiment_analyzer.enrich_tickers_with_llm(
        ticker_data=ticker_data,
        posts=all_posts,
        articles=articles,
        tracker=tracker,
        config=llm_cfg,
    )

    # ── Stage 5: Stock Prices ────────────────────────────────────────────
    logger.info("Stage 5/6 — Fetching stock prices …")
    tickers = list(ticker_data.keys())
    stock_prices = stock_price_collector.collect(tickers) if tickers else {}

    # ── Stage 6: Scoring & Ranking ───────────────────────────────────────
    logger.info("Stage 6/6 — Computing composite scores and ranking …")

    # Aggregate average sentiment per ticker
    for ticker, data in ticker_data.items():
        ticker_lower = ticker.lower()
        sentiments = []
        for post in all_posts:
            text = (
                post.get("title", "")
                + " "
                + post.get("text", "")
                + " "
                + post.get("text", "")
            ).lower()
            if ticker_lower in text:
                s = post.get("sentiment", {})
                if s:
                    sentiments.append(s.get("compound", 0))
        for article in articles:
            text = (article.get("title", "") + " " + article.get("summary", "")).lower()
            if ticker_lower in text:
                s = article.get("sentiment", {})
                if s:
                    sentiments.append(s.get("compound", 0))
        if sentiments:
            avg_sent = sum(sentiments) / len(sentiments)
            data["avg_sentiment"] = avg_sent
            data["avg_sentiment_label"] = (
                "bullish" if avg_sent >= 0.05 else "bearish" if avg_sent <= -0.05 else "neutral"
            )
        else:
            data["avg_sentiment"] = 0.0
            data["avg_sentiment_label"] = "neutral"

    ticker_data = composite_scorer.score_tickers(
        ticker_data=ticker_data,
        stock_prices=stock_prices,
        weights=scoring_cfg or None,
    )

    ranked = top10_ranker.rank(ticker_data, top_n=top_n)
    top10_ranker.save_history(ranked)
    top10_ranker.save_ticker_history(ticker_data)

    spiking_topics = trend_detector.detect(topics)

    # ── Stage 7: Visualisations ──────────────────────────────────────────
    logger.info("Generating visualisations …")
    chart_paths: List[Path] = []
    try:
        chart_paths.append(score_trend_chart.generate())
    except Exception as exc:
        logger.warning("Score trend chart failed: %s", exc)
    try:
        chart_paths.append(sentiment_pie.generate(ranked))
    except Exception as exc:
        logger.warning("Sentiment pie chart failed: %s", exc)
    try:
        chart_paths.append(sector_heatmap.generate(ticker_data))
    except Exception as exc:
        logger.warning("Sector heatmap failed: %s", exc)
    try:
        chart_paths.append(wordcloud_gen.generate(topics))
    except Exception as exc:
        logger.warning("Word cloud failed: %s", exc)
    chart_paths = [p for p in chart_paths if p and p.exists()]

    # ── Cost & Verification ──────────────────────────────────────────────
    actual_cost = tracker.total_actual()
    verification = _build_verification(
        posts=posts,
        articles=articles,
        topics=topics,
        ticker_data=ticker_data,
        ranked=ranked,
        stock_prices=stock_prices,
        chart_paths=chart_paths,
    )

    # ── Stage 8: Reports ─────────────────────────────────────────────────
    logger.info("Generating reports …")
    report = investment_reporter.build_report(
        topics=topics,
        posts=posts,
        articles=articles,
        ticker_data=ticker_data,
        ranked=ranked,
        spiking_topics=spiking_topics,
        run_timestamp=run_ts,
        cost=actual_cost,
        verification=verification,
    )

    report_path: Optional[Path] = None
    html_report_path: Optional[Path] = None
    dashboard_path: Optional[Path] = None

    if save:
        report_path = investment_reporter.save_report(report, output_dir=out_dir)
        try:
            html_report = html_reporter.build_html_report(
                topics=topics,
                posts=posts,
                articles=articles,
                ticker_data=ticker_data,
                ranked=ranked,
                spiking_topics=spiking_topics,
                run_timestamp=run_ts,
                cost=actual_cost,
                verification=verification,
            )
            html_report_path = html_reporter.save_html_report(html_report, output_dir=out_dir)
        except Exception as exc:
            logger.warning("HTML report generation failed: %s", exc)
        try:
            dashboard_path = daily_dashboard.generate(
                ranked=ranked,
                topics=topics,
                spiking_topics=spiking_topics,
                posts=posts,
                articles=articles,
                chart_paths=chart_paths,
                cost=actual_cost,
                verification=verification,
                output_path=out_dir / f"dashboard_{run_ts.strftime('%Y%m%d_%H%M%S')}.html",
            )
        except Exception as exc:
            logger.warning("HTML dashboard generation failed: %s", exc)

    if verbose:
        investment_reporter.print_summary(ticker_data, top_n=top_n)
        _print_cost_summary(actual_cost, estimate)

    logger.info("=== Pipeline finished — %d tickers, top-10 ranked ===", len(ticker_data))

    return {
        "posts": posts,
        "articles": articles,
        "tweets": tweets,
        "videos": videos,
        "topics": topics,
        "ticker_data": ticker_data,
        "ranked": ranked,
        "spiking_topics": spiking_topics,
        "report": report,
        "report_path": report_path,
        "html_report_path": html_report_path,
        "dashboard_path": dashboard_path,
        "cost": actual_cost,
        "verification": verification,
    }


def _build_verification(
    posts: List[Dict[str, Any]],
    articles: List[Dict[str, Any]],
    topics: List[Tuple[str, int]],
    ticker_data: Dict[str, Dict[str, Any]],
    ranked: List[Dict[str, Any]],
    stock_prices: Dict[str, Dict[str, Any]],
    chart_paths: List[Path],
) -> List[Dict[str, Any]]:
    """Build a checklist of goals achieved in this pipeline run."""
    checklist = [
        {"goal": "Collect Reddit posts", "status": bool(posts), "count": len(posts)},
        {"goal": "Collect news articles", "status": bool(articles), "count": len(articles)},
        {"goal": "Extract trending topics", "status": bool(topics), "count": len(topics)},
        {"goal": "Map topics to stocks", "status": bool(ticker_data), "count": len(ticker_data)},
        {
            "goal": "Fetch live stock prices",
            "status": bool(stock_prices),
            "count": len([p for p in stock_prices.values() if not p.get("error")]),
        },
        {
            "goal": "Analyze sentiment",
            "status": bool(articles and articles[0].get("sentiment") if articles else False),
            "count": len(articles),
        },
        {
            "goal": "Compute composite scores",
            "status": bool(
                ticker_data
                and list(ticker_data.values())[0].get("composite_score")
                if ticker_data
                else False
            ),
            "count": len(ticker_data),
        },
        {"goal": "Rank top-10 picks", "status": bool(ranked), "count": len(ranked)},
        {"goal": "Generate visualizations", "status": bool(chart_paths), "count": len(chart_paths)},
        {"goal": "Generate reports", "status": True, "count": 2},  # Markdown + HTML
    ]
    return checklist


def _print_cost_summary(actual: Dict[str, Any], estimate: Dict[str, Any]) -> None:
    """Print a compact cost summary to stdout."""
    print("\n" + "=" * 60)
    print("💰 API COST SUMMARY")
    print("=" * 60)
    print(f"{'Metric':<30} {'Estimated':>12} {'Actual':>12}")
    print("-" * 60)
    print(f"{'API calls':<30} {estimate['calls']:>12} {actual['total_calls']:>12}")
    print(
        f"{'Input tokens':<30} {estimate['input_tokens']:>12,} {actual['total_input_tokens']:>12,}"
    )
    print(
        f"{'Output tokens':<30} {estimate['output_tokens']:>12,} {actual['total_output_tokens']:>12,}"
    )
    print(f"{'Cost (USD)':<30} ${estimate['estimated_cost_usd']:>10} ${actual['total_cost_usd']:>10}")
    print("=" * 60)
    for provider, data in actual.get("by_provider", {}).items():
        print(f"  {provider.capitalize()}: {data['calls']} calls, ${data['cost_usd']}")
    print()
