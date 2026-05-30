"""
HTML reporter — formats the pipeline results into a visually rich HTML report.

Includes per-ticker SVG sparkline trend charts, animated score bars,
sentiment gauges, and collapsible cards.

SECURITY NOTES
--------------
• Only writes to the configured outputs directory.
• HTML-escapes all user-facing content.
• No eval/exec of dynamic content.
• URL validation uses the same _is_safe_url() as the Markdown reporter.
"""

from __future__ import annotations

import html as html_module
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

from src.reporters.investment_reporter import _is_safe_url, _signal_for, _emoji

logger = logging.getLogger(__name__)

_OUTPUTS_DIR = Path(__file__).resolve().parents[2] / "outputs"
_TICKER_HISTORY_FILE = _OUTPUTS_DIR / "ticker_score_history.json"

# ── CSS ──────────────────────────────────────────────────────────────────────

_CSS = """
:root {
  --bg: #f8f9fa;
  --card-bg: #ffffff;
  --text: #212529;
  --text-muted: #6c757d;
  --border: #dee2e6;
  --primary: #0d6efd;
  --success: #198754;
  --warning: #ffc107;
  --danger: #dc3545;
  --info: #0dcaf0;
  --accent: #6610f2;
  --shadow: 0 4px 20px rgba(0,0,0,0.08);
  --radius: 14px;
  --font: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  --font-mono: 'SF Mono', Monaco, Inconsolata, monospace;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0f1115;
    --card-bg: #1a1d24;
    --text: #e9ecef;
    --text-muted: #adb5bd;
    --border: #2d333b;
    --primary: #6ea8fe;
    --success: #75b798;
    --warning: #ffda6a;
    --danger: #ea868f;
    --info: #6edff6;
    --accent: #a27de3;
    --shadow: 0 4px 20px rgba(0,0,0,0.4);
  }
}

* { box-sizing: border-box; }

body {
  margin: 0;
  padding: 0;
  font-family: var(--font);
  background: var(--bg);
  color: var(--text);
  line-height: 1.6;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 32px 24px;
}

/* ── Header ──────────────────────────────────────────────────────────────── */
.header {
  text-align: center;
  padding: 48px 0 32px;
  border-bottom: 2px solid var(--border);
  margin-bottom: 32px;
}
.header h1 {
  font-size: 2.4rem;
  font-weight: 800;
  margin: 0 0 8px;
  letter-spacing: -0.5px;
}
.header .subtitle {
  color: var(--text-muted);
  font-size: 1rem;
  margin-bottom: 12px;
}
.header .disclaimer {
  font-size: 0.85rem;
  color: var(--text-muted);
  font-style: italic;
  max-width: 700px;
  margin: 0 auto;
}

/* ── Live indicator ──────────────────────────────────────────────────────── */
.live-indicator {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.78rem;
  color: var(--success);
  font-weight: 600;
}
.live-dot {
  width: 8px;
  height: 8px;
  background: var(--success);
  border-radius: 50%;
  animation: pulse 2s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.8); }
}

/* ── Cards ───────────────────────────────────────────────────────────────── */
.card {
  background: var(--card-bg);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 28px;
  margin-bottom: 28px;
  border: 1px solid var(--border);
}

.card h2 {
  margin: 0 0 20px;
  font-size: 1.35rem;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 10px;
}

.card h3 {
  margin: 0 0 14px;
  font-size: 1.15rem;
  font-weight: 600;
}

/* ── Tables ──────────────────────────────────────────────────────────────── */
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.92rem;
}

th, td {
  padding: 12px 14px;
  text-align: left;
  border-bottom: 1px solid var(--border);
}

th {
  font-weight: 700;
  color: var(--text-muted);
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  background: transparent;
}

tr:hover td {
  background: rgba(13, 110, 253, 0.04);
}

/* ── Badges ──────────────────────────────────────────────────────────────── */
.badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.badge-buy  { background: rgba(25, 135, 84, 0.12); color: var(--success); }
.badge-hold { background: rgba(255, 193, 7, 0.15); color: #d4a017; }
.badge-watch{ background: rgba(13, 202, 240, 0.12); color: var(--info); }
.badge-sell { background: rgba(220, 53, 69, 0.12); color: var(--danger); }

.badge-bullish { background: rgba(25, 135, 84, 0.12); color: var(--success); }
.badge-bearish { background: rgba(220, 53, 69, 0.12); color: var(--danger); }
.badge-neutral { background: rgba(108, 117, 125, 0.12); color: var(--text-muted); }

/* ── Score Bars ──────────────────────────────────────────────────────────── */
.score-bar-container {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 16px 0;
}

.score-bar-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.score-bar-label {
  width: 130px;
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-muted);
  text-align: right;
  flex-shrink: 0;
}

.score-bar-track {
  flex: 1;
  height: 22px;
  background: var(--border);
  border-radius: 11px;
  overflow: hidden;
  position: relative;
}

.score-bar-fill {
  height: 100%;
  border-radius: 11px;
  transition: width 1.2s cubic-bezier(0.22, 1, 0.36, 1);
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding-right: 8px;
  font-size: 0.72rem;
  font-weight: 700;
  color: #fff;
  text-shadow: 0 1px 2px rgba(0,0,0,0.3);
  min-width: 30px;
}

.score-bar-value {
  width: 50px;
  font-size: 0.82rem;
  font-weight: 700;
  text-align: left;
  flex-shrink: 0;
}

.bar-news   { background: linear-gradient(90deg, #0d6efd, #0dcaf0); }
.bar-social { background: linear-gradient(90deg, #6610f2, #a27de3); }
.bar-sent   { background: linear-gradient(90deg, #198754, #75b798); }
.bar-mom    { background: linear-gradient(90deg, #fd7e14, #ffc107); }
.bar-ai     { background: linear-gradient(90deg, #dc3545, #ea868f); }

/* ── Sparkline ───────────────────────────────────────────────────────────── */
.sparkline-wrap {
  background: var(--bg);
  border-radius: 10px;
  padding: 16px 20px;
  border: 1px solid var(--border);
  margin: 10px 0;
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

.sparkline-range {
  font-size: 0.75rem;
  color: var(--text-muted);
  font-family: var(--font-mono);
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
  stroke-dasharray: 1000;
  stroke-dashoffset: 1000;
  transition: stroke-dashoffset 1.5s cubic-bezier(0.22, 1, 0.36, 1);
}

.sparkline-area {
  fill: rgba(13, 110, 253, 0.08);
  stroke: none;
}

.sparkline-dot {
  fill: var(--primary);
  stroke: var(--card-bg);
  stroke-width: 2.5;
  r: 4;
  animation: dotPulse 2s infinite;
}

@keyframes dotPulse {
  0%, 100% { r: 4; }
  50% { r: 5.5; }
}

.sparkline-axis {
  stroke: var(--border);
  stroke-width: 1;
}

.sparkline-label {
  font-size: 9px;
  fill: var(--text-muted);
  font-family: var(--font-mono);
}

.sparkline-grid {
  stroke: var(--border);
  stroke-width: 0.5;
  stroke-dasharray: 2,2;
  opacity: 0.5;
}

/* ── Ticker Cards ────────────────────────────────────────────────────────── */
.ticker-card {
  background: var(--card-bg);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  margin-bottom: 24px;
  border: 1px solid var(--border);
  overflow: hidden;
}

.ticker-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 28px;
  background: linear-gradient(135deg, rgba(13,110,253,0.05), rgba(102,16,242,0.05));
  border-bottom: 1px solid var(--border);
  cursor: pointer;
  transition: background 0.2s;
}
.ticker-header:hover {
  background: linear-gradient(135deg, rgba(13,110,253,0.08), rgba(102,16,242,0.08));
}

.ticker-header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.ticker-symbol {
  font-size: 1.6rem;
  font-weight: 800;
  letter-spacing: -0.5px;
}

.ticker-meta {
  display: flex;
  align-items: center;
  gap: 16px;
  color: var(--text-muted);
  font-size: 0.9rem;
}

.ticker-score-wrap {
  display: flex;
  align-items: center;
  gap: 12px;
}

.ticker-score {
  font-size: 1.8rem;
  font-weight: 800;
  color: var(--primary);
}

.ticker-body {
  padding: 24px 28px;
}

.ticker-section {
  margin-bottom: 20px;
}
.ticker-section:last-child { margin-bottom: 0; }

.ticker-section-title {
  font-size: 0.85rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted);
  margin-bottom: 10px;
}

/* ── Sentiment Gauge ─────────────────────────────────────────────────────── */
.sentiment-gauge {
  display: flex;
  align-items: center;
  gap: 16px;
  margin: 10px 0;
}

.sentiment-track {
  flex: 1;
  height: 10px;
  background: linear-gradient(90deg, var(--danger), var(--warning), var(--success));
  border-radius: 5px;
  position: relative;
}

.sentiment-marker {
  position: absolute;
  top: -5px;
  width: 20px;
  height: 20px;
  background: var(--card-bg);
  border: 3px solid var(--text);
  border-radius: 50%;
  transform: translateX(-50%);
  transition: left 1s cubic-bezier(0.22, 1, 0.36, 1);
}

.sentiment-labels {
  display: flex;
  justify-content: space-between;
  font-size: 0.72rem;
  color: var(--text-muted);
  margin-top: 4px;
}

/* ── Source Links ────────────────────────────────────────────────────────── */
.source-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.source-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 8px;
  background: rgba(13, 110, 253, 0.06);
  border: 1px solid rgba(13, 110, 253, 0.15);
  color: var(--primary);
  text-decoration: none;
  font-size: 0.82rem;
  font-weight: 500;
  transition: all 0.15s;
}
.source-link:hover {
  background: rgba(13, 110, 253, 0.12);
  border-color: var(--primary);
  transform: translateY(-1px);
}

/* ── Narrative Block ─────────────────────────────────────────────────────── */
.narrative {
  background: linear-gradient(135deg, rgba(13,110,253,0.04), rgba(102,16,242,0.04));
  border-left: 4px solid var(--primary);
  padding: 16px 20px;
  border-radius: 0 10px 10px 0;
  font-style: italic;
  color: var(--text);
  margin: 10px 0;
}

/* ── Cost Cards ──────────────────────────────────────────────────────────── */
.cost-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin: 16px 0;
}

.cost-card {
  background: var(--bg);
  border-radius: 10px;
  padding: 20px;
  text-align: center;
  border: 1px solid var(--border);
}

.cost-card-value {
  font-size: 1.8rem;
  font-weight: 800;
  color: var(--primary);
  margin: 4px 0;
}

.cost-card-label {
  font-size: 0.8rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
}

/* ── Topic Tags ──────────────────────────────────────────────────────────── */
.topic-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.topic-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 20px;
  background: var(--bg);
  border: 1px solid var(--border);
  font-size: 0.85rem;
  font-weight: 500;
}

/* ── Collapsible ─────────────────────────────────────────────────────────── */
.collapse-icon {
  font-size: 1.2rem;
  transition: transform 0.3s;
  color: var(--text-muted);
}
.ticker-card.collapsed .ticker-body { display: none; }
.ticker-card.collapsed .collapse-icon { transform: rotate(-90deg); }

/* ── Footer ──────────────────────────────────────────────────────────────── */
.footer {
  text-align: center;
  padding: 32px 0;
  color: var(--text-muted);
  font-size: 0.85rem;
  border-top: 1px solid var(--border);
  margin-top: 32px;
}

/* ── Responsive ──────────────────────────────────────────────────────────── */
@media (max-width: 768px) {
  .container { padding: 16px; }
  .header h1 { font-size: 1.6rem; }
  .ticker-header { flex-direction: column; align-items: flex-start; gap: 10px; }
  .score-bar-label { width: 100px; font-size: 0.75rem; }
  .cost-grid { grid-template-columns: 1fr 1fr; }
}
"""

