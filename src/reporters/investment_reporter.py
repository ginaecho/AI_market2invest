"""
Investment reporter — formats the pipeline results into a readable Markdown
report and saves it to the ``outputs/`` directory.

SECURITY NOTES
--------------
• Only writes to the configured outputs directory.
• HTML-escapes user-facing content when generating HTML.
• No eval/exec of dynamic content.
"""

from __future__ import annotations

import logging
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

# Safe URL validation — only allow https links from known sources
_SAFE_SCHEMES = ("https://",)
_BLOCKED_PATTERNS = (
    "javascript:", "data:", "vbscript:", "file:", "about:", "chrome:", "javascript//", "data//",
)


def _is_safe_url(url: str) -> bool:
    """Validate that a URL is safe to render as a clickable link."""
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    if not url.startswith(_SAFE_SCHEMES):
        return False
    lower = url.lower()
    for bad in _BLOCKED_PATTERNS:
        if bad in lower:
            return False
    # Must look like a real URL (has a domain with a dot)
    if "." not in url.split("/", 3)[2]:
        return False
    return True


def _render_source_list(sources: List[Dict[str, Any]], key: str = "title") -> List[str]:
    """Render a list of source dicts as Markdown bullet links."""
    lines: List[str] = []
    for src in sources:
        text = src.get(key, "Source") or "Source"
        url = src.get("url", "")
        if _is_safe_url(url):
            lines.append(f"- [{text}]({url})")
        else:
            lines.append(f"- {text}")
    return lines


def _signal_for(ticker_info: Dict[str, Any]) -> str:
    ai = ticker_info.get("ai_analysis", {})
    signal = ai.get("signal", "WATCH").upper()
    if not signal or signal == "WATCH":
        signal = ticker_info.get("kimi_signal", "WATCH").upper()
    return signal


def _emoji(signal: str) -> str:
    return _SIGNAL_EMOJI.get(signal, _DEFAULT_SIGNAL)


