"""Tests for reddit_collector and news_collector."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.collectors import reddit_collector, news_collector


# ── reddit_collector ──────────────────────────────────────────────────────────

def _make_reddit_response(subreddit: str, n: int = 3) -> dict:
    """Build a minimal fake Reddit JSON response."""
    children = []
    for i in range(n):
        children.append({
            "data": {
                "title": f"Post {i} about {subreddit}",
                "selftext": f"Body text for post {i}",
                "score": 100 * (i + 1),
                "num_comments": 10 * (i + 1),
                "permalink": f"/r/{subreddit}/comments/{i}/",
                "author": f"user{i}",
                "created_utc": 1700000000.0 + i,
            }
        })
    return {"data": {"children": children}}


class TestRedditCollector:
    @patch("src.collectors.reddit_collector.requests.get")
    @patch("src.collectors.reddit_collector.time.sleep")
    def test_collect_returns_posts(self, mock_sleep, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_reddit_response("stocks", n=3)
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        posts = reddit_collector.collect(subreddits=["stocks"], limit_per_sub=3)

        assert len(posts) == 3
        assert all(p["source"] == "reddit" for p in posts)
        assert all(p["subreddit"] == "stocks" for p in posts)

    @patch("src.collectors.reddit_collector.requests.get")
    @patch("src.collectors.reddit_collector.time.sleep")
    def test_collect_sorts_by_score_descending(self, mock_sleep, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_reddit_response("investing", n=3)
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        posts = reddit_collector.collect(subreddits=["investing"], limit_per_sub=3)

        scores = [p["score"] for p in posts]
        assert scores == sorted(scores, reverse=True)

    @patch("src.collectors.reddit_collector.requests.get")
    @patch("src.collectors.reddit_collector.time.sleep")
    def test_collect_handles_request_error_gracefully(self, mock_sleep, mock_get):
        import requests

        mock_get.side_effect = requests.RequestException("timeout")

        # Should not raise; returns empty list
        posts = reddit_collector.collect(subreddits=["stocks"], limit_per_sub=5)
        assert posts == []

    @patch("src.collectors.reddit_collector.requests.get")
    @patch("src.collectors.reddit_collector.time.sleep")
    def test_collect_multiple_subreddits(self, mock_sleep, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_reddit_response("x", n=2)
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        posts = reddit_collector.collect(
            subreddits=["stocks", "investing"], limit_per_sub=2
        )
        # 2 subreddits × 2 posts each = 4 total
        assert len(posts) == 4

    @patch("src.collectors.reddit_collector._get_oauth_token")
    @patch("src.collectors.reddit_collector._fetch_authenticated")
    @patch("src.collectors.reddit_collector.time.sleep")
    def test_collect_uses_authenticated_fetch_when_token_available(
        self, mock_sleep, mock_auth_fetch, mock_token
    ):
        mock_token.return_value = "fake_token"
        mock_auth_fetch.return_value = [{"title": "post", "score": 1, "source": "reddit", "subreddit": "stocks"}]

        posts = reddit_collector.collect(subreddits=["stocks"], limit_per_sub=5)

        mock_auth_fetch.assert_called_once()
        assert len(posts) == 1


# ── news_collector ────────────────────────────────────────────────────────────

def _make_feedparser_response(n: int = 3):
    """Build a minimal fake feedparser result."""
    entries = []
    for i in range(n):
        entry = MagicMock()
        entry.get = lambda key, default="", _i=i: {
            "title": f"News headline {_i}",
            "summary": f"Summary for article {_i}",
            "link": f"https://example.com/article/{_i}",
            "published": "Mon, 01 Jan 2024 12:00:00 +0000",
        }.get(key, default)
        entry.tags = []
        entries.append(entry)

    result = MagicMock()
    result.entries = entries
    return result


class TestNewsCollector:
    @patch("src.collectors.news_collector.feedparser.parse")
    @patch("src.collectors.news_collector.time.sleep")
    def test_collect_returns_articles(self, mock_sleep, mock_parse):
        mock_parse.return_value = _make_feedparser_response(n=3)

        articles = news_collector.collect(
            feeds={"Test Feed": "https://example.com/rss"},
            max_items_per_feed=3,
        )

        assert len(articles) == 3
        assert all(a["source"] == "Test Feed" for a in articles)

    @patch("src.collectors.news_collector.feedparser.parse")
    @patch("src.collectors.news_collector.time.sleep")
    def test_collect_respects_max_items(self, mock_sleep, mock_parse):
        mock_parse.return_value = _make_feedparser_response(n=10)

        articles = news_collector.collect(
            feeds={"Feed": "https://example.com/rss"},
            max_items_per_feed=5,
        )

        assert len(articles) == 5

    @patch("src.collectors.news_collector.feedparser.parse")
    @patch("src.collectors.news_collector.time.sleep")
    def test_collect_handles_parse_error_gracefully(self, mock_sleep, mock_parse):
        mock_parse.side_effect = Exception("network error")

        articles = news_collector.collect(
            feeds={"Bad Feed": "https://broken.example.com/rss"},
        )

        assert articles == []

    @patch("src.collectors.news_collector.feedparser.parse")
    @patch("src.collectors.news_collector.time.sleep")
    def test_collect_aggregates_multiple_feeds(self, mock_sleep, mock_parse):
        mock_parse.return_value = _make_feedparser_response(n=2)

        articles = news_collector.collect(
            feeds={
                "Feed A": "https://example.com/a",
                "Feed B": "https://example.com/b",
            },
            max_items_per_feed=2,
        )

        assert len(articles) == 4