_JS = """
function toggleTicker(card) {
  card.classList.toggle('collapsed');
  // Animate sparkline when card opens
  if (!card.classList.contains('collapsed')) {
    const svg = card.querySelector('.sparkline-svg');
    if (svg) {
      const path = svg.querySelector('.sparkline-path');
      if (path) {
        path.style.strokeDashoffset = '1000';
        setTimeout(function() {
          path.style.strokeDashoffset = '0';
        }, 100);
      }
    }
  }
}

// Animate score bars and sparklines on load
document.addEventListener('DOMContentLoaded', function() {
  const bars = document.querySelectorAll('.score-bar-fill');
  bars.forEach(function(bar) {
    const target = bar.getAttribute('data-width');
    bar.style.width = '0%';
    setTimeout(function() {
      bar.style.width = target + '%';
    }, 100);
  });

  // Animate sentiment markers
  const markers = document.querySelectorAll('.sentiment-marker');
  markers.forEach(function(marker) {
    const target = marker.getAttribute('data-pos');
    marker.style.left = '50%';
    setTimeout(function() {
      marker.style.left = target + '%';
    }, 200);
  });

  // Animate visible sparklines on load
  const sparklines = document.querySelectorAll('.sparkline-path');
  sparklines.forEach(function(path) {
    path.style.strokeDashoffset = '1000';
    setTimeout(function() {
      path.style.strokeDashoffset = '0';
    }, 300);
  });
});
"""


