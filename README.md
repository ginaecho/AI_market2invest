# AI Market-to-Invest

> **Collect → Analyse → Invest**  
> A repeatable pipeline that collects news and social-media buzz, scores stocks with a composite AI model, and delivers a ranked Top-10 investment report with price data, sentiment, and clear rationale — every day.

---

## STAR Guide

### Situation
Markets move on narrative. Trump tweets, OPEC cuts, meme-stock surges, geopolitical shocks — by the time you read about them, the move is half over. You need a system that **actively hunts** these signals across Reddit, news RSS, Twitter/X, YouTube, and a **Kimi Agent Swarm** of specialized AI agents (Trump, Geopolitics, Energy, Product Trends, Social Media) — then turns that noise into ranked, actionable stock picks.

### Task
Get a daily **Top-10 Investment Picks** report that tells you:
- Which stocks are trending and why
- Current price and change %
- Sentiment (bullish / bearish / neutral)
- A composite score (0–100) based on news volume + social buzz + sentiment + price momentum + AI rationale
- Clear evidence linking news → ticker → recommendation
- **Cost transparency**: estimated vs actual API spend
- **Verification checklist**: which pipeline stages succeeded

### Action — Get Started in 5 Minutes

**Zero keys required.** The pipeline works 100% with free public sources. Only add API keys if you want AI enrichment.

```bash
# 1. Clone and enter the repo
git clone https://github.com/ginaecho/AI_market2invest.git
cd AI_market2invest

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional) Add API keys for AI-powered features
cp .env.example .env
# Edit .env — only the keys you want. See table below.

# 5. Run the pipeline
python run_pipeline.py
```

The report is saved to `outputs/report_YYYYMMDD_HHMMSS.md` and an interactive HTML dashboard to `outputs/dashboard_YYYYMMDD_HHMMSS.html`.

#### Optional: Start the Scheduler
```bash
# Runs daily (or weekly) at the time set in config.yaml
python run_pipeline.py --schedule
```

#### Optional: Enable Cost Confirmation
```yaml
# config.yaml
confirm_cost: true   # Prompts "Proceed? [Y/n]" with $ estimate before running
```

---

## Results — What You Get

### 1. Top-10 Investment Picks Table
| Rank | Ticker | Score | Price | Change % | Sentiment | Signal | Δ |
|------|--------|-------|-------|----------|-----------|--------|---|
| 1 | **RTX** | 78.85 | $179.66 | +0.39% | Bullish | 🔵 WATCH | new |
| 2 | **XOM** | 78.36 | $145.26 | −1.16% | Bullish | 🔵 WATCH | ↑1 |

### 2. "Why This Stock?" Rationale
Every pick includes linked evidence (news headlines, Reddit posts, tweets), price context, score breakdown, and optional AI/Kimi thesis.

### 3. Cost & Token Tracking
```
============================================================
💰 API COST SUMMARY
============================================================
Metric                            Estimated       Actual
------------------------------------------------------------
API calls                                 2            0
Input tokens                         28,500            0
Output tokens                         9,000            0
Cost (USD)                     $    0.0622 $       0.0
============================================================
```

### 4. Verification Checklist
```
| # | Goal | Status | Count |
|---|------|--------|-------|
| 1 | Collect Reddit posts | ❌ | 0 |
| 2 | Collect news articles | ✅ | 132 |
| 3 | Extract trending topics | ✅ | 5 |
| ... | ... | ... | ... |
**9/10 goals achieved.**
```

