"""Tests for investment_reporter."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.reporters import investment_reporter, html_reporter


SAMPLE_TOPICS = [
    ("nvidia", 500),
    ("artificial intelligence", 400),
    ("bitcoin", 300),
    ("federal reserve", 200),
]

SAMPLE_POSTS = [
    {
        "title": "NVDA mooning after earnings",
        "text": "",
        "score": 8000,
        "subreddit": "wallstreetbets",
        "url": "https://reddit.com/r/wsb/1",
        "source": "reddit",
    },
    {
        "title": "Is it time to buy bonds?",
        "text": "",
        "score": 3000,
        "subreddit": "investing",
        "url": "https://reddit.com/r/investing/2",
        "source": "reddit",
    },
]

SAMPLE_ARTICLES = [
    {
        "title": "Nvidia breaks revenue records",
        "summary": "Record AI-driven GPU demand",
        "source": "Reuters",
        "url": "https://reuters.com/1",
    },
    {
        "title": "Fed signals rate cut ahead",
        "summary": "Inflation data supports easing",
        "source": "CNBC",
        "url": "https://cnbc.com/2",
    },
]

SAMPLE_TICKER_DATA = {
    "NVDA": {
        "ticker": "NVDA",
        "score": 900,
        "reasons": ["'nvidia' (score 500)", "'artificial intelligence' (score 400)"],
        "news_snippets": ["Nvidia breaks revenue records"],
        "reddit_snippets": ["NVDA mooning after earnings"],
    },
    "MSFT": {
        "ticker": "MSFT",
        "score": 400,
        "reasons": ["'artificial intelligence' (score 400)"],
        "news_snippets": [],
        "reddit_snippets": [],
    },
    "COIN": {
        "ticker": "COIN",
        "score": 300,
        "reasons": ["'bitcoin' (score 300)"],
        "news_snippets": [],
        "reddit_snippets": [],
    },
}

SAMPLE_TICKER_DATA_WITH_AI = {
    "NVDA": {
        "ticker": "NVDA",
        "score": 900,
        "reasons": ["'nvidia' (score 500)"],
        "news_snippets": ["Nvidia breaks records"],
        "reddit_snippets": [],
        "ai_analysis": {
            "signal": "BUY",
            "thesis": "Strong AI GPU demand driving record earnings growth.",
            "catalysts": ["AI capex surge", "Data center expansion"],
            "risks": ["Competition from AMD", "Supply constraints"],
        },
    },
}


class TestBuildReport:
    def test_returns_string(self):
        report = investment_reporter.build_report(
            SAMPLE_TOPICS, SAMPLE_POSTS, SAMPLE_ARTICLES, SAMPLE_TICKER_DATA
        )
        assert isinstance(report, str)
        assert len(report) > 100

    def test_contains_header(self):
        report = investment_reporter.build_report(
            SAMPLE_TOPICS, SAMPLE_POSTS, SAMPLE_ARTICLES, SAMPLE_TICKER_DATA
        )
        assert "Market Intelligence" in report

    def test_contains_trending_topics(self):
        report = investment_reporter.build_report(
            SAMPLE_TOPICS, SAMPLE_POSTS, SAMPLE_ARTICLES, SAMPLE_TICKER_DATA
        )
        assert "nvidia" in report.lower()
        assert "Trending Topics" in report

    def test_contains_news_section(self):
        report = investment_reporter.build_report(
            SAMPLE_TOPICS, SAMPLE_POSTS, SAMPLE_ARTICLES, SAMPLE_TICKER_DATA
        )
        assert "Reuters" in report
        assert "Nvidia breaks revenue records" in report

    def test_contains_reddit_section(self):
        report = investment_reporter.build_report(
            SAMPLE_TOPICS, SAMPLE_POSTS, SAMPLE_ARTICLES, SAMPLE_TICKER_DATA
        )
        assert "wallstreetbets" in report
        assert "NVDA mooning" in report

    def test_contains_investment_section(self):
        report = investment_reporter.build_report(
            SAMPLE_TOPICS, SAMPLE_POSTS, SAMPLE_ARTICLES, SAMPLE_TICKER_DATA
        )
        assert "Investment Recommendations" in report
        assert "NVDA" in report

    def test_contains_timestamp(self):
        ts = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
        report = investment_reporter.build_report(
            SAMPLE_TOPICS, SAMPLE_POSTS, SAMPLE_ARTICLES, SAMPLE_TICKER_DATA,
            run_timestamp=ts,
        )
        assert "2024-01-15" in report

    def test_ai_analysis_included_when_present(self):
        report = investment_reporter.build_report(
            SAMPLE_TOPICS, SAMPLE_POSTS, SAMPLE_ARTICLES, SAMPLE_TICKER_DATA_WITH_AI
        )
        assert "BUY" in report
        assert "Strong AI GPU demand" in report
        assert "AI capex surge" in report

    def test_signal_emoji_buy(self):
        report = investment_reporter.build_report(
            SAMPLE_TOPICS, SAMPLE_POSTS, SAMPLE_ARTICLES, SAMPLE_TICKER_DATA_WITH_AI
        )
        assert "🟢" in report

    def test_watch_signal_for_ticker_without_ai(self):
        # Without ai_analysis, default signal is WATCH
        assert investment_reporter._signal_for(SAMPLE_TICKER_DATA["NVDA"]) == "WATCH"

    def test_tickers_sorted_by_score_descending(self):
        report = investment_reporter.build_report(
            SAMPLE_TOPICS, SAMPLE_POSTS, SAMPLE_ARTICLES, SAMPLE_TICKER_DATA
        )
        # Find the recommendations section, then check NVDA appears before COIN
        rec_section_start = report.find("## 💡 Investment Recommendations")
        assert rec_section_start != -1
        rec_section = report[rec_section_start:]
        nvda_pos = rec_section.find("NVDA")
        coin_pos = rec_section.find("COIN")
        # NVDA has highest score (900) so should appear before COIN (300)
        assert nvda_pos != -1
        assert coin_pos != -1
        assert nvda_pos < coin_pos

    def test_contains_methodology(self):
        report = investment_reporter.build_report(
            SAMPLE_TOPICS, SAMPLE_POSTS, SAMPLE_ARTICLES, SAMPLE_TICKER_DATA
        )
        assert "Methodology" in report


class TestSaveReport:
    def test_saves_file(self, tmp_path):
        report = "# Test Report\nContent here."
        path = investment_reporter.save_report(report, output_dir=tmp_path)
        assert path.exists()
        assert path.read_text(encoding="utf-8") == report

    def test_filename_has_timestamp(self, tmp_path):
        report = "# Test"
        path = investment_reporter.save_report(report, output_dir=tmp_path)
        assert path.name.startswith("report_")
        assert path.suffix == ".md"

    def test_creates_output_dir(self, tmp_path):
        nested = tmp_path / "a" / "b" / "c"
        report = "# Test"
        path = investment_reporter.save_report(report, output_dir=nested)
        assert path.exists()


class TestPrintSummary:
    def test_runs_without_error(self, capsys):
        investment_reporter.print_summary(SAMPLE_TICKER_DATA, top_n=3)
        captured = capsys.readouterr()
        assert "NVDA" in captured.out
        assert "COIN" in captured.out


# ── HTML Reporter Tests ──────────────────────────────────────────────────────

SAMPLE_RANKED = [
    {
        "rank": 1,
        "ticker": "NVDA",
        "composite_score": 85.5,
        "price": 450.0,
        "change_pct": 2.5,
        "avg_sentiment": 0.42,
        "avg_sentiment_label": "bullish",
        "score_breakdown": {
            "news_volume": 80.0,
            "social_engagement": 90.0,
            "sentiment": 85.0,
            "price_momentum": 75.0,
            "ai_rationale": 60.0,
        },
        "ai_analysis": {
            "signal": "BUY",
            "thesis": "AI demand is driving record GPU sales.",
            "catalysts": ["Data center growth", "AI adoption"],
            "risks": ["Competition"],
        },
        "news_sources": [
            {"title": "Nvidia Breaks Records", "url": "https://reuters.com/nvda"},
        ],
        "news_snippets": ["Nvidia breaks revenue records"],
    },
    {
        "rank": 2,
        "ticker": "COIN",
        "composite_score": 62.3,
        "price": 180.0,
        "change_pct": -1.2,
        "avg_sentiment": -0.15,
        "avg_sentiment_label": "bearish",
        "score_breakdown": {
            "news_volume": 50.0,
            "social_engagement": 60.0,
            "sentiment": 35.0,
            "price_momentum": 40.0,
            "ai_rationale": 40.0,
        },
        "ai_analysis": {
            "signal": "WATCH",
            "thesis": "Crypto volatility creates uncertainty.",
        },
        "news_snippets": ["Bitcoin drops amid regulatory fears"],
    },
]


class TestBuildHtmlReport:
    def test_returns_string(self):
        report = html_reporter.build_html_report(
            SAMPLE_TOPICS, SAMPLE_POSTS, SAMPLE_ARTICLES, SAMPLE_TICKER_DATA,
            ranked=SAMPLE_RANKED,
        )
        assert isinstance(report, str)
        assert len(report) > 500

    def test_contains_doctype_and_html(self):
        report = html_reporter.build_html_report(
            SAMPLE_TOPICS, SAMPLE_POSTS, SAMPLE_ARTICLES, SAMPLE_TICKER_DATA,
            ranked=SAMPLE_RANKED,
        )
        assert "<!DOCTYPE html>" in report
        assert "<html" in report
        assert "</html>" in report

    def test_contains_title_and_header(self):
        report = html_reporter.build_html_report(
            SAMPLE_TOPICS, SAMPLE_POSTS, SAMPLE_ARTICLES, SAMPLE_TICKER_DATA,
            ranked=SAMPLE_RANKED,
        )
        assert "Market Intelligence Report" in report
        assert "Top-10 Investment Picks" in report

    def test_contains_ticker_cards(self):
        report = html_reporter.build_html_report(
            SAMPLE_TOPICS, SAMPLE_POSTS, SAMPLE_ARTICLES, SAMPLE_TICKER_DATA,
            ranked=SAMPLE_RANKED,
        )
        assert "NVDA" in report
        assert "COIN" in report

    def test_contains_score_bars(self):
        report = html_reporter.build_html_report(
            SAMPLE_TOPICS, SAMPLE_POSTS, SAMPLE_ARTICLES, SAMPLE_TICKER_DATA,
            ranked=SAMPLE_RANKED,
        )
        assert "score-bar-fill" in report
        assert "bar-news" in report
        assert "bar-sent" in report

    def test_contains_sentiment_gauge(self):
        report = html_reporter.build_html_report(
            SAMPLE_TOPICS, SAMPLE_POSTS, SAMPLE_ARTICLES, SAMPLE_TICKER_DATA,
            ranked=SAMPLE_RANKED,
        )
        assert "sentiment-marker" in report
        assert "sentiment-track" in report

    def test_contains_source_links(self):
        report = html_reporter.build_html_report(
            SAMPLE_TOPICS, SAMPLE_POSTS, SAMPLE_ARTICLES, SAMPLE_TICKER_DATA,
            ranked=SAMPLE_RANKED,
        )
        assert "reuters.com/nvda" in report
        assert 'class="source-link"' in report

    def test_contains_narrative(self):
        report = html_reporter.build_html_report(
            SAMPLE_TOPICS, SAMPLE_POSTS, SAMPLE_ARTICLES, SAMPLE_TICKER_DATA,
            ranked=SAMPLE_RANKED,
        )
        assert "What the Market Is Saying" in report
        assert "AI demand is driving record GPU sales" in report

    def test_contains_cost_section(self):
        cost = {
            "total_calls": 28,
            "total_input_tokens": 9880,
            "total_output_tokens": 11161,
            "total_cost_usd": 0.18,
            "by_provider": {"claude": {"calls": 28, "cost_usd": 0.18}},
        }
        report = html_reporter.build_html_report(
            SAMPLE_TOPICS, SAMPLE_POSTS, SAMPLE_ARTICLES, SAMPLE_TICKER_DATA,
            ranked=SAMPLE_RANKED, cost=cost,
        )
        assert "Cost &amp; Token Usage" in report or "Cost & Token Usage" in report
        # Numbers are formatted with commas: 9,880
        assert "9,880" in report
        assert "11,161" in report
        assert "0.18" in report

    def test_contains_verification(self):
        verification = [
            {"goal": "Collect news", "status": True, "count": 10},
            {"goal": "Rank top-10", "status": True, "count": 10},
        ]
        report = html_reporter.build_html_report(
            SAMPLE_TOPICS, SAMPLE_POSTS, SAMPLE_ARTICLES, SAMPLE_TICKER_DATA,
            ranked=SAMPLE_RANKED, verification=verification,
        )
        assert "Verification Checklist" in report
        assert "Collect news" in report

    def test_contains_methodology(self):
        report = html_reporter.build_html_report(
            SAMPLE_TOPICS, SAMPLE_POSTS, SAMPLE_ARTICLES, SAMPLE_TICKER_DATA,
            ranked=SAMPLE_RANKED,
        )
        assert "Methodology" in report
        assert "Composite scoring" in report

    def test_escapes_html_in_ticker_names(self):
        malicious = [
            {
                "rank": 1,
                "ticker": "<script>alert(1)</script>",
                "composite_score": 50.0,
                "avg_sentiment": 0.0,
                "avg_sentiment_label": "neutral",
            },
        ]
        report = html_reporter.build_html_report(
            SAMPLE_TOPICS, SAMPLE_POSTS, SAMPLE_ARTICLES, SAMPLE_TICKER_DATA,
            ranked=malicious,
        )
        # The HTML report itself contains <script> tags for interactivity,
        # so we check the specific ticker card area is escaped.
        ticker_section = report.split('class="ticker-symbol"')[1].split("</div>")[0]
        assert "<script>" not in ticker_section
        assert "&lt;script&gt;" in ticker_section

    def test_escapes_html_in_sources(self):
        bad_sources = [
            {
                "rank": 1,
                "ticker": "SAFE",
                "composite_score": 50.0,
                "avg_sentiment": 0.0,
                "avg_sentiment_label": "neutral",
                "news_sources": [
                    {"title": "<img src=x onerror=alert(1)>", "url": "https://example.com"},
                ],
            },
        ]
        report = html_reporter.build_html_report(
            SAMPLE_TOPICS, SAMPLE_POSTS, SAMPLE_ARTICLES, SAMPLE_TICKER_DATA,
            ranked=bad_sources,
        )
        # The HTML report contains onerror= in its own <script> tag,
        # so we check the source-link area specifically.
        source_section = report.split('class="source-grid"')[1].split("</div>")[0]
        # Verify the malicious title is escaped (not rendered as HTML)
        assert "&lt;img" in source_section
        assert "&gt;" in source_section
        # The raw <img> tag must not be rendered
        assert "<img" not in source_section

    def test_no_ranked_shows_legacy(self):
        report = html_reporter.build_html_report(
            SAMPLE_TOPICS, SAMPLE_POSTS, SAMPLE_ARTICLES, SAMPLE_TICKER_DATA,
        )
        assert "Market Intelligence Report" in report
        # Should still have trending topics and news
        assert "Trending Topics" in report

    def test_sparkline_function_generates_svg(self):
        history = [
            {"date": "2024-01-01", "composite_score": 50.0},
            {"date": "2024-01-02", "composite_score": 60.0},
            {"date": "2024-01-03", "composite_score": 55.0},
        ]
        svg = html_reporter._sparkline_svg(history)
        assert "<svg" in svg
        assert "</svg>" in svg
        assert "sparkline-path" in svg
        assert "sparkline-dot" in svg
        assert "45" in svg  # min score label (50 - 5 padding)

    def test_sparkline_returns_empty_for_short_history(self):
        svg = html_reporter._sparkline_svg([{"date": "2024-01-01", "composite_score": 50.0}])
        assert svg == ""
        svg = html_reporter._sparkline_svg([])
        assert svg == ""

    def test_sparkline_in_report_when_history_available(self, tmp_path, monkeypatch):
        original_file = html_reporter._TICKER_HISTORY_FILE
        temp_hist = tmp_path / "ticker_score_history.json"
        temp_hist.write_text(
            json.dumps({
                "NVDA": [
                    {"date": "2024-01-01", "composite_score": 70.0},
                    {"date": "2024-01-02", "composite_score": 80.0},
                    {"date": "2024-01-03", "composite_score": 85.5},
                ]
            }),
            encoding="utf-8",
        )
        monkeypatch.setattr(html_reporter, "_TICKER_HISTORY_FILE", temp_hist)

        report = html_reporter.build_html_report(
            SAMPLE_TOPICS, SAMPLE_POSTS, SAMPLE_ARTICLES, SAMPLE_TICKER_DATA,
            ranked=SAMPLE_RANKED,
        )
        assert "sparkline-svg" in report
        assert "sparkline-path" in report
        assert "Score Trend" in report
        # Check live indicator appears
        assert "live-indicator" in report
        monkeypatch.setattr(html_reporter, "_TICKER_HISTORY_FILE", original_file)

    def test_no_sparkline_when_history_missing(self, tmp_path, monkeypatch):
        original_file = html_reporter._TICKER_HISTORY_FILE
        temp_hist = tmp_path / "ticker_score_history.json"
        temp_hist.write_text(json.dumps({}), encoding="utf-8")
        monkeypatch.setattr(html_reporter, "_TICKER_HISTORY_FILE", temp_hist)

        report = html_reporter.build_html_report(
            SAMPLE_TOPICS, SAMPLE_POSTS, SAMPLE_ARTICLES, SAMPLE_TICKER_DATA,
            ranked=SAMPLE_RANKED,
        )
        # No tickers have history, so no rendered sparklines should appear
        # Check for the actual rendered content, not CSS selectors
        assert "Score Trend (last" not in report
        monkeypatch.setattr(html_reporter, "_TICKER_HISTORY_FILE", original_file)


class TestSaveHtmlReport:
    def test_saves_file(self, tmp_path):
        report = "<html><body>Test</body></html>"
        path = html_reporter.save_html_report(report, output_dir=tmp_path)
        assert path.exists()
        assert path.read_text(encoding="utf-8") == report

    def test_filename_has_html_extension(self, tmp_path):
        report = "<html></html>"
        path = html_reporter.save_html_report(report, output_dir=tmp_path)
        assert path.name.startswith("report_")
        assert path.suffix == ".html"

    def test_creates_output_dir(self, tmp_path):
        nested = tmp_path / "x" / "y"
        report = "<html></html>"
        path = html_reporter.save_html_report(report, output_dir=nested)
        assert path.exists()