# ── Helper functions ─────────────────────────────────────────────────────────


def _h(text: str) -> str:
    """HTML-escape a string."""
    return html_module.escape(str(text))


def _badge(signal: str) -> str:
    """Return a CSS class for a signal badge."""
    sig = signal.upper()
    mapping = {
        "BUY": "badge-buy",
        "HOLD": "badge-hold",
        "WATCH": "badge-watch",
        "SELL": "badge-sell",
    }
    return mapping.get(sig, "badge-watch")


def _sentiment_badge(label: str) -> str:
    """Return a CSS class for a sentiment badge."""
    lbl = label.lower()
    mapping = {
        "bullish": "badge-bullish",
        "bearish": "badge-bearish",
        "neutral": "badge-neutral",
    }
    return mapping.get(lbl, "badge-neutral")


def _score_bar(label: str, weight_pct: int, raw_score: float, bar_class: str) -> str:
    """Render a single animated score bar."""
    width = max(0, min(100, raw_score))
    contribution = round(raw_score * weight_pct / 100, 1)
    return (
        f'<div class="score-bar-row">'
        f'  <div class="score-bar-label">{_h(label)}</div>'
        f'  <div class="score-bar-track">'
        f'    <div class="score-bar-fill {bar_class}" data-width="{width:.1f}">'
        f'      ~{contribution}'
        f'    </div>'
        f'  </div>'
        f'  <div class="score-bar-value">{raw_score:.1f}</div>'
        f'</div>'
    )


def _sentiment_gauge(compound: float) -> str:
    """Render a sentiment gauge with a marker."""
    pos = max(0, min(100, (compound + 1) / 2 * 100))
    return (
        f'<div class="sentiment-gauge">'
        f'  <div style="flex:1">'
        f'    <div class="sentiment-track">'
        f'      <div class="sentiment-marker" data-pos="{pos:.1f}"></div>'
        f'    </div>'
        f'    <div class="sentiment-labels">'
        f'      <span>Bearish (-1.0)</span>'
        f'      <span>Neutral (0)</span>'
        f'      <span>Bullish (+1.0)</span>'
        f'    </div>'
        f'  </div>'
        f'</div>'
    )