### 5. Visualisations
- Score trend chart (30-day history)
- Sentiment distribution pie chart
- Sector heatmap
- Word cloud of trending keywords
- All embedded in the HTML dashboard

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  DATA COLLECTION                                             │
│  • Reddit  • News RSS  • Twitter/X (Nitter)  • YouTube      │
│  • Kimi Agent Swarm: Trump | Geopolitics | Energy | Social  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  ANALYSIS                                                    │
│  • Topic extraction  • Sentiment (VADER + Kimi)             │
│  • Stock mapping  • Composite scoring 0–100                 │
│  • Trend detection (Z-score spikes)                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  REPORTING                                                   │
│  • Top-10 ranking  • Price data (yfinance)                  │
│  • Markdown + HTML dashboard  • Cost & verification         │
└─────────────────────────────────────────────────────────────┘
```

---

## CLI Options

```bash
python run_pipeline.py [options]

  --subreddits SUB [SUB ...]  Override subreddit list
  --sort {hot,top,new,rising} Reddit sort order (default: hot)
  --reddit-limit N            Max posts per subreddit (default: 25)
  --news-limit N              Max articles per feed (default: 20)
  --top-topics N              Trending topics to surface (default: 30)
  --output-dir DIR            Report save directory
  --no-save                   Print to stdout only
  --quiet                     Suppress terminal summary
  --schedule                  Start scheduler daemon
  --frequency {daily,weekly}  Override schedule frequency
  --config PATH               Config file path (default: ./config.yaml)
  --log-level {DEBUG,INFO,WARNING,ERROR}
```

---

## Configuration (`config.yaml`)

Key sections you can tune without touching code:

| Section | What it controls |
|---------|-----------------|
| `reddit.subreddits` | Which communities to monitor |
| `news.feeds` | RSS sources (includes Trump/politics, geopolitics, energy feeds) |
| `social_sources` | Toggle Reddit, Twitter, YouTube, TikTok, Meta on/off |
| `topic_filters` | Boost Trump / geopolitics / energy themes in scoring |
| `scoring` | Composite score weights (news, social, sentiment, price, AI) |
| `agent_swarm` | Enable/disable agents, set max queries per agent |
| `cost_rates` | USD per 1K tokens for Kimi and OpenAI |
| `confirm_cost` | Prompt before running if cost is above estimate |
| `schedule` | Daily / weekly cron-like scheduling |

---

## What You Need vs What's Free

### ✅ Free / Public — No API Key Needed

| Source | How it works | What you get |
|--------|-------------|--------------|
| **Reddit** | Public JSON API (no auth) | Posts from r/stocks, r/investing, r/wallstreetbets, etc. |
| **News RSS** | Standard RSS/Atom feeds | Yahoo Finance, Reuters, CNBC, MarketWatch, BBC, Al Jazeera, OilPrice.com |
| **Twitter/X** | Nitter RSS mirrors | Trending tweets for Trump, geopolitics, energy |
| **YouTube** | Invidious RSS feeds | Trending video titles & descriptions |
| **Stock Prices** | `yfinance` library | Live price, change %, volume from Yahoo Finance |
| **Sentiment** | VADER (NLTK) | Local, offline sentiment scoring |
| **Agent Swarm** | Bing News RSS + base queries | 5 agents search and collect articles without any AI key |
| **Visualizations** | matplotlib, seaborn, wordcloud | Charts, heatmaps, word clouds |

**Result:** With zero API keys, you get the full pipeline — Top-10 ranking, prices, sentiment, reports, charts, and HTML dashboard.

### 🔑 Optional API Keys — Supercharge with AI

Set **one** LLM provider at a time. Switching is a one-line change.

| Variable | Cost | What it unlocks |
|----------|------|----------------|
| `LLM_PROVIDER` + `LLM_API_KEY` | Provider-dependent | **Agent swarm smart queries**, **AI-extracted tickers & sentiment**, **AI rationale** per stock pick |
| `REDDIT_CLIENT_ID` + `SECRET` | Free | Higher Reddit rate limits (fewer 403 blocks) |
| `NEWSAPI_KEY` | Free tier available | Additional news sources beyond RSS |
| `X_BEARER_TOKEN` | Free tier available | Direct Twitter/X API (replaces Nitter mirrors) |
| `YOUTUBE_API_KEY` | Free tier available | Direct YouTube Data API (replaces Invidious) |
| `TIKTOK_API_KEY` | Paid / apply | TikTok video collection (stub today) |
| `META_APP_ID` + `SECRET` | Paid / app review | Facebook/Instagram collection (stub today) |

**Supported LLM providers:** `kimi` · `openai` · `gemini` · `claude`

```bash
# Example: use Gemini
cp .env.example .env
# Edit .env:
#   LLM_PROVIDER=gemini
#   LLM_API_KEY=your_gemini_key
```

Copy `.env.example → .env` and fill in only the keys you want.

---

## Automated Pipeline (GitHub Actions)

Runs **daily at 13:00 UTC** (9 AM ET / 6 AM PT). Every run produces:
- A Markdown report (`outputs/report_*.md`)
- A rich HTML report with animated sparklines (`outputs/report_*.html`)
- A chart dashboard (`outputs/dashboard_*.html`)
- Persistent ticker history (`outputs/ticker_score_history.json`) — accumulates across runs

### Setup

1. **Fork** the repo to your own GitHub account.
2. **Enable GitHub Actions** in your fork: *Settings → Actions → General → Allow all actions*.
3. **Enable GitHub Pages**:
   - *Settings → Pages → Source: GitHub Actions*
   - This makes the latest HTML report viewable at `https://yourname.github.io/AI_market2invest/`
