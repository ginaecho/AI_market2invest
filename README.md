# AI Market-to-Invest

> **Collect → Analyse → Invest**  
> A repeatable pipeline that scrapes financial Reddit communities and RSS news feeds, extracts trending topics, maps them to stock tickers, and generates a ready-to-read Markdown investment report — automatically, every trading day.

---

## How it works

```
Reddit (r/stocks, r/investing, r/wallstreetbets, …)
News RSS (Yahoo Finance, Reuters, CNBC, MarketWatch, …)
        │
        ▼
  Topic Extractor  ──  keyword frequency + engagement weighting
        │
        ▼
  Stock Mapper  ──  200+ keyword → ticker phrases  +  optional OpenAI enrichment
        │
        ▼
  Investment Reporter  ──  Markdown report saved to outputs/
```

Each stage is a focused Python module with no mandatory API keys — everything works out of the box with public data sources.  
Optionally, add an **OpenAI** key to upgrade the stock analysis from keyword-matching to GPT-4o-mini narrative reasoning.

---

## Quick start

```bash
# 1. Clone and enter the repo
git clone https://github.com/ginaecho/AI_market2invest.git
cd AI_market2invest

# 2. Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional) Configure API keys
cp .env.example .env
# Edit .env and add OPENAI_API_KEY / REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET

# 5. Run the pipeline
python run_pipeline.py
```

The report is saved to `outputs/report_YYYYMMDD_HHMMSS.md` and a summary table is printed to the terminal.

---

## CLI options

```
python run_pipeline.py [options]

Options:
  --subreddits SUB [SUB ...]  Override the list of subreddits
  --sort {hot,top,new,rising} Reddit post sort order (default: hot)
  --reddit-limit N            Max posts per subreddit (default: 25)
  --news-limit N              Max articles per news feed (default: 20)
  --top-topics N              Number of trending topics to surface (default: 30)
  --output-dir DIR            Directory for saving the report
  --no-save                   Print report to stdout instead of saving
  --quiet                     Suppress summary table
  --log-level {DEBUG,INFO,WARNING,ERROR}
```

---

## Automated pipeline (GitHub Actions)

The workflow at `.github/workflows/market_analysis.yml` runs automatically every **Monday–Friday at 14:00 UTC** (9 AM ET, US market open).

### Setup

1. Fork or clone this repository.
2. Add secrets in **Settings → Secrets and variables → Actions**:

| Secret | Required? | Purpose |
|--------|-----------|---------|
| `OPENAI_API_KEY` | Optional | GPT-4o-mini narrative analysis |
| `REDDIT_CLIENT_ID` | Optional | Higher Reddit rate limits |
| `REDDIT_CLIENT_SECRET` | Optional | (required with client ID) |

3. Enable Actions in your fork if prompted.
4. Each run uploads the report as a **workflow artifact** and commits it back to `outputs/`.

You can also trigger a run manually from the **Actions** tab → **Market Analysis Pipeline** → **Run workflow**.

---

## Project structure

```
AI_market2invest/
├── src/
│   ├── collectors/
│   │   ├── reddit_collector.py   # Reddit public JSON API + optional OAuth2
│   │   └── news_collector.py     # RSS/Atom feed parser
│   ├── analyzers/
│   │   ├── topic_extractor.py    # Keyword frequency & bigram extraction
│   │   └── stock_mapper.py       # Keyword→ticker map + OpenAI enrichment
│   ├── reporters/
│   │   └── investment_reporter.py # Markdown report builder
│   └── pipeline.py               # Orchestration
├── tests/
│   ├── test_collectors.py
│   ├── test_analyzers.py
│   └── test_reporters.py
├── outputs/                      # Generated reports (gitignored except .gitkeep)
├── .github/
│   └── workflows/
│       └── market_analysis.yml   # Scheduled + manual GitHub Actions workflow
├── config.yaml                   # Subreddit list, feed URLs, tuning knobs
├── run_pipeline.py               # CLI entry point
├── requirements.txt
└── .env.example                  # Environment variables template
```

---

## Data sources

### Reddit communities monitored by default

| Subreddit | Focus |
|-----------|-------|
| r/stocks | Stock analysis & news |
| r/investing | Long-term investing |
| r/wallstreetbets | High-conviction / meme plays |
| r/finance | General finance |
| r/economics | Macro & economic data |
| r/StockMarket | Market discussion |
| r/options | Options trading |
| r/SecurityAnalysis | Fundamental analysis |
| r/dividends | Dividend investing |
| r/ETFs | ETF strategies |

### News feeds

Yahoo Finance, Reuters Business, CNBC Top News, CNBC Finance, CNBC Economy, MarketWatch, Investopedia, Seeking Alpha.

---

## Configuration

Edit `config.yaml` to add / remove subreddits and news feeds without touching the code.

---

## Running tests

```bash
python -m pytest tests/ -v
```

---

## Report sample

```markdown
# 📈 Market Intelligence & Investment Report
**Generated:** 2026-05-30 14:00 UTC

## 🔥 Top Trending Topics
| Rank | Topic | Score |
|------|-------|-------|
| 1 | `nvidia` | 842 |
| 2 | `artificial intelligence` | 720 |
...

## 💡 Investment Recommendations

### 🟢 NVDA
**Signal:** BUY | **Engagement Score:** 900
**Thesis:** Strong AI GPU demand driving record earnings growth.
**Catalysts:**
- AI capex surge across hyperscalers
- Blackwell chip ramp
...
```

---

## Disclaimer

This tool is for **informational and educational purposes only**.  
It does **not** constitute financial advice.  
Always do your own research before making investment decisions.
