"""Tests for topic_extractor and stock_mapper."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analyzers import topic_extractor, stock_mapper


# ── topic_extractor ───────────────────────────────────────────────────────────

SAMPLE_POSTS = [
    {
        "title": "NVIDIA GPU sales smash records — AI demand drives revenue",
        "text": "The artificial intelligence boom is pushing NVIDIA to new heights.",
        "score": 5000,
        "subreddit": "stocks",
        "source": "reddit",
    },
    {
        "title": "Is Microsoft Azure the best cloud platform for AI workloads?",
        "text": "Comparing Azure vs AWS for machine learning deployments.",
        "score": 2000,
        "subreddit": "investing",
        "source": "reddit",
    },
    {
        "title": "Bitcoin hits new high amid crypto excitement",
        "text": "Crypto investors are euphoric as bitcoin surges.",
        "score": 3000,
        "subreddit": "wallstreetbets",
        "source": "reddit",
    },
]

SAMPLE_ARTICLES = [
    {
        "title": "Nvidia reports record quarterly earnings on AI chip demand",
        "summary": "Nvidia's data centre revenue surges 200% year-on-year.",
        "source": "Reuters",
        "url": "https://reuters.com/nvidia",
    },
    {
        "title": "Federal Reserve signals potential interest rate cut",
        "summary": "The Fed may lower rates in the next meeting amid inflation data.",
        "source": "CNBC",
        "url": "https://cnbc.com/fed",
    },
    {
        "title": "Bitcoin reaches $100k milestone",
        "summary": "Crypto market celebrates as bitcoin breaks six figures.",
        "source": "Yahoo Finance",
        "url": "https://finance.yahoo.com/bitcoin",
    },
]


class TestTopicExtractor:
    def test_extract_from_reddit_returns_list(self):
        results = topic_extractor.extract_from_reddit(SAMPLE_POSTS)
        assert isinstance(results, list)
        assert len(results) > 0

    def test_extract_from_reddit_tuples(self):
        results = topic_extractor.extract_from_reddit(SAMPLE_POSTS)
        for item in results:
            assert isinstance(item, tuple)
            assert len(item) == 2
            assert isinstance(item[0], str)
            assert isinstance(item[1], int)

    def test_extract_from_reddit_respects_top_n(self):
        results = topic_extractor.extract_from_reddit(SAMPLE_POSTS, top_n=5)
        assert len(results) <= 5

    def test_extract_from_news_returns_list(self):
        results = topic_extractor.extract_from_news(SAMPLE_ARTICLES)
        assert isinstance(results, list)

    def test_extract_from_news_respects_top_n(self):
        results = topic_extractor.extract_from_news(SAMPLE_ARTICLES, top_n=3)
        assert len(results) <= 3

    def test_merge_topics_combines_scores(self):
        reddit = [("nvidia", 100), ("bitcoin", 80)]
        news = [("nvidia", 50), ("federal reserve", 60)]
        merged = topic_extractor.merge_topics(reddit, news, top_n=10)

        # nvidia should appear once with combined score
        nvidia_entries = [m for m in merged if m[0] == "nvidia"]
        assert len(nvidia_entries) == 1
        # reddit score 100 + news score 50*2 = 200
        assert nvidia_entries[0][1] == 200

    def test_merge_topics_returns_sorted(self):
        reddit = [("a", 10), ("b", 5)]
        news = [("c", 100)]
        merged = topic_extractor.merge_topics(reddit, news, top_n=10)
        scores = [s for _, s in merged]
        assert scores == sorted(scores, reverse=True)

    def test_extract_high_level(self):
        topics = topic_extractor.extract(SAMPLE_POSTS, SAMPLE_ARTICLES, top_n=20)
        assert isinstance(topics, list)
        assert len(topics) > 0

    def test_tokenise_removes_stop_words(self):
        tokens = topic_extractor._tokenise("the quick brown fox jumps over the lazy dog")
        assert "the" not in tokens
        assert "over" not in tokens
        assert "quick" in tokens

    def test_tokenise_handles_punctuation(self):
        tokens = topic_extractor._tokenise("nvidia's GPU, revenue: $100 billion!")
        for t in tokens:
            assert "," not in t
            assert "!" not in t

    def test_empty_inputs_return_empty(self):
        results = topic_extractor.extract([], [], top_n=10)
        assert results == []


# ── stock_mapper ──────────────────────────────────────────────────────────────

SAMPLE_TOPICS = [
    ("nvidia", 500),
    ("artificial intelligence", 400),
    ("bitcoin", 300),
    ("federal reserve", 200),
    ("microsoft azure", 150),
    ("electric vehicle", 100),
]


class TestStockMapper:
    def test_map_topics_returns_dict(self):
        result = stock_mapper.map_topics_to_stocks(SAMPLE_TOPICS)
        assert isinstance(result, dict)

    def test_map_topics_identifies_nvidia(self):
        result = stock_mapper.map_topics_to_stocks([("nvidia", 500)])
        assert "NVDA" in result

    def test_map_topics_identifies_bitcoin_tickers(self):
        result = stock_mapper.map_topics_to_stocks([("bitcoin", 300)])
        # bitcoin maps to COIN, MSTR, etc.
        assert any(t in result for t in ("COIN", "MSTR", "RIOT", "MARA"))

    def test_map_topics_accumulates_scores(self):
        topics = [("nvidia", 100), ("nvda", 200)]
        result = stock_mapper.map_topics_to_stocks(topics)
        assert "NVDA" in result
        assert result["NVDA"]["score"] >= 300

    def test_map_topics_includes_reasons(self):
        result = stock_mapper.map_topics_to_stocks([("nvidia", 500)])
        assert "NVDA" in result
        assert len(result["NVDA"]["reasons"]) > 0

    def test_map_topics_attaches_news_snippets(self):
        articles = [
            {
                "title": "Nvidia GPU sales break records",
                "summary": "Revenue up 200%",
                "source": "Reuters",
                "url": "https://reuters.com/nvidia",
            }
        ]
        result = stock_mapper.map_topics_to_stocks(
            [("nvidia", 500)], articles=articles
        )
        assert "NVDA" in result
        assert len(result["NVDA"]["news_snippets"]) > 0

    def test_map_topics_attaches_reddit_snippets(self):
        posts = [
            {
                "title": "NVIDIA is going to the moon!",
                "text": "AI demand is insane",
                "score": 5000,
                "subreddit": "wallstreetbets",
                "source": "reddit",
            }
        ]
        result = stock_mapper.map_topics_to_stocks(
            [("nvidia", 500)], posts=posts
        )
        assert "NVDA" in result
        assert len(result["NVDA"]["reddit_snippets"]) > 0

    def test_enrich_with_openai_skipped_without_key(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        ticker_data = {"NVDA": {"ticker": "NVDA", "score": 100, "reasons": [], "news_snippets": [], "reddit_snippets": []}}
        result = stock_mapper.enrich_with_openai(ticker_data, SAMPLE_TOPICS, SAMPLE_ARTICLES)
        # Should return unchanged — no ai_analysis key added
        assert "ai_analysis" not in result["NVDA"]

    def test_map_topics_handles_empty_input(self):
        result = stock_mapper.map_topics_to_stocks([])
        assert result == {}

    def test_keyword_ticker_map_structure(self):
        for phrase, tickers in stock_mapper.KEYWORD_TICKER_MAP.items():
            assert isinstance(phrase, str)
            assert isinstance(tickers, list)
            assert all(isinstance(t, str) for t in tickers)
