"""
Daily dashboard — generates a single HTML file embedding all charts, tables,
per-ticker detail cards with trend sparklines, and time-range selectors.

SECURITY NOTES
--------------
• Purely local file generation.
• No external network calls; all assets are inline.
• No user input is rendered without HTML escaping.
"""

from __future__ import annotations

import html
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

_HISTORY_FILE = Path("outputs") / "ticker_score_history.json"

# ── CSS ──────────────────────────────────────────────────────────────────────

_CSS = """
:root {
  --bg: #f5f6fa;
  --card-bg: #ffffff;
  --text: #2d3436;
  --text-muted: #636e72;
  --border: #dfe6e9;
  --primary: #0984e3;
  --success: #00b894;
  --warning: #fdcb6e;
  --danger: #d63031;
  --shadow: 0 2px 8px rgba(0,0,0,0.06);
  --radius: 12px;
  --font: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0f1115;
    --card-bg: #1a1d24;
    --text: #e9ecef;
    --text-muted: #adb5bd;
    --border: #2d333b;
    --primary: #74b9ff;
    --success: #55efc4;
    --warning: #ffeaa7;
    --danger: #ff7675;
    --shadow: 0 2px 8px rgba(0,0,0,0.3);
  }
}

* { box-sizing: border-box; }

body {
  margin: 0;
  padding: 20px;
  font-family: var(--font);
  background: var(--bg);
  color: var(--text);
}

h1, h2, h3 { color: var(--text); }

.card {
  background: var(--card-bg);
  border-radius: var(--radius);
  padding: 20px;
  margin-bottom: 20px;
  box-shadow: var(--shadow);
}

/* ── Table ──────────────────────────────────────────────────────────────── */
table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 10px;
}

th, td {
  padding: 10px 12px;
  text-align: left;
  border-bottom: 1px solid var(--border);
}

th { background: rgba(0,0,0,0.03); font-weight: 600; }

.score { font-weight: bold; color: var(--primary); }

.bullish { color: var(--success); }
.bearish { color: var(--danger); }
.neutral { color: var(--warning); }

/* ── Ticker links ───────────────────────────────────────────────────────── */
.ticker-link {
  color: var(--primary);
  text-decoration: none;
  font-weight: 700;
}
.ticker-link:hover {
  text-decoration: underline;
}

/* ── Ticker detail card ─────────────────────────────────────────────────── */
.ticker-detail {
  scroll-margin-top: 20px;
}

.ticker-detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border);
}

.ticker-detail-symbol {
  font-size: 1.4rem;
  font-weight: 800;
}

.ticker-detail-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--text-muted);
  font-size: 0.9rem;
}

.badge {
  display: inline-flex;
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
}

.badge-buy  { background: rgba(0,184,148,0.12); color: var(--success); }
.badge-hold { background: rgba(253,203,110,0.2); color: #d4a017; }
.badge-watch{ background: rgba(116,185,255,0.12); color: var(--primary); }
.badge-sell { background: rgba(214,48,49,0.12); color: var(--danger); }

/* ── Sparkline ──────────────────────────────────────────────────────────── */
.sparkline-wrap {
  background: rgba(0,0,0,0.02);
  border-radius: 10px;
  padding: 16px;
  margin: 12px 0;
}

.sparkline-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.sparkline-title {
  font-size: 0.8rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted);
}

.sparkline-svg {
  width: 100%;
  height: 90px;
  overflow: visible;
}

.sparkline-path {
  fill: none;
  stroke: var(--primary);
  stroke-width: 2.5;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.sparkline-area {
  fill: rgba(9, 132, 227, 0.08);
  stroke: none;
}

.sparkline-dot {
  fill: var(--primary);
  stroke: var(--card-bg);
  stroke-width: 2.5;
  r: 4;
}

.sparkline-label {
  font-size: 9px;
  fill: var(--text-muted);
  font-family: monospace;
}

.sparkline-grid {
  stroke: var(--border);
  stroke-width: 0.5;
  stroke-dasharray: 2,2;
  opacity: 0.5;
}

/* ── Range buttons ──────────────────────────────────────────────────────── */
.range-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}

.range-btn {
  padding: 5px 12px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--card-bg);
  color: var(--text-muted);
  font-size: 0.78rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}

.range-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
}

.range-btn.active {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
}

.range-btn.disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* ── Limitation note ────────────────────────────────────────────────────── */
.limitation-note {
  background: rgba(253,203,110,0.1);
  border-left: 3px solid var(--warning);
  padding: 10px 14px;
  border-radius: 0 8px 8px 0;
  font-size: 0.82rem;
  color: var(--text-muted);
  margin: 8px 0;
}

/* ── Chart images ───────────────────────────────────────────────────────── */
.chart { max-width: 100%; border-radius: 8px; margin-top: 10px; }

.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; }

.tag { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 12px; background: var(--border); margin-right: 4px; }

/* ── Back to top ────────────────────────────────────────────────────────── */
.back-to-top {
  display: inline-block;
  margin-top: 12px;
  font-size: 0.82rem;
  color: var(--primary);
  text-decoration: none;
}
.back-to-top:hover { text-decoration: underline; }

/* ── eToro-style market panel ───────────────────────────────────────────── */
.market-panel {
  background: rgba(0,0,0,0.02);
  border-radius: 10px;
  padding: 16px;
  margin: 12px 0 20px;
}

.market-header {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.market-logo {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  object-fit: cover;
  background: var(--border);
}

.market-price-block { flex: 1; min-width: 180px; }

.market-last {
  font-size: 1.6rem;
  font-weight: 800;
  line-height: 1.2;
}

.market-change.up { color: var(--success); }
.market-change.down { color: var(--danger); }

.market-bid-ask {
  display: flex;
  gap: 16px;
  font-size: 0.82rem;
  color: var(--text-muted);
  margin-top: 4px;
}

.market-bid-ask strong { color: var(--text); }

.market-canvas-wrap {
  position: relative;
  width: 100%;
  height: 220px;
  margin-top: 8px;
}

.market-canvas {
  width: 100%;
  height: 220px;
  display: block;
  border-radius: 8px;
  background: rgba(0,0,0,0.015);
}

.market-source {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-top: 8px;
}
"""