4. **Add secrets** (all optional — the pipeline works without any):
   - Go to *Settings → Secrets and variables → Actions → New repository secret*

| Secret | Required? | What it does |
|--------|-----------|-------------|
| `LLM_PROVIDER` | No | `kimi` · `openai` · `gemini` · `claude` |
| `LLM_API_KEY` | No | Generic API key (provider auto-detected) |
| `ANTHROPIC_API_KEY` | No | Claude API key (if provider = claude) |
| `KIMI_API_KEY` | No | Kimi API key |
| `OPENAI_API_KEY` | No | OpenAI API key |
| `GEMINI_API_KEY` | No | Gemini API key |
| `REDDIT_CLIENT_ID` | No | Higher Reddit rate limits |
| `REDDIT_CLIENT_SECRET` | No | Paired with CLIENT_ID |
| `X_BEARER_TOKEN` | No | Direct X/Twitter API access |

5. **Run once manually** to verify: *Actions → Market Analysis Pipeline → Run workflow*.

### What Gets Committed vs. What Stays in Artifacts

| Output | Committed to repo | Artifact (30 days) |
|--------|------------------|-------------------|
| `*.json` history files | ✅ Yes (needed for sparklines) | ✅ Yes |
| `*.md` report | ✅ Yes | ✅ Yes |
| `*.html` report | ✅ Yes | ✅ Yes |
| `*.png` charts | ❌ No (prevents git bloat) | ✅ Yes |

### Live Report URL

After the first successful run, your latest HTML report is automatically deployed to:

```
https://<your-username>.github.io/AI_market2invest/
```

Bookmark it — it updates every day.

---

## Project Structure

```
AI_market2invest/
├── src/
│   ├── collectors/        # Reddit, RSS, Twitter, YouTube, stock prices
│   ├── agents/            # Kimi Agent Swarm (Trump, Geopolitics, Energy, etc.)
│   ├── analyzers/         # Topics, stock mapper, sentiment, composite scorer
│   ├── visualizers/       # Charts, heatmaps, word clouds, HTML dashboard
│   ├── reporters/         # Markdown report builder
│   ├── utils/             # Cost tracker
│   └── pipeline.py        # Orchestration
├── tests/
├── outputs/               # Generated reports
├── .github/workflows/     # CI/CD
├── config.yaml
├── run_pipeline.py
├── requirements.txt
└── .env.example
```

---

## Running Tests

```bash
python -m pytest tests/ -v
```

---

## Disclaimer

This tool is for **informational and educational purposes only**.  
It does **not** constitute financial advice.  
Always do your own research before making investment decisions.