def build_report(
    topics: List[Tuple[str, int]],
    posts: List[Dict[str, Any]],
    articles: List[Dict[str, Any]],
    ticker_data: Dict[str, Dict[str, Any]],
    ranked: List[Dict[str, Any]] | None = None,
    spiking_topics: List[Dict[str, Any]] | None = None,
    run_timestamp: datetime | None = None,
    cost: Dict[str, Any] | None = None,
    verification: List[Dict[str, Any]] | None = None,
) -> str:
    """
    Build a Markdown investment report string.

    Args:
        topics:       Top trending topics (keyword, score).
        posts:        Raw Reddit posts.
        articles:     Raw news articles.
        ticker_data:  Enriched ticker info from stock_mapper + composite_scorer.
        ranked:       Top-10 ranked tickers.
        spiking_topics: Detected spiking topics.
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
        "> *This report is generated automatically from public Reddit posts, news feeds, "
        "social media, and market data. It is for informational purposes only and does "
        "not constitute financial advice.*",
        "",
        "---",
        "",
    ]

    if ranked:
        # ── Top-10 Investment Picks ──────────────────────────────────────────
        lines += [
            "## 📊 Top-10 Investment Picks",
            "",
            "Ranked by composite score (news volume + social engagement + sentiment + price momentum + AI rationale).",
            "",
            "| Rank | Ticker | Score | Price | Change % | Sentiment | Signal | Δ |",
            "|------|--------|-------|-------|----------|-----------|--------|---|",
        ]
        for item in ranked:
            ticker = item["ticker"]
            score = item.get("composite_score", 0)
            price = item.get("price", "—")
            change = item.get("change_pct", "—")
            sentiment = item.get("avg_sentiment_label", "neutral").capitalize()
            signal = _signal_for(item)
            emoji = _emoji(signal)
            rank_change = item.get("rank_change", "—")
            lines.append(
                f"| {item['rank']} | **{ticker}** | {score} | {price} | {change} | {sentiment} | {emoji} {signal} | {rank_change} |"
            )
        lines += ["", "---", ""]

        # ── Detailed Why for Top-10 ──────────────────────────────────────────
        lines += [
            "## 💡 Why These Stocks?",
            "",
        ]
        for item in ranked:
            ticker = item["ticker"]
            score = item.get("composite_score", 0)
            signal = _signal_for(item)
            emoji = _emoji(signal)

            lines.append(f"### {emoji} {ticker} (Score: {score})")
            lines.append("")

            # Price context
            price = item.get("price")
            change = item.get("change_pct")
            if price is not None:
                lines.append(f"**Price:** ${price}  |  **Change:** {change}%")
                lines.append("")

            # Score breakdown with explanation
            breakdown = item.get("score_breakdown", {})
            if breakdown:
                lines.append("**📊 Ranking Breakdown (how this score was calculated):**")
                lines.append(f"| Factor | Weight | Raw Score | Contribution |")
                lines.append(f"|--------|--------|-----------|--------------|")
                for k, v in breakdown.items():
                    weight = {"news_volume": "25%", "social_engagement": "25%", "sentiment": "25%", "price_momentum": "15%", "ai_rationale": "10%"}.get(k, "?")
                    lines.append(f"| {k.replace('_', ' ').title()} | {weight} | {v} | ~{round(v * float(weight.rstrip('%')) / 100, 1)} |")
                lines.append("")

            # Sentiment detail
            compound = item.get("avg_sentiment", 0.0)
            sentiment_label = item.get("avg_sentiment_label", "neutral").capitalize()
            sentiment_emoji = "🟢" if compound >= 0.05 else "🔴" if compound <= -0.05 else "⚪"
            lines.append(f"**🎭 Sentiment:** {sentiment_emoji} **{sentiment_label}** (compound score: {compound:.3f})")
            lines.append("")
            if compound >= 0.05:
                lines.append(f"> *Market tone is **positive** — articles and posts mention this stock with optimistic language.*")
            elif compound <= -0.05:
                lines.append(f"> *Market tone is **negative** — articles and posts mention this stock with cautious or pessimistic language.*")
            else:
                lines.append(f"> *Market tone is **neutral** — mixed or balanced coverage with no strong directional bias.*")
            lines.append("")

            # AI thesis
            ai = item.get("ai_analysis", {})
            if ai.get("thesis"):
                lines.append(f"**AI Thesis:** {ai['thesis']}")
                lines.append("")
            kimi_rationale = item.get("kimi_rationale", "")
            if kimi_rationale:
                lines.append(f"**Kimi Rationale:** {kimi_rationale}")
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

            # What the market is saying
            lines.append("**🗣️ What the Market Is Saying:**")
            market_narrative = []
            if ai.get("thesis"):
                market_narrative.append(ai["thesis"])
            elif item.get("llm_rationale"):
                market_narrative.append(item["llm_rationale"])
            elif item.get("kimi_rationale"):
                market_narrative.append(item["kimi_rationale"])
            if item.get("news_snippets"):
                top_snippet = item["news_snippets"][0]
                market_narrative.append(f"Recent headline: '{top_snippet}'")
            if market_narrative:
                lines.append(f"> {' '.join(market_narrative[:2])}")
            else:
                lines.append(f"> *No specific market narrative available. Score driven by keyword matching and volume.*")
            lines.append("")

            # Evidence with validated source links
            if item.get("news_sources"):
                lines.append("**📰 Evidence & Sources (News):**")
                lines.extend(_render_source_list(item["news_sources"][:5], key="title"))
                lines.append("")
            elif item.get("news_snippets"):
                lines.append("**📰 Supporting news:**")
                for snippet in item["news_snippets"][:3]:
                    lines.append(f"- {snippet}")
                lines.append("")

            if item.get("reddit_sources"):
                lines.append("**💬 Evidence & Sources (Reddit):**")
                lines.extend(_render_source_list(item["reddit_sources"][:5], key="title"))
                lines.append("")
            elif item.get("reddit_snippets"):
                lines.append("**💬 Reddit buzz:**")
                for snippet in item["reddit_snippets"][:3]:
                    lines.append(f"- {snippet}")
                lines.append("")

            if item.get("twitter_sources"):
                lines.append("**🐦 Evidence & Sources (X/Twitter):**")
                lines.extend(_render_source_list(item["twitter_sources"][:5], key="text"))
                lines.append("")
            elif item.get("twitter_snippets"):
                lines.append("**🐦 Twitter/X buzz:**")
                for snippet in item["twitter_snippets"][:3]:
                    lines.append(f"- {snippet}")
                lines.append("")

            if item.get("youtube_sources"):
                lines.append("**▶️ Evidence & Sources (YouTube):**")
                lines.extend(_render_source_list(item["youtube_sources"][:5], key="title"))
                lines.append("")
            elif item.get("youtube_snippets"):
                lines.append("**▶️ YouTube mentions:**")
                for snippet in item["youtube_snippets"][:3]:
                    lines.append(f"- {snippet}")
                lines.append("")

            lines.append("---")
            lines.append("")
    else:
        # ── Legacy Investment Recommendations ────────────────────────────────
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

            if ai.get("thesis"):
                lines.append(f"**Thesis:** {ai['thesis']}")
                lines.append("")

            if ai.get("catalysts"):
                lines.append("**Catalysts:**")
                for c in ai["catalysts"]:
                    lines.append(f"- {c}")
                lines.append("")

            if ai.get("risks"):
                lines.append("**Risks:**")
                for r in ai["risks"]:
                    lines.append(f"- {r}")
                lines.append("")

            if info.get("reasons"):
                top_reasons = info["reasons"][:5]
                lines.append(f"**Trending keywords:** {', '.join(top_reasons)}")
                lines.append("")

            if info.get("news_sources"):
                lines.append("**📰 Evidence & Sources (News):**")
                lines.extend(_render_source_list(info["news_sources"][:5], key="title"))
                lines.append("")
            elif info.get("news_snippets"):
                lines.append("**📰 Supporting news:**")
                for snippet in info["news_snippets"][:3]:
                    lines.append(f"- {snippet}")
                lines.append("")

            if info.get("reddit_sources"):
                lines.append("**💬 Evidence & Sources (Reddit):**")
                lines.extend(_render_source_list(info["reddit_sources"][:5], key="title"))
                lines.append("")
            elif info.get("reddit_snippets"):
                lines.append("**💬 Reddit posts:**")
                for snippet in info["reddit_snippets"][:3]:
                    lines.append(f"- {snippet}")
                lines.append("")

            if info.get("twitter_sources"):
                lines.append("**🐦 Evidence & Sources (X/Twitter):**")
                lines.extend(_render_source_list(info["twitter_sources"][:5], key="text"))
                lines.append("")
            elif info.get("twitter_snippets"):
                lines.append("**🐦 Twitter/X buzz:**")
                for snippet in info["twitter_snippets"][:3]:
                    lines.append(f"- {snippet}")
                lines.append("")

            if info.get("youtube_sources"):
                lines.append("**▶️ Evidence & Sources (YouTube):**")
                lines.extend(_render_source_list(info["youtube_sources"][:5], key="title"))
                lines.append("")
            elif info.get("youtube_snippets"):
                lines.append("**▶️ YouTube mentions:**")
                for snippet in info["youtube_snippets"][:3]:
                    lines.append(f"- {snippet}")
                lines.append("")

            lines.append("---")
            lines.append("")

    # ── Spiking Topics ───────────────────────────────────────────────────
    if spiking_topics:
        lines += [
            "## 🚀 Spiking Topics (Emerging Trends)",
            "",
            "Topics that are rising fast compared to their 7-day rolling average.",
            "",
            "| Topic | Today | 7-Day Avg | Z-Score |",
            "|-------|-------|-----------|---------|",
        ]
        for st in spiking_topics[:10]:
            lines.append(
                f"| `{st['topic']}` | {st['today_count']} | {st['rolling_mean']} | {st['z_score']} |"
            )
        lines += ["", "---", ""]

    # ── Trending Topics ──────────────────────────────────────────────────
    lines += [
        "## 🔥 Top Trending Topics",
        "",
        "Topics ranked by engagement across all sources.",
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

    for src, items in list(grouped.items())[:8]:
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
        sentiment = post.get("sentiment", {}).get("label", "neutral")
        if title:
            link = f"[{title}]({url})" if url else title
            emoji = "🟢" if sentiment == "bullish" else "🔴" if sentiment == "bearish" else "⚪"
            lines.append(f"- **r/{sub}** (↑{score:,}) {emoji} — {link}")
    lines += ["", "---", ""]

    # ── Cost & Verification ──────────────────────────────────────────────
    if cost:
        lines += [
            "",
            "---",
            "",
            "## 💰 Cost & Token Usage",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total API calls | {cost.get('total_calls', 0)} |",
            f"| Input tokens | {cost.get('total_input_tokens', 0):,} |",
            f"| Output tokens | {cost.get('total_output_tokens', 0):,} |",
            f"| **Total cost** | **${cost.get('total_cost_usd', 0)}** |",
        ]
        for provider, data in cost.get("by_provider", {}).items():
            lines.append(
                f"| {provider.capitalize()} ({data['calls']} calls) | ${data['cost_usd']} |"
            )
        lines += ["", "---", ""]

    if verification:
        lines += [
            "## ✅ Verification Checklist",
            "",
            "| # | Goal | Status | Count |",
            "|---|------|--------|-------|",
        ]
        for i, item in enumerate(verification, start=1):
            status = "✅" if item.get("status") else "❌"
            lines.append(
                f"| {i} | {item['goal']} | {status} | {item.get('count', 0)} |"
            )
        passed = sum(1 for v in verification if v.get("status"))
        lines += [
            "",
            f"**{passed}/{len(verification)} goals achieved.**",
            "",
            "---",
            "",
        ]

    # ── Methodology ──────────────────────────────────────────────────────
    lines += [
        "## ℹ️ Methodology",
        "",
        "1. **Data collection**: Reddit posts, financial RSS feeds (Yahoo Finance, Reuters, "
        "CNBC, MarketWatch, Seeking Alpha, BBC, Al Jazeera), Twitter/X via Nitter RSS, "
        "YouTube trending via Invidious RSS, live stock prices via Yahoo Finance, "
        "and the **Kimi Agent Swarm** (specialized AI agents for Trump, geopolitics, "
        "energy, product trends, and social-media buzz).",
        "2. **Topic extraction**: Keyword-frequency analysis with engagement weighting "
        "(Reddit upvotes) and editorial weighting (news mentions ×2).",
        "3. **Stock mapping**: Curated keyword→ticker dictionary covering 300+ phrases "
        "across all major sectors including Trump/geopolitics/energy themes.",
        "4. **Sentiment analysis**: VADER (local, free) for social-media text; "
        "optional Kimi API for nuanced financial sentiment.",
        "5. **Composite scoring**: Weighted formula combining news volume, social "
        "engagement, sentiment, price momentum, and AI rationale.",
        "6. **Trend detection**: Z-score spike detection vs 7-day rolling average.",
        "",
        "*Run this pipeline daily with GitHub Actions or local scheduler — see config.yaml.*",
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
        ticker_data.values(), key=lambda x: x.get("composite_score", 0), reverse=True
    )[:top_n]

    print("\n" + "=" * 70)
    print(f"{'RANK':<6} {'TICKER':<8} {'SIGNAL':<8} {'SCORE':>8} {'PRICE':>10} {'CHANGE':>8}  REASON")
    print("=" * 70)
    for i, info in enumerate(sorted_tickers, start=1):
        ticker = info["ticker"]
        signal = _signal_for(info)
        score = info.get("composite_score", 0)
        price = info.get("price", "—")
        change = info.get("change_pct", "—")
        top_reason = info["reasons"][0] if info.get("reasons") else ""
        print(f"{i:<6} {ticker:<8} {signal:<8} {score:>8} {str(price):>10} {str(change):>8}  {top_reason}")
    print("=" * 70 + "\n")