_JS = """
function showRange(ticker, range) {
  // Hide all sparklines for this ticker
  document.querySelectorAll('.sparkline-' + ticker).forEach(function(el) {
    el.style.display = 'none';
  });
  // Show selected
  var selected = document.getElementById('sparkline-' + ticker + '-' + range);
  if (selected) selected.style.display = 'block';
  // Update buttons
  document.querySelectorAll('.btn-' + ticker).forEach(function(btn) {
    btn.classList.remove('active');
  });
  var activeBtn = document.getElementById('btn-' + ticker + '-' + range);
  if (activeBtn) activeBtn.classList.add('active');
}

function showMarketRange(ticker, range) {
  document.querySelectorAll('.mkt-btn-' + ticker).forEach(function(btn) {
    btn.classList.remove('active');
  });
  var activeBtn = document.getElementById('mkt-btn-' + ticker + '-' + range);
  if (activeBtn) activeBtn.classList.add('active');
  drawMarketChart(ticker, range);
}

function drawMarketChart(ticker, range) {
  var canvas = document.getElementById('market-canvas-' + ticker);
  if (!canvas || !window.MARKET_CHARTS || !window.MARKET_CHARTS[ticker]) return;
  var candles = window.MARKET_CHARTS[ticker][range];
  if (!candles || !candles.length) return;

  var ctx = canvas.getContext('2d');
  var dpr = window.devicePixelRatio || 1;
  var rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  ctx.scale(dpr, dpr);
  var W = rect.width, H = rect.height;
  ctx.clearRect(0, 0, W, H);

  var padL = 48, padR = 12, padT = 14, padB = 28;
  var lows = candles.map(function(c) { return c.l; });
  var highs = candles.map(function(c) { return c.h; });
  var minP = Math.min.apply(null, lows);
  var maxP = Math.max.apply(null, highs);
  var pad = (maxP - minP) * 0.06 || 1;
  minP -= pad; maxP += pad;
  var n = candles.length;
  var slot = (W - padL - padR) / n;
  var bodyW = Math.max(2, slot * 0.55);

  function y(price) {
    return padT + (maxP - price) / (maxP - minP) * (H - padT - padB);
  }

  candles.forEach(function(c, i) {
    var cx = padL + slot * i + slot / 2;
    var up = c.c >= c.o;
    var color = up ? '#00b894' : '#d63031';
    ctx.strokeStyle = color;
    ctx.fillStyle = color;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(cx, y(c.h));
    ctx.lineTo(cx, y(c.l));
    ctx.stroke();
    var top = y(Math.max(c.o, c.c));
    var bot = y(Math.min(c.o, c.c));
    var h = Math.max(1, bot - top);
    ctx.fillRect(cx - bodyW / 2, top, bodyW, h);
  });

  ctx.fillStyle = '#636e72';
  ctx.font = '10px monospace';
  ctx.textAlign = 'right';
  ctx.fillText(maxP.toFixed(2), padL - 6, y(maxP) + 3);
  ctx.fillText(minP.toFixed(2), padL - 6, y(minP) + 3);
  if (candles.length >= 2) {
    var fmt = function(ts) {
      var d = new Date(ts * 1000);
      return (d.getMonth()+1) + '/' + d.getDate() + ' ' +
        String(d.getHours()).padStart(2,'0') + ':' + String(d.getMinutes()).padStart(2,'0');
    };
    ctx.textAlign = 'center';
    ctx.fillText(fmt(candles[0].t), padL + slot/2, H - 6);
    ctx.fillText(fmt(candles[n-1].t), padL + slot*(n-1) + slot/2, H - 6);
  }
}

document.addEventListener('DOMContentLoaded', function() {
  if (!window.MARKET_CHARTS) return;
  Object.keys(window.MARKET_CHARTS).forEach(function(ticker) {
    var frames = window.MARKET_CHARTS[ticker];
    var first = frames['1D'] ? '1D' : Object.keys(frames)[0];
    if (first) drawMarketChart(ticker, first);
  });
});
"""


