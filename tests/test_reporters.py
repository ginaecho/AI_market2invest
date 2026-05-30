"""Tests for investment_reporter."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.reporters import investment_reporter


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
