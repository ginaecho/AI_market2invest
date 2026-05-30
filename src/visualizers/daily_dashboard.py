"""
Daily dashboard — generates a single HTML file embedding all charts and tables.

SECURITY NOTES
--------------
• Purely local file generation.
• No external network calls; all assets are inline or local file references.
• No user input is rendered without HTML escaping.
"""

from __future__ import annotations

import html
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


def generate(
    ranked: List[Dict[str, Any]],
    topics: List[Tuple[str, int]],
    spiking_topics: List[Dict[str, Any]],
    posts: List[Dict[str, Any]],
    articles: List[Dict[str, Any]],
    chart_paths: List[Path],
    cost: Dict[str, Any] | None = None,
    verification: List[Dict[str, Any]] | None = None,
    output_path: Path | None = None,
) -> Path:
    """
    Generate an interactive HTML dashboard.

    Args:
        ranked: Top-10 ranked tickers.
        topics: Trending topics.
        spiking_topics: Detected spiking topics.
        posts: Reddit posts.
        articles: News articles.
        chart_paths: List of paths to generated chart PNGs.
        output_path: Where to write the HTML file.

    Returns:
        Path to the saved HTML file.
    """
    ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines: List[str] = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '  <meta charset="UTF-8">',
        '  <meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f"  <title>Market Intelligence Dashboard — {ts}</title>",
        "  <style>",
        "    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f6fa; color: #2d3436; }",
        "    h1, h2 { color: #2d3436; }",
        "    .card { background: white; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }",
        "    table { width: 100%; border-collapse: collapse; margin-top: 10px; }",
        "    th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #dfe6e9; }",
        "    th { background: #f8f9fa; font-weight: 600; }",
        "    .score { font-weight: bold; color: #0984e3; }",
        "    .bullish { color: #00b894; }",
        "    .bearish { color: #d63031; }",
        "    .neutral { color: #fdcb6e; }",
        "    .chart { max-width: 100%; border-radius: 8px; margin-top: 10px; }",
        "    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; }",
        "    .tag { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 12px; background: #dfe6e9; margin-right: 4px; }",
        "  </style>",
        "</head>",
        "<body>",
        f"  <h1>📈 Market Intelligence Dashboard</h1>",
        f"  <p>Generated: <strong>{html.escape(ts)}</strong></p>",
        '  <div class="card">',
        "    <h2>📊 Top-10 Investment Picks</h2>",
        '    <table>',
        "      <tr><th>Rank</th><th>Ticker</th><th>Score</th><th>Price</th><th>Change %</th><th>Sentiment</th><th>Signal</th><th>Change</th></tr>",
    ]

    for item in ranked:
        ticker = html.escape(item["ticker"])
        score = item.get("composite_score", 0)
        price = item.get("price", "—")
        change = item.get("change_pct", "—")
        sentiment = item.get("avg_sentiment_label", "neutral")
        signal = item.get("kimi_signal", "") or item.get("ai_analysis", {}).get("signal", "WATCH")
        rank_change = item.get("rank_change", "—")
        sentiment_cls = "bullish" if sentiment == "bullish" else "bearish" if sentiment == "bearish" else "neutral"
        lines.append(
            f"      <tr>"
            f"<td>{item['rank']}</td>"
            f"<td><strong>{ticker}</strong></td>"
            f'<td class="score">{score}</td>'
            f"<td>{price}</td>"
            f"<td>{change}</td>"
            f'<td class="{sentiment_cls}">{sentiment.capitalize()}</td>'
            f"<td>{html.escape(signal)}</td>"
            f"<td>{html.escape(str(rank_change))}</td>"
            f"</tr>"
        )

    lines += [
        "    </table>",
        "  </div>",
    ]

    # Charts
    valid_charts = [c for c in chart_paths if c and c.exists() and c.name]
    if valid_charts:
        lines += ['  <div class="grid">']
        for chart in valid_charts:
                rel = chart.name
                lines += [
                    '    <div class="card">',
                    f'      <img src="{html.escape(rel)}" class="chart" alt="{html.escape(rel)}">',
                    "    </div>",
                ]
        lines += ["  </div>"]

    # Spiking topics
    if spiking_topics:
        lines += [
            '  <div class="card">',
            "    <h2>🚀 Spiking Topics (Emerging)</h2>",
            '    <table>',
            "      <tr><th>Topic</th><th>Today</th><th>7-Day Avg</th><th>Z-Score</th></tr>",
        ]
        for st in spiking_topics[:10]:
            lines.append(
                f"      <tr>"
                f"<td>{html.escape(st['topic'])}</td>"
                f"<td>{st['today_count']}</td>"
                f"<td>{st['rolling_mean']}</td>"
                f"<td>{st['z_score']}</td>"
                f"</tr>"
            )
        lines += ["    </table>", "  </div>"]

    # Top topics
    lines += [
        '  <div class="card">',
        "    <h2>🔥 Trending Topics</h2>",
    ]
    for topic, score in topics[:20]:
        lines.append(f'    <span class="tag">{html.escape(topic)} ({score})</span>')
    lines += ["  </div>"]

    # Source highlights
    lines += [
        '  <div class="card">',
        "    <h2>📰 News Highlights</h2>",
        "    <ul>",
    ]
    for article in articles[:8]:
        title = html.escape(article.get("title", ""))
        url = html.escape(article.get("url", ""))
        source = html.escape(article.get("source", ""))
        if title:
            link = f'<a href="{url}" target="_blank" rel="noopener">{title}</a>' if url else title
            lines.append(f"      <li><strong>[{source}]</strong> {link}</li>")
    lines += ["    </ul>", "  </div>"]

    # Cost & Verification
    if cost:
        lines += [
            '  <div class="card">',
            "    <h2>💰 Cost & Token Usage</h2>",
            '    <table>',
            "      <tr><th>Metric</th><th>Value</th></tr>",
            f"      <tr><td>Total API calls</td><td>{cost.get('total_calls', 0)}</td></tr>",
            f"      <tr><td>Input tokens</td><td>{cost.get('total_input_tokens', 0):,}</td></tr>",
            f"      <tr><td>Output tokens</td><td>{cost.get('total_output_tokens', 0):,}</td></tr>",
            f"      <tr><td><strong>Total cost</strong></td><td><strong>${cost.get('total_cost_usd', 0)}</strong></td></tr>",
        ]
        for provider, data in cost.get("by_provider", {}).items():
            lines.append(
                f"      <tr><td>{html.escape(provider.capitalize())} ({data['calls']} calls)</td>"
                f"<td>${data['cost_usd']}</td></tr>"
            )
        lines += ["    </table>", "  </div>"]

    if verification:
        lines += [
            '  <div class="card">',
            "    <h2>✅ Verification Checklist</h2>",
            '    <table>',
            "      <tr><th>#</th><th>Goal</th><th>Status</th><th>Count</th></tr>",
        ]
        for i, item in enumerate(verification, start=1):
            status = "✅" if item.get("status") else "❌"
            lines.append(
                f"      <tr><td>{i}</td><td>{html.escape(item['goal'])}</td>"
                f"<td>{status}</td><td>{item.get('count', 0)}</td></tr>"
            )
        passed = sum(1 for v in verification if v.get("status"))
        lines += [
            "    </table>",
            f"    <p><strong>{passed}/{len(verification)} goals achieved.</strong></p>",
            "  </div>",
        ]

    # Footer
    lines += [
        '  <div class="card">',
        "    <p><em>This dashboard is generated automatically for informational purposes only. "
        "It does not constitute financial advice.</em></p>",
        "  </div>",
        "</body>",
        "</html>",
    ]

    out = output_path or (Path("outputs") / f"dashboard_{datetime.now(tz=timezone.utc).strftime('%Y%m%d_%H%M%S')}.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    logger.info("HTML dashboard saved to %s", out)
    return out