# ── Helpers ──────────────────────────────────────────────────────────────────


def _h(text: str) -> str:
    return html.escape(str(text))


def _badge_class(signal: str) -> str:
    return {
        "BUY": "badge-buy",
        "HOLD": "badge-hold",
        "WATCH": "badge-watch",
        "SELL": "badge-sell",
    }.get(signal.upper(), "badge-watch")


def _load_history() -> Dict[str, List[Dict[str, Any]]]:
    """Load per-ticker score history from JSON.

    The file format is {ticker: [ {date, composite_score, price, ...}, ... ]}
    as written by top10_ranker.save_ticker_history().
    """
    if not _HISTORY_FILE.exists():
        return {}
    try:
        with _HISTORY_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        # data is {ticker: [ {date, composite_score, ...}, ... ]}
        ticker_history: Dict[str, List[Dict[str, Any]]] = {}
        for ticker, entries in data.items():
            if not isinstance(entries, list):
                continue
            ticker_history[ticker] = [
                {
                    "date": e.get("date", ""),
                    "score": e.get("composite_score", 0) or 0,
                    "price": e.get("price"),
                    "rank": None,
                }
                for e in entries
                if e.get("date")
            ]
            ticker_history[ticker].sort(key=lambda x: x["date"])
        return ticker_history
    except Exception as exc:
        logger.warning("Failed to load history: %s", exc)
        return {}