def _source_links(sources: List[Dict[str, Any]], key: str = "title") -> str:
    """Render source links as a grid of clickable tags."""
    if not sources:
        return ""
    parts: List[str] = ['<div class="source-grid">']
    for src in sources[:5]:
        text = src.get(key, "Source") or "Source"
        url = src.get("url", "")
        icon = "🔗" if key == "title" else "🐦" if key == "text" else "▶️"
        if _is_safe_url(url):
            parts.append(
                f'<a class="source-link" href="{_h(url)}" target="_blank" rel="noopener">'
                f'{icon} {_h(text[:60])}</a>'
            )
        else:
            parts.append(f'<span class="source-link" style="opacity:0.6">{icon} {_h(text[:60])}</span>')
    parts.append("</div>")
    return "\n".join(parts)


def _snippet_list(snippets: List[str], icon: str = "•") -> str:
    """Render a list of text snippets."""
    if not snippets:
        return ""
    parts: List[str] = ['<ul style="margin:8px 0;padding-left:20px">']
    for snippet in snippets[:3]:
        parts.append(f'<li>{_h(snippet)}</li>')
    parts.append("</ul>")
    return "\n".join(parts)


# ── Sparkline generator ──────────────────────────────────────────────────────


def _sparkline_svg(history: List[Dict[str, Any]], width: int = 600, height: int = 90) -> str:
    """
    Generate an inline SVG sparkline from a ticker's score history.

    Args:
        history: List of dicts with 'date' (YYYY-MM-DD) and 'composite_score'.
        width: SVG width in pixels.
        height: SVG height in pixels.

    Returns:
        SVG string.
    """
    if not history or len(history) < 2:
        return ""

    # Extract data points
    entries = sorted(history, key=lambda x: x.get("date", ""))
    scores = [e.get("composite_score", 0) or 0 for e in entries]
    dates = [e.get("date", "") for e in entries]

    if not scores:
        return ""

    # Padding
    pad_left = 40
    pad_right = 20
    pad_top = 15
    pad_bottom = 20
    chart_w = width - pad_left - pad_right
    chart_h = height - pad_top - pad_bottom

    # Scale
    min_score = max(0, min(scores) - 5)
    max_score = max(scores) + 5
    score_range = max(1, max_score - min_score)

    n = len(scores)
    if n == 1:
        x_step = chart_w
    else:
        x_step = chart_w / (n - 1)

    def _x(i: int) -> float:
        return pad_left + i * x_step

    def _y(score: float) -> float:
        return pad_top + chart_h - ((score - min_score) / score_range) * chart_h

    # Build polyline points
    points = " ".join(f"{_x(i)},{_y(s):.1f}" for i, s in enumerate(scores))

    # Area path (closed polygon for gradient fill)
    area_points = f"{_x(0)},{pad_top + chart_h} {points} {_x(n - 1)},{pad_top + chart_h}"

    # Last point (current)
    last_x = _x(n - 1)
    last_y = _y(scores[-1])

    # Date labels (show first, middle, last)
    date_labels = []
    if n >= 3:
        for idx in [0, n // 2, n - 1]:
            d = dates[idx]
            label = d[5:] if len(d) >= 7 else d  # MM-DD
            date_labels.append(f'<text x="{_x(idx):.1f}" y="{height - 4}" text-anchor="middle" class="sparkline-label">{_h(label)}</text>')
    elif n >= 1:
        d = dates[-1]
        label = d[5:] if len(d) >= 7 else d
        date_labels.append(f'<text x="{last_x:.1f}" y="{height - 4}" text-anchor="middle" class="sparkline-label">{_h(label)}</text>')

    # Y-axis labels (min, mid, max)
    y_labels = [
        f'<text x="{pad_left - 6}" y="{pad_top + chart_h + 3}" text-anchor="end" class="sparkline-label">{min_score:.0f}</text>',
        f'<text x="{pad_left - 6}" y="{pad_top + 3}" text-anchor="end" class="sparkline-label">{max_score:.0f}</text>',
    ]

    # Horizontal grid lines
    grid_lines = [
        f'<line x1="{pad_left}" y1="{pad_top}" x2="{pad_left + chart_w}" y2="{pad_top}" class="sparkline-grid"/>',
        f'<line x1="{pad_left}" y1="{pad_top + chart_h / 2}" x2="{pad_left + chart_w}" y2="{pad_top + chart_h / 2}" class="sparkline-grid"/>',
        f'<line x1="{pad_left}" y1="{pad_top + chart_h}" x2="{pad_left + chart_w}" y2="{pad_top + chart_h}" class="sparkline-grid"/>',
    ]

    svg_parts = [
        f'<div class="sparkline-wrap">',
        f'  <div class="sparkline-header">',
        f'    <div class="sparkline-title">📈 Score Trend (last {len(scores)} runs)</div>',
        f'    <div class="sparkline-range">min {min_score:.0f} → max {max_score:.0f}</div>',
        f'  </div>',
        f'  <svg class="sparkline-svg" viewBox="0 0 {width} {height}" preserveAspectRatio="none">',
        f'    {"".join(grid_lines)}',
        f'    <polygon points="{area_points}" class="sparkline-area"/>',
        f'    <polyline points="{points}" class="sparkline-path"/>',
        f'    <circle cx="{last_x:.1f}" cy="{last_y:.1f}" class="sparkline-dot"/>',
        f'    {"".join(y_labels)}',
        f'    {"".join(date_labels)}',
        f'  </svg>',
        f'</div>',
    ]

    return "\n".join(svg_parts)


# ── Main builder ─────────────────────────────────────────────────────────────


def build_html_report(
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
    Build a visually rich HTML investment report.

    Args:
        topics:       Top trending topics (keyword, score).
        posts:        Raw Reddit posts.
        articles:     Raw news articles.
        ticker_data:  Enriched ticker info from stock_mapper + composite_scorer.
        ranked:       Top-10 ranked tickers.
        spiking_topics: Detected spiking topics.
        run_timestamp: UTC datetime of the pipeline run.
        cost:         Cost breakdown dict.
        verification: Checklist of achieved goals.

    Returns:
        HTML-formatted report as a string.
    """
    ts = run_timestamp or datetime.now(tz=timezone.utc)
    ts_str = ts.strftime("%Y-%m-%d %H:%M UTC")

    # Load ticker score history for sparklines
    ticker_history: Dict[str, List[Dict[str, Any]]] = {}
    if _TICKER_HISTORY_FILE.exists():
        try:
            with _TICKER_HISTORY_FILE.open("r", encoding="utf-8") as f:
                ticker_history = json.load(f)
        except Exception:
            pass

    parts: List[str] = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '  <meta charset="UTF-8">',
        '  <meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f'  <title>Market Intelligence Report — {ts_str}</title>',
        '  <style>',
        _CSS,
        '  </style>',
        '</head>',
        '<body>',
        '  <div class="container">',
        '    <div class="header">',
        '      <h1>📈 Market Intelligence Report</h1>',
        f'      <div class="subtitle">Generated: <strong>{ts_str}</strong></div>',
        '      <div class="disclaimer">',
        '        This report is generated automatically from public Reddit posts, news feeds, ',
        '        social media, and market data. It is for informational purposes only and does ',
        '        not constitute financial advice.',
        '      </div>',
        '    </div>',
    ]

    # ── Top-10 Summary Table ───────────────────────────────────────────────
    if ranked:
        parts += [
            '    <div class="card">',
            '      <h2>📊 Top-10 Investment Picks</h2>',
            '      <p style="color:var(--text-muted);font-size:0.9rem;margin:-8px 0 16px">',
            '        Ranked by composite score (news volume + social engagement + sentiment + price momentum + AI rationale).',
            '      </p>',
            '      <table>',
            '        <tr>',
            '          <th>Rank</th><th>Ticker</th><th>Score</th><th>Price</th>',
            '          <th>Change %</th><th>Sentiment</th><th>Signal</th><th>Δ</th>',
            '        </tr>',
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
            parts.append(
                f'        <tr>'
                f'<td>{item["rank"]}</td>'
                f'<td><strong>{_h(ticker)}</strong></td>'
                f'<td style="font-weight:800;color:var(--primary)">{score}</td>'
                f'<td>${price}</td>'
                f'<td>{change}</td>'
                f'<td><span class="badge {_sentiment_badge(sentiment)}">{sentiment}</span></td>'
                f'<td><span class="badge {_badge(signal)}">{emoji} {signal}</span></td>'
                f'<td>{_h(str(rank_change))}</td>'
                f'</tr>'
            )
        parts += ['      </table>', '    </div>']

        # ── Detailed Ticker Cards ──────────────────────────────────────────
        parts += ['    <h2 style="margin:36px 0 20px;font-size:1.5rem">💡 Why These Stocks?</h2>']

        _BAR_CLASSES = {
            "news_volume": "bar-news",
            "social_engagement": "bar-social",
            "sentiment": "bar-sent",
            "price_momentum": "bar-mom",
            "ai_rationale": "bar-ai",
        }
        _WEIGHTS = {
            "news_volume": 25,
            "social_engagement": 25,
            "sentiment": 25,
            "price_momentum": 15,
            "ai_rationale": 10,
        }

        for item in ranked:
            ticker = item["ticker"]
            score = item.get("composite_score", 0)
            signal = _signal_for(item)
            emoji = _emoji(signal)
            price = item.get("price")
            change = item.get("change_pct")
            compound = item.get("avg_sentiment", 0.0)
            sentiment_label = item.get("avg_sentiment_label", "neutral").capitalize()
            breakdown = item.get("score_breakdown", {})
            ai = item.get("ai_analysis", {})

            # Get sparkline for this ticker
            history = ticker_history.get(ticker, [])
            sparkline_html = _sparkline_svg(history) if len(history) >= 2 else ""

            parts += [
                f'    <div class="ticker-card">',
                f'      <div class="ticker-header" onclick="toggleTicker(this.parentElement)">',
                f'        <div class="ticker-header-left">',
                f'          <div class="ticker-symbol">{_h(ticker)}</div>',
                f'          <div class="ticker-meta">',
            ]
            if price is not None:
                parts.append(f'            <span>💵 ${price} &nbsp;|&nbsp; 📊 {change}%</span>')
            parts += [
                f'            <span class="badge {_sentiment_badge(sentiment_label)}">{sentiment_label}</span>',
                f'            <span class="badge {_badge(signal)}">{emoji} {signal}</span>',
                f'          </div>',
                f'        </div>',
                f'        <div class="ticker-score-wrap">',
            ]
            if sparkline_html:
                parts.append(f'          <div class="live-indicator"><div class="live-dot"></div>Live</div>')
            parts += [
                f'          <div class="ticker-score">{score}</div>',
                f'          <div class="collapse-icon">▼</div>',
                f'        </div>',
                f'      </div>',
                f'      <div class="ticker-body">',
            ]

            # Sparkline trend
            if sparkline_html:
                parts.append(f'        <div class="ticker-section">{sparkline_html}</div>')

            # Score breakdown
            if breakdown:
                parts += [
                    f'        <div class="ticker-section">',
                    f'          <div class="ticker-section-title">📊 Ranking Breakdown</div>',
                    f'          <div class="score-bar-container">',
                ]
                for key, raw_score in breakdown.items():
                    label = key.replace("_", " ").title()
                    weight = _WEIGHTS.get(key, 0)
                    bar_cls = _BAR_CLASSES.get(key, "bar-news")
                    parts.append(_score_bar(label, weight, raw_score, bar_cls))
                parts += [
                    f'          </div>',
                    f'          <p style="font-size:0.8rem;color:var(--text-muted);margin-top:8px">',
                    f'            Weights: News 25% | Social 25% | Sentiment 25% | Momentum 15% | AI 10%',
                    f'          </p>',
                    f'        </div>',
                ]

            # Sentiment detail
            parts += [
                f'        <div class="ticker-section">',
                f'          <div class="ticker-section-title">🎭 Sentiment Analysis</div>',
                f'          <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">',
                f'            <span class="badge {_sentiment_badge(sentiment_label)}">{sentiment_label}</span>',
                f'            <span style="font-family:var(--font-mono);font-size:0.9rem">compound: {compound:.3f}</span>',
                f'          </div>',
                _sentiment_gauge(compound),
            ]
            if compound >= 0.05:
                parts.append(f'          <p style="color:var(--success);font-size:0.9rem;margin-top:8px">✓ Market tone is <strong>positive</strong> — optimistic language in coverage.</p>')
            elif compound <= -0.05:
                parts.append(f'          <p style="color:var(--danger);font-size:0.9rem;margin-top:8px">⚠ Market tone is <strong>negative</strong> — cautious or pessimistic language in coverage.</p>')
            else:
                parts.append(f'          <p style="color:var(--text-muted);font-size:0.9rem;margin-top:8px">● Market tone is <strong>neutral</strong> — mixed or balanced coverage.</p>')
            parts += [f'        </div>']

            # AI Thesis & Market Narrative
            parts += [f'        <div class="ticker-section">']
            parts += [f'          <div class="ticker-section-title">🗣️ What the Market Is Saying</div>']

            if ai.get("thesis"):
                parts.append(f'          <div class="narrative">{_h(ai["thesis"])}</div>')
            elif item.get("llm_rationale"):
                parts.append(f'          <div class="narrative">{_h(item["llm_rationale"])}</div>')
            elif item.get("kimi_rationale"):
                parts.append(f'          <div class="narrative">{_h(item["kimi_rationale"])}</div>')

            if item.get("news_snippets"):
                top_snippet = item["news_snippets"][0]
                parts.append(f'          <p style="font-size:0.9rem;color:var(--text-muted);margin-top:8px"><strong>Recent headline:</strong> &ldquo;{_h(top_snippet)}&rdquo;</p>')

            if not ai.get("thesis") and not item.get("llm_rationale") and not item.get("kimi_rationale") and not item.get("news_snippets"):
                parts.append(f'          <p style="color:var(--text-muted);font-size:0.9rem">No specific market narrative available. Score driven by keyword matching and volume.</p>')

            parts += [f'        </div>']

            # Catalysts
            if ai.get("catalysts"):
                parts += [
                    f'        <div class="ticker-section">',
                    f'          <div class="ticker-section-title">🚀 Catalysts</div>',
                    f'          <ul style="margin:0;padding-left:20px">',
                ]
                for c in ai["catalysts"]:
                    parts.append(f'            <li>{_h(c)}</li>')
                parts += [f'          </ul>', f'        </div>']

            # Risks
            if ai.get("risks"):
                parts += [
                    f'        <div class="ticker-section">',
                    f'          <div class="ticker-section-title">⚠️ Risks</div>',
                    f'          <ul style="margin:0;padding-left:20px">',
                ]
                for r in ai["risks"]:
                    parts.append(f'            <li>{_h(r)}</li>')
                parts += [f'          </ul>', f'        </div>']

            # Evidence & Sources
            if item.get("news_sources"):
                parts += [
                    f'        <div class="ticker-section">',
                    f'          <div class="ticker-section-title">📰 News Sources</div>',
                    _source_links(item["news_sources"][:5], key="title"),
                    f'        </div>',
                ]
            elif item.get("news_snippets"):
                parts += [
                    f'        <div class="ticker-section">',
                    f'          <div class="ticker-section-title">📰 Supporting News</div>',
                    _snippet_list(item["news_snippets"][:3]),
                    f'        </div>',
                ]

            if item.get("reddit_sources"):
                parts += [
                    f'        <div class="ticker-section">',
                    f'          <div class="ticker-section-title">💬 Reddit Sources</div>',
                    _source_links(item["reddit_sources"][:5], key="title"),
                    f'        </div>',
                ]
            elif item.get("reddit_snippets"):
                parts += [
                    f'        <div class="ticker-section">',
                    f'          <div class="ticker-section-title">💬 Reddit Buzz</div>',
                    _snippet_list(item["reddit_snippets"][:3]),
                    f'        </div>',
                ]

            if item.get("twitter_sources"):
                parts += [
                    f'        <div class="ticker-section">',
                    f'          <div class="ticker-section-title">🐦 X/Twitter Sources</div>',
                    _source_links(item["twitter_sources"][:5], key="text"),
                    f'        </div>',
                ]
            elif item.get("twitter_snippets"):
                parts += [
                    f'        <div class="ticker-section">',
                    f'          <div class="ticker-section-title">🐦 Twitter/X Buzz</div>',
                    _snippet_list(item["twitter_snippets"][:3]),
                    f'        </div>',
                ]

            if item.get("youtube_sources"):
                parts += [
                    f'        <div class="ticker-section">',
                    f'          <div class="ticker-section-title">▶️ YouTube Sources</div>',
                    _source_links(item["youtube_sources"][:5], key="title"),
                    f'        </div>',
                ]
            elif item.get("youtube_snippets"):
                parts += [
                    f'        <div class="ticker-section">',
                    f'          <div class="ticker-section-title">▶️ YouTube Mentions</div>',
                    _snippet_list(item["youtube_snippets"][:3]),
                    f'        </div>',
                ]

            parts += [
                f'      </div>',
                f'    </div>',
            ]

    # ── Spiking Topics ─────────────────────────────────────────────────────
    if spiking_topics:
        parts += [
            '    <div class="card">',
            '      <h2>🚀 Spiking Topics (Emerging Trends)</h2>',
            '      <p style="color:var(--text-muted);font-size:0.9rem;margin:-8px 0 16px">Topics rising fast compared to their 7-day rolling average.</p>',
            '      <table>',
            '        <tr><th>Topic</th><th>Today</th><th>7-Day Avg</th><th>Z-Score</th></tr>',
        ]
        for st in spiking_topics[:10]:
            parts.append(
                f'        <tr>'
                f'<td><code>{_h(st["topic"])}</code></td>'
                f'<td>{st["today_count"]}</td>'
                f'<td>{st["rolling_mean"]}</td>'
                f'<td style="font-weight:700">{st["z_score"]}</td>'
                f'</tr>'
            )
        parts += ['      </table>', '    </div>']

    # ── Trending Topics ────────────────────────────────────────────────────
    parts += [
        '    <div class="card">',
        '      <h2>🔥 Top Trending Topics</h2>',
        '      <div class="topic-tags">',
    ]
    for topic, score in topics[:20]:
        parts.append(f'        <span class="topic-tag">{_h(topic)} <strong>{score}</strong></span>')
    parts += ['      </div>', '    </div>']

    # ── News Highlights ────────────────────────────────────────────────────
    parts += [
        '    <div class="card">',
        '      <h2>📰 News Highlights</h2>',
    ]
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for article in articles[:40]:
        src = article.get("source", "Other")
        if article.get("title"):
            grouped.setdefault(src, [])
            if len(grouped[src]) < 4:
                grouped[src].append(article)

    for src, items in list(grouped.items())[:8]:
        parts.append(f'      <h3 style="margin-top:16px">{_h(src)}</h3>')
        parts.append(f'      <div class="source-grid">')
        for art in items:
            title = art.get("title", "")
            url = art.get("url", "")
            if _is_safe_url(url):
                parts.append(
                    f'        <a class="source-link" href="{_h(url)}" target="_blank" rel="noopener">🔗 {_h(title[:70])}</a>'
                )
            else:
                parts.append(f'        <span class="source-link" style="opacity:0.6">{_h(title[:70])}</span>')
        parts.append(f'      </div>')
    parts += ['    </div>']

    # ── Reddit Buzz ────────────────────────────────────────────────────────
    parts += [
        '    <div class="card">',
        '      <h2>💬 Reddit Buzz</h2>',
        '      <p style="color:var(--text-muted);font-size:0.9rem;margin:-8px 0 16px">Top posts by score across financial subreddits.</p>',
        '      <table>',
        '        <tr><th>Subreddit</th><th>Score</th><th>Sentiment</th><th>Title</th></tr>',
    ]
    for post in posts[:10]:
        title = post.get("title", "").strip()
        url = post.get("url", "")
        sub = post.get("subreddit", "")
        score = post.get("score", 0)
        sentiment = post.get("sentiment", {}).get("label", "neutral")
        if title:
            sent_badge = _sentiment_badge(sentiment)
            link = f'<a href="{_h(url)}" target="_blank" rel="noopener">{_h(title[:80])}</a>' if url else _h(title[:80])
            parts.append(
                f'        <tr>'
                f'<td><strong>r/{_h(sub)}</strong></td>'
                f'<td>↑{score:,}</td>'
                f'<td><span class="badge {sent_badge}">{sentiment.capitalize()}</span></td>'
                f'<td>{link}</td>'
                f'</tr>'
            )
    parts += ['      </table>', '    </div>']

    # ── Cost & Verification ────────────────────────────────────────────────
    if cost:
        parts += [
            '    <div class="card">',
            '      <h2>💰 Cost & Token Usage</h2>',
            '      <div class="cost-grid">',
            f'        <div class="cost-card"><div class="cost-card-label">API Calls</div><div class="cost-card-value">{cost.get("total_calls", 0)}</div></div>',
            f'        <div class="cost-card"><div class="cost-card-label">Input Tokens</div><div class="cost-card-value">{cost.get("total_input_tokens", 0):,}</div></div>',
            f'        <div class="cost-card"><div class="cost-card-label">Output Tokens</div><div class="cost-card-value">{cost.get("total_output_tokens", 0):,}</div></div>',
            f'        <div class="cost-card"><div class="cost-card-label">Total Cost</div><div class="cost-card-value">${cost.get("total_cost_usd", 0)}</div></div>',
            '      </div>',
            '      <table style="margin-top:16px">',
            '        <tr><th>Provider</th><th>Calls</th><th>Cost</th></tr>',
        ]
        for provider, data in cost.get("by_provider", {}).items():
            parts.append(
                f'        <tr>'
                f'<td>{_h(provider.capitalize())}</td>'
                f'<td>{data["calls"]}</td>'
                f'<td>${data["cost_usd"]}</td>'
                f'</tr>'
            )
        parts += ['      </table>', '    </div>']

    if verification:
        parts += [
            '    <div class="card">',
            '      <h2>✅ Verification Checklist</h2>',
            '      <table>',
            '        <tr><th>#</th><th>Goal</th><th>Status</th><th>Count</th></tr>',
        ]
        for i, item in enumerate(verification, start=1):
            status = "✅" if item.get("status") else "❌"
            parts.append(
                f'        <tr>'
                f'<td>{i}</td>'
                f'<td>{_h(item["goal"])}</td>'
                f'<td style="font-size:1.1rem">{status}</td>'
                f'<td>{item.get("count", 0)}</td>'
                f'</tr>'
            )
        passed = sum(1 for v in verification if v.get("status"))
        parts += [
            '      </table>',
            f'      <p style="margin-top:12px;font-weight:700">{passed}/{len(verification)} goals achieved.</p>',
            '    </div>',
        ]

    # ── Methodology ────────────────────────────────────────────────────────
    parts += [
        '    <div class="card">',
        '      <h2>ℹ️ Methodology</h2>',
        '      <ol style="line-height:1.9">',
        '        <li><strong>Data collection:</strong> Reddit posts, financial RSS feeds (Yahoo Finance, Reuters, CNBC, MarketWatch, Seeking Alpha, BBC, Al Jazeera), Twitter/X, YouTube, and AI agent swarm.</li>',
        '        <li><strong>Topic extraction:</strong> Keyword-frequency analysis with engagement weighting and editorial weighting.</li>',
        '        <li><strong>Stock mapping:</strong> Curated keyword→ticker dictionary covering 300+ phrases across all major sectors.</li>',
        '        <li><strong>Sentiment analysis:</strong> VADER (local, free) for social-media text; optional LLM for nuanced financial sentiment.</li>',
        '        <li><strong>Composite scoring:</strong> Weighted formula combining news volume (25%), social engagement (25%), sentiment (25%), price momentum (15%), and AI rationale (10%).</li>',
        '        <li><strong>Trend detection:</strong> Z-score spike detection vs 7-day rolling average.</li>',
        '      </ol>',
        '      <p style="color:var(--text-muted);font-size:0.9rem">Run this pipeline daily with GitHub Actions or local scheduler — see <code>config.yaml</code>.</p>',
        '    </div>',
    ]

    # ── Footer ─────────────────────────────────────────────────────────────
    parts += [
        '    <div class="footer">',
        '      <p>Generated by AI Market-to-Invest Pipeline</p>',
        f'      <p>{ts_str}</p>',
        '    </div>',
        '  </div>',
        '  <script>',
        _JS,
        '  </script>',
        '</body>',
        '</html>',
    ]

    return "\n".join(parts)


def save_html_report(report_html: str, output_dir: Path | None = None) -> Path:
    """
    Save the HTML report to a timestamped file.

    Args:
        report_html: HTML report string.
        output_dir: Directory to write into; defaults to ``outputs/``.

    Returns:
        Path to the written file.
    """
    out_dir = output_dir or _OUTPUTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"report_{timestamp}.html"
    path = out_dir / filename
    path.write_text(report_html, encoding="utf-8")
    logger.info("HTML report saved to %s", path)
    return path
