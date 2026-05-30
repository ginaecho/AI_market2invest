"""
Investment reporter — formats the pipeline results into a readable Markdown
report and saves it to the ``outputs/`` directory.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

_OUTPUTS_DIR = Path(__file__).resolve().parents[2] / "outputs"

# Signal display config
_SIGNAL_EMOJI = {
    "BUY": "🟢",
    "HOLD": "🟡",
    "WATCH": "🔵",
    "SELL": "🔴",
}
_DEFAULT_SIGNAL = "🔵"


def _signal_for(ticker_info: Dict[str, Any]) -> str:
    ai = ticker_info.get("ai_analysis", {})
    signal = ai.get("signal", "WATCH").upper()
    return signal


def _emoji(signal: str) -> str:
    return _SIGNAL_EMOJI.get(signal, _DEFAULT_SIGNAL)


def build_report(
    topics: List[Tuple[str, int]],
    posts: List[Dict[str, Any]],
    articles: List[Dict[str, Any]],
    ticker_data: Dict[str, Dict[str, Any]],
    run_timestamp: datetime | None = None,
) -> str:
    """
    Build a Markdown investment report string.

    Args:
        topics:       Top trending topics (keyword, score).
        posts:        Raw Reddit posts.
        articles:     Raw news articles.
        ticker_data:  Enriched ticker info from stock_mapper.
        run_timestamp: UTC datetime of the pipeline run.

    Returns:
        Markdown-formatted report as a string.
    """
    ts = run_timestamp or datetime.now(tz=timezone.utc)
    ts_str = ts.strftime("%Y-%m-%d %H:%M UTC")

    lines: List[str] = []

    # ── Header ────────────────────────────────────────────────────────────
    lines += [
        "# 📈 Market Intelligence & Investment Report",
        f"**Generated:** {ts_str}",
        "",
        "> *This report is generated automatically from public Reddit posts and*",
        "> *financial RSS feeds. It is for informational purposes only and does*",
        "> *not constitute financial advice.*",
        "",
        "---",
        "",
    ]

    # ── Trending Topics ──────────────────────────────────────────────────
    lines += [
        "## 🔥 Top Trending Topics",
        "",
        "Topics ranked by engagement across Reddit financial communities and news feeds.",
        "",
        "| Rank | Topic | Score |",
        "|------|-------|-------|",
    ]
    for i, (topic, score) in enumerate(topics[:20], start=1):
        lines.append(f"| {i} | `{topic}` | {score} |")
    lines += ["", "---", ""]

    # ── News Highlights ──────────────────────────────────────────────────
    lines += [
        "## 📰 News Highlights",
        "",
    ]
    grouped: Dict[str, List[str]] = {}
    for article in articles[:40]:
        src = article.get("source", "Other")
        title = article.get("title", "").strip()
        url = article.get("url", "")
        if title:
            grouped.setdefault(src, [])
            if len(grouped[src]) < 4:
                link = f"[{title}]({url})" if url else title
                grouped[src].append(link)

    for src, items in list(grouped.items())[:6]:
        lines.append(f"### {src}")
        for item in items:
            lines.append(f"- {item}")
        lines.append("")
    lines += ["---", ""]

    # ── Reddit Buzz ───────────────────────────────────────────────────────
    lines += [
        "## 💬 Reddit Buzz",
        "",
        "Top posts by score across financial subreddits:",
        "",
    ]
    for post in posts[:10]:
        title = post.get("title", "").strip()
        url = post.get("url", "")
        sub = post.get("subreddit", "")
        score = post.get("score", 0)
        if title:
            link = f"[{title}]({url})" if url else title
            lines.append(f"- **r/{sub}** (↑{score:,}) — {link}")
    lines += ["", "---", ""]

    # ── Investment Recommendations ────────────────────────────────────────
    lines += [
        "## 💡 Investment Recommendations",
        "",
        "Stocks surfaced by social-media buzz and news coverage, ranked by aggregate",
        "engagement score.  Tickers enriched with AI analysis when available.",
        "",
    ]

    sorted_tickers = sorted(
        ticker_data.values(), key=lambda x: x["score"], reverse=True
    )

    for info in sorted_tickers[:20]:
        ticker = info["ticker"]
        score = info["score"]
        ai = info.get("ai_analysis", {})
        signal = _signal_for(info)
        emoji = _emoji(signal)

        lines.append(f"### {emoji} {ticker}")
        lines.append(f"**Signal:** {signal} &nbsp;|&nbsp; **Engagement Score:** {score}")
        lines.append("")

        # AI thesis (if available)
        if ai.get("thesis"):
            lines.append(f"**Thesis:** {ai['thesis']}")
            lines.append("")

        # Catalysts
        if ai.get("catalysts"):
            lines.append("**Catalysts:**")
            for c in ai["catalysts"]:
                lines.append(f"- {c}")
            lines.append("")

        # Risks
        if ai.get("risks"):
            lines.append("**Risks:**")
            for r in ai["risks"]:
                lines.append(f"- {r}")
            lines.append("")

        # Keyword reasons
        if info.get("reasons"):
            top_reasons = info["reasons"][:5]
            lines.append(f"**Trending keywords:** {', '.join(top_reasons)}")
            lines.append("")

        # Supporting headlines
        if info.get("news_snippets"):
            lines.append("**Supporting news:**")
            for snippet in info["news_snippets"]:
                lines.append(f"- {snippet}")
            lines.append("")

        # Reddit posts
        if info.get("reddit_snippets"):
            lines.append("**Reddit posts:**")
            for snippet in info["reddit_snippets"]:
                lines.append(f"- {snippet}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # ── Footer ────────────────────────────────────────────────────────────
    lines += [
        "## ℹ️ Methodology",
        "",
        "1. **Data collection**: Reddit posts (r/stocks, r/investing, r/wallstreetbets, "
        "r/finance, r/economics, r/StockMarket, r/options, r/dividends, r/ETFs) and "
        "financial RSS feeds (Yahoo Finance, Reuters, CNBC, MarketWatch, Seeking Alpha).",
        "2. **Topic extraction**: Keyword-frequency analysis with engagement weighting "
        "(Reddit upvotes) and editorial weighting (news mentions ×2).",
        "3. **Stock mapping**: Curated keyword→ticker dictionary covering 200+ phrases "
        "across all major sectors.",
        "4. **AI enrichment**: When `OPENAI_API_KEY` is configured, GPT-4o-mini provides "
        "narrative thesis, catalysts, and risk analysis for each ticker.",
        "",
        "*Run this pipeline daily with GitHub Actions — see `.github/workflows/market_analysis.yml`.*",
    ]

    return "\n".join(lines)


def save_report(report: str, output_dir: Path | None = None) -> Path:
    """
    Save the report to a timestamped Markdown file.

    Args:
        report:     Markdown report string.
        output_dir: Directory to write into; defaults to ``outputs/``.

    Returns:
        Path to the written file.
    """
    out_dir = output_dir or _OUTPUTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"report_{timestamp}.md"
    path = out_dir / filename
    path.write_text(report, encoding="utf-8")
    logger.info("Report saved to %s", path)
    return path


def print_summary(ticker_data: Dict[str, Dict[str, Any]], top_n: int = 10) -> None:
    """Print a compact summary table to stdout."""
    sorted_tickers = sorted(
        ticker_data.values(), key=lambda x: x["score"], reverse=True
    )[:top_n]

    print("\n" + "=" * 60)
    print(f"{'TICKER':<8} {'SIGNAL':<8} {'SCORE':>8}  REASON")
    print("=" * 60)
    for info in sorted_tickers:
        ticker = info["ticker"]
        signal = _signal_for(info)
        score = info["score"]
        top_reason = info["reasons"][0] if info.get("reasons") else ""
        print(f"{ticker:<8} {signal:<8} {score:>8}  {top_reason}")
    print("=" * 60 + "\n")