def _sparkline_svg(
    ticker: str,
    history: List[Dict[str, Any]],
    range_label: str,
    visible: bool = True,
) -> str:
    """Generate an inline SVG sparkline for a ticker."""
    if not history or len(history) < 2:
        return ""

    scores = [h["score"] for h in history]
    dates = [h["date"] for h in history]
    n = len(scores)

    # Padding
    pad_left = 40
    pad_right = 20
    pad_top = 15
    pad_bottom = 20
    chart_w = 600 - pad_left - pad_right
    chart_h = 90 - pad_top - pad_bottom

    min_score = max(0, min(scores) - 5)
    max_score = max(scores) + 5
    score_range = max(1, max_score - min_score)

    x_step = chart_w / (n - 1) if n > 1 else chart_w

    def _x(i: int) -> float:
        return pad_left + i * x_step

    def _y(s: float) -> float:
        return pad_top + chart_h - ((s - min_score) / score_range) * chart_h

    points = " ".join(f"{_x(i)},{_y(s):.1f}" for i, s in enumerate(scores))
    area_points = f"{_x(0)},{pad_top + chart_h} {points} {_x(n - 1)},{pad_top + chart_h}"

    last_x = _x(n - 1)
    last_y = _y(scores[-1])

    # Date labels (first, middle-ish, last)
    date_labels = []
    if n >= 3:
        for idx in [0, n // 2, n - 1]:
            d = dates[idx]
            label = d[5:] if len(d) >= 7 else d
            date_labels.append(
                f'<text x="{_x(idx):.1f}" y="86" text-anchor="middle" class="sparkline-label">{_h(label)}</text>'
            )
    else:
        d = dates[-1]
        label = d[5:] if len(d) >= 7 else d
        date_labels.append(f'<text x="{last_x:.1f}" y="86" text-anchor="middle" class="sparkline-label">{_h(label)}</text>')

    y_labels = [
        f'<text x="{pad_left - 6}" y="{pad_top + chart_h + 3}" text-anchor="end" class="sparkline-label">{min_score:.0f}</text>',
        f'<text x="{pad_left - 6}" y="{pad_top + 3}" text-anchor="end" class="sparkline-label">{max_score:.0f}</text>',
    ]

    grid_lines = [
        f'<line x1="{pad_left}" y1="{pad_top}" x2="{pad_left + chart_w}" y2="{pad_top}" class="sparkline-grid"/>',
        f'<line x1="{pad_left}" y1="{pad_top + chart_h / 2}" x2="{pad_left + chart_w}" y2="{pad_top + chart_h / 2}" class="sparkline-grid"/>',
        f'<line x1="{pad_left}" y1="{pad_top + chart_h}" x2="{pad_left + chart_w}" y2="{pad_top + chart_h}" class="sparkline-grid"/>',
    ]

    display = "block" if visible else "none"

    return (
        f'<div class="sparkline-wrap sparkline-{_h(ticker)}" id="sparkline-{_h(ticker)}-{range_label}" style="display:{display}">'
        f'  <div class="sparkline-header">'
        f'    <div class="sparkline-title">📈 Score Trend ({_h(range_label)})</div>'
        f'    <div style="font-size:0.75rem;color:var(--text-muted)">{_h(n)} data points</div>'
        f'  </div>'
        f'  <svg class="sparkline-svg" viewBox="0 0 600 90" preserveAspectRatio="none">'
        f'    {"".join(grid_lines)}'
        f'    <polygon points="{area_points}" class="sparkline-area"/>'
        f'    <polyline points="{points}" class="sparkline-path"/>'
        f'    <circle cx="{last_x:.1f}" cy="{last_y:.1f}" class="sparkline-dot"/>'
        f'    {"".join(y_labels)}'
        f'    {"".join(date_labels)}'
        f'  </svg>'
        f'</div>'
    )


def _render_market_panel(
    ticker: str,
    quote: Dict[str, Any] | None,
    charts: Dict[str, List[Dict[str, Any]]] | None,
    etoro_enabled: bool,
) -> str:
    """eToro-style live quote header + intraday candlestick chart."""
    if not charts:
        if etoro_enabled and quote and not quote.get("error"):
            return _render_quote_only(ticker, quote)
        return (
            '<p style="color:var(--text-muted);font-size:0.85rem">'
            "Market chart data unavailable for this ticker."
            "</p>"
        )

    from src.collectors.market_chart_collector import TIMEFRAMES

    available = [lbl for lbl in TIMEFRAMES if lbl in charts and charts[lbl]]
    if not available:
        return '<p style="color:var(--text-muted);font-size:0.85rem">No candle data for this symbol.</p>'

    default_range = "1D" if "1D" in available else available[0]
    parts: List[str] = ['<div class="market-panel">']

    if quote and not quote.get("error"):
        parts.append(_render_quote_header(ticker, quote))
    elif quote and quote.get("error"):
        parts.append(
            f'<p style="color:var(--text-muted);font-size:0.82rem">eToro: {_h(quote["error"])}</p>'
        )

    parts.append('<div class="range-buttons">')
    for label in available:
        active = "active" if label == default_range else ""
        parts.append(
            f'<button id="mkt-btn-{_h(ticker)}-{_h(label)}" '
            f'class="range-btn mkt-btn-{_h(ticker)} {active}" '
            f'onclick="showMarketRange(\'{_h(ticker)}\', \'{_h(label)}\')">{_h(label)}</button>'
        )
    parts.append("</div>")

    parts.append(
        f'<div class="market-canvas-wrap">'
        f'<canvas id="market-canvas-{_h(ticker)}" class="market-canvas" '
        f'aria-label="Price chart for {_h(ticker)}"></canvas>'
        f"</div>"
    )

    source_bits = ["Yahoo Finance OHLC"]
    if quote and not quote.get("error"):
        source_bits.insert(0, "eToro bid/ask")
    parts.append(f'<p class="market-source">Data: {" · ".join(source_bits)}</p>')
    parts.append("</div>")
    return "\n".join(parts)


def _render_quote_header(ticker: str, quote: Dict[str, Any]) -> str:
    name = quote.get("display_name") or ticker
    last = quote.get("last") or quote.get("ask") or quote.get("bid")
    change = quote.get("change_pct", 0) or 0
    change_cls = "up" if change >= 0 else "down"
    sign = "+" if change >= 0 else ""
    logo = quote.get("logo_url") or ""
    bid = quote.get("bid")
    ask = quote.get("ask")
    exchange = quote.get("exchange") or ""

    logo_html = (
        f'<img class="market-logo" src="{_h(logo)}" alt="{_h(name)}" loading="lazy">'
        if logo
        else ""
    )
    bid_ask = ""
    if bid is not None and ask is not None:
        spread = round(ask - bid, 4) if ask and bid else 0
        bid_ask = (
            f'<div class="market-bid-ask">'
            f"<span>Bid <strong>{bid}</strong></span>"
            f"<span>Ask <strong>{ask}</strong></span>"
            f"<span>Spread <strong>{spread}</strong></span>"
            f"</div>"
        )

    exchange_suffix = f" · {_h(exchange)}" if exchange else ""
    return (
        f'<div class="market-header">'
        f"{logo_html}"
        f'<div class="market-price-block">'
        f'<div style="font-size:0.85rem;color:var(--text-muted)">{_h(name)} · {_h(ticker)}{exchange_suffix}</div>'
        f'<div class="market-last">{last if last is not None else "—"}</div>'
        f'<div class="market-change {change_cls}">{sign}{change}% today</div>'
        f"{bid_ask}"
        f"</div></div>"
    )


def _render_quote_only(ticker: str, quote: Dict[str, Any]) -> str:
    return f'<div class="market-panel">{_render_quote_header(ticker, quote)}</div>'


def _render_ticker_charts(ticker: str, history: List[Dict[str, Any]]) -> str:
    """Render range selector buttons + sparklines for composite score history."""
    if not history or len(history) < 2:
        return (
            '<p style="color:var(--text-muted);font-size:0.85rem">'
            "Not enough daily runs yet for score trend (needs 2+ pipeline runs)."
            "</p>"
        )

    total = len(history)
    ranges = [
        ("30D", min(total, 30)),
        ("10D", min(total, 10)),
        ("7D", min(total, 7)),
    ]

    parts: List[str] = ['<div class="range-buttons">']
    for label, count in ranges:
        if count < 2:
            continue
        active = "active" if label == "30D" else ""
        parts.append(
            f'<button id="btn-{_h(ticker)}-{label}" class="range-btn btn-{_h(ticker)} {active}" '
            f'onclick="showRange(\'{_h(ticker)}\', \'{label}\')">{label}</button>'
        )
    parts.append("</div>")

    for label, count in ranges:
        if count < 2:
            continue
        subset = history[-count:]
        visible = label == "30D"
        parts.append(_sparkline_svg(ticker, subset, label, visible))

    return "\n".join(parts)


# ── Main generator ───────────────────────────────────────────────────────────


def generate(
    ranked: List[Dict[str, Any]],
    topics: List[Tuple[str, int]],
    spiking_topics: List[Dict[str, Any]],
    posts: List[Dict[str, Any]],
    articles: List[Dict[str, Any]],
    chart_paths: List[Path],
    cost: Dict[str, Any] | None = None,
    verification: List[Dict[str, Any]] | None = None,
    market_data: Dict[str, Any] | None = None,
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

    # Load historical data for sparklines
    ticker_history = _load_history()
    market_data = market_data or {}
    etoro_quotes: Dict[str, Any] = market_data.get("quotes") or {}
    market_charts: Dict[str, Any] = market_data.get("charts") or {}
    etoro_enabled = bool(market_data.get("etoro_enabled"))

    parts: List[str] = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '  <meta charset="UTF-8">',
        '  <meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f'  <title>Market Intelligence Dashboard — {ts}</title>',
        '  <style>',
        _CSS,
        '  </style>',
        '</head>',
        '<body>',
        f'  <h1 id="top">📈 Market Intelligence Dashboard</h1>',
        f'  <p>Generated: <strong>{_h(ts)}</strong></p>',
        '  <div class="card">',
        '    <h2>📊 Top-10 Investment Picks</h2>',
        '    <table>',
        '      <tr><th>Rank</th><th>Ticker</th><th>Score</th><th>Price</th><th>Change %</th><th>Sentiment</th><th>Signal</th><th>Change</th></tr>',
    ]

    for item in ranked:
        ticker = item["ticker"]
        score = item.get("composite_score", 0)
        price = item.get("price", "—")
        change = item.get("change_pct", "—")
        sentiment = item.get("avg_sentiment_label", "neutral")
        signal = item.get("kimi_signal", "") or item.get("ai_analysis", {}).get("signal", "WATCH")
        rank_change = item.get("rank_change", "—")
        sentiment_cls = "bullish" if sentiment == "bullish" else "bearish" if sentiment == "bearish" else "neutral"
        parts.append(
            f'      <tr>'
            f'<td>{item["rank"]}</td>'
            f'<td><a href="#ticker-{_h(ticker)}" class="ticker-link">{_h(ticker)}</a></td>'
            f'<td class="score">{score}</td>'
            f'<td>{price}</td>'
            f'<td>{change}</td>'
            f'<td class="{sentiment_cls}">{sentiment.capitalize()}</td>'
            f'<td><span class="badge {_badge_class(signal)}">{_h(signal)}</span></td>'
            f'<td>{_h(str(rank_change))}</td>'
            f'</tr>'
        )

    parts += [
        '    </table>',
        '  </div>',
    ]

    # Charts
    valid_charts = [c for c in chart_paths if c and c.exists() and c.name]
    if valid_charts:
        parts += ['  <div class="grid">']
        for chart in valid_charts:
            rel = chart.name
            parts += [
                '    <div class="card">',
                f'      <img src="{_h(rel)}" class="chart" alt="{_h(rel)}">',
                '    </div>',
            ]
        parts += ["  </div>"]

    # ── Per-ticker detail cards ────────────────────────────────────────────
    if ranked:
        parts += ['  <h2 id="details">📋 Ticker Details & Trends</h2>']

        for item in ranked:
            ticker = item["ticker"]
            score = item.get("composite_score", 0)
            price = item.get("price", "—")
            change = item.get("change_pct", "—")
            sentiment = item.get("avg_sentiment_label", "neutral").capitalize()
            signal = item.get("kimi_signal", "") or item.get("ai_analysis", {}).get("signal", "WATCH")
            compound = item.get("avg_sentiment", 0.0)
            ai = item.get("ai_analysis", {})
            history = ticker_history.get(ticker, [])

            parts += [
                f'  <div class="card ticker-detail" id="ticker-{_h(ticker)}">',
                f'    <div class="ticker-detail-header">',
                f'      <div class="ticker-detail-symbol">{_h(ticker)}</div>',
                f'      <div class="ticker-detail-meta">',
            ]
            if price is not None:
                parts.append(f'        <span>💵 ${price} &nbsp;|&nbsp; 📊 {change}%</span>')
            parts += [
                f'        <span class="badge badge-{sentiment.lower()}">{sentiment}</span>',
                f'        <span class="badge {_badge_class(signal)}">{_h(signal)}</span>',
                f'        <span class="score">Score: {score}</span>',
                f'      </div>',
                f'    </div>',
            ]

            # Live market chart (eToro-style)
            parts.append(f'    <h3>💹 Market</h3>')
            parts.append(
                _render_market_panel(
                    ticker,
                    etoro_quotes.get(ticker.upper()) or etoro_quotes.get(ticker),
                    market_charts.get(ticker.upper()) or market_charts.get(ticker),
                    etoro_enabled,
                )
            )

            # Composite score trend
            parts.append(f'    <h3>📈 Score Trend (daily runs)</h3>')
            parts.append(_render_ticker_charts(ticker, history))

            # Sentiment
            parts += [
                f'    <h3>🎭 Sentiment</h3>',
                f'    <p><strong>Compound:</strong> {compound:.3f} &nbsp;|&nbsp; <strong>Label:</strong> {sentiment}</p>',
            ]

            # AI Thesis
            if ai.get("thesis"):
                parts += [
                    f'    <h3>🗣️ What the Market Is Saying</h3>',
                    f'    <p>{_h(ai["thesis"])}</p>',
                ]

            # Catalysts
            if ai.get("catalysts"):
                parts += [f'    <h3>🚀 Catalysts</h3>', '<ul>']
                for c in ai["catalysts"]:
                    parts.append(f'      <li>{_h(c)}</li>')
                parts += ['</ul>']

            # Risks
            if ai.get("risks"):
                parts += [f'    <h3>⚠️ Risks</h3>', '<ul>']
                for r in ai["risks"]:
                    parts.append(f'      <li>{_h(r)}</li>')
                parts += ['</ul>']

            # Evidence links
            if item.get("news_sources"):
                parts += [f'    <h3>📰 Sources</h3>', '<ul>']
                for src in item["news_sources"][:5]:
                    title = src.get("title", "Source")
                    url = src.get("url", "")
                    if url:
                        parts.append(f'      <li><a href="{_h(url)}" target="_blank" rel="noopener">{_h(title)}</a></li>')
                    else:
                        parts.append(f'      <li>{_h(title)}</li>')
                parts += ['</ul>']

            parts += [
                f'    <a href="#top" class="back-to-top">↑ Back to top</a>',
                f'  </div>',
            ]

    # Spiking topics
    if spiking_topics:
        parts += [
            '  <div class="card">',
            '    <h2>🚀 Spiking Topics (Emerging)</h2>',
            '    <table>',
            '      <tr><th>Topic</th><th>Today</th><th>7-Day Avg</th><th>Z-Score</th></tr>',
        ]
        for st in spiking_topics[:10]:
            parts.append(
                f'      <tr>'
                f'<td>{_h(st["topic"])}</td>'
                f'<td>{st["today_count"]}</td>'
                f'<td>{st["rolling_mean"]}</td>'
                f'<td>{st["z_score"]}</td>'
                f'</tr>'
            )
        parts += ['    </table>', '  </div>']

    # Top topics
    parts += [
        '  <div class="card">',
        '    <h2>🔥 Trending Topics</h2>',
    ]
    for topic, score in topics[:20]:
        parts.append(f'    <span class="tag">{_h(topic)} ({score})</span>')
    parts += ['  </div>']

    # Source highlights
    parts += [
        '  <div class="card">',
        '    <h2>📰 News Highlights</h2>',
        '    <ul>',
    ]
    for article in articles[:8]:
        title = article.get("title", "")
        url = article.get("url", "")
        source = article.get("source", "")
        if title:
            link = f'<a href="{_h(url)}" target="_blank" rel="noopener">{_h(title)}</a>' if url else _h(title)
            parts.append(f'      <li><strong>[{_h(source)}]</strong> {link}</li>')
    parts += ['    </ul>', '  </div>']

    # Cost & Verification
    if cost:
        parts += [
            '  <div class="card">',
            '    <h2>💰 Cost & Token Usage</h2>',
            '    <table>',
            '      <tr><th>Metric</th><th>Value</th></tr>',
            f'      <tr><td>Total API calls</td><td>{cost.get("total_calls", 0)}</td></tr>',
            f'      <tr><td>Input tokens</td><td>{cost.get("total_input_tokens", 0):,}</td></tr>',
            f'      <tr><td>Output tokens</td><td>{cost.get("total_output_tokens", 0):,}</td></tr>',
            f'      <tr><td><strong>Total cost</strong></td><td><strong>${cost.get("total_cost_usd", 0)}</strong></td></tr>',
        ]
        for provider, data in cost.get("by_provider", {}).items():
            parts.append(
                f'      <tr><td>{_h(provider.capitalize())} ({data["calls"]} calls)</td>'
                f'<td>${data["cost_usd"]}</td></tr>'
            )
        parts += ['    </table>', '  </div>']

    if verification:
        parts += [
            '  <div class="card">',
            '    <h2>✅ Verification Checklist</h2>',
            '    <table>',
            '      <tr><th>#</th><th>Goal</th><th>Status</th><th>Count</th></tr>',
        ]
        for i, item in enumerate(verification, start=1):
            status = "✅" if item.get("status") else "❌"
            parts.append(
                f'      <tr><td>{i}</td><td>{_h(item["goal"])}</td>'
                f'<td>{status}</td><td>{item.get("count", 0)}</td></tr>'
            )
        passed = sum(1 for v in verification if v.get("status"))
        parts += [
            '    </table>',
            f'    <p><strong>{passed}/{len(verification)} goals achieved.</strong></p>',
            '  </div>',
        ]

    # Embedded market chart JSON for client-side rendering
    if market_charts:
        parts += [
            "  <script>",
            "window.MARKET_CHARTS = ",
            json.dumps(market_charts),
            ";",
            "  </script>",
        ]

    # Footer
    parts += [
        '  <div class="card">',
        '    <p><em>This dashboard is generated automatically for informational purposes only. '
        'It does not constitute financial advice.</em></p>',
        '  </div>',
        '  <script>',
        _JS,
        '  </script>',
        '</body>',
        '</html>',
    ]

    out = output_path or (Path("outputs") / f"dashboard_{datetime.now(tz=timezone.utc).strftime('%Y%m%d_%H%M%S')}.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(parts), encoding="utf-8")
    logger.info("HTML dashboard saved to %s", out)
    return out
