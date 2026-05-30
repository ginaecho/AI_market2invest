"""
Topic extractor — identifies the most-discussed keywords and themes from
collected Reddit posts and news articles.

Uses frequency analysis and a curated list of financial stop-words.  Does
not require any external API; the optional OpenAI path is handled upstream
by the stock mapper.
"""

from __future__ import annotations

import re
import string
import logging
from collections import Counter
from typing import Dict, List, Any, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Stop words to filter out during frequency analysis
# ---------------------------------------------------------------------------
_STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "shall", "can",
    "to", "of", "in", "for", "on", "with", "at", "by", "from", "as",
    "into", "through", "during", "before", "after", "above", "below",
    "up", "down", "out", "off", "over", "under", "again", "then", "once",
    "here", "there", "when", "where", "why", "how", "all", "both", "each",
    "few", "more", "most", "other", "some", "such", "no", "nor", "not",
    "only", "own", "same", "so", "than", "too", "very", "just", "its",
    "it", "this", "that", "these", "those", "i", "me", "my", "we", "our",
    "you", "your", "he", "him", "his", "she", "her", "they", "them",
    "what", "which", "who", "whom", "s", "t", "re", "ve", "ll", "d",
    "also", "about", "if", "while", "between", "after", "before",
    # generic finance filler
    "market", "markets", "stock", "stocks", "share", "shares", "price",
    "prices", "trade", "trading", "investor", "investors", "company",
    "companies", "year", "years", "quarter", "quarters", "report",
    "said", "says", "new", "says", "make", "get", "go", "like", "one",
    "two", "three", "per", "cent", "percent", "billion", "million",
    "trillion", "today", "week", "month", "day", "time", "now", "still",
}

_PUNCTUATION_RE = re.compile(r"[^a-zA-Z0-9\s\-]")
_WHITESPACE_RE = re.compile(r"\s+")


def _tokenise(text: str) -> List[str]:
    """Lower-case, strip punctuation, split into tokens."""
    text = _PUNCTUATION_RE.sub(" ", text.lower())
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return [t for t in text.split() if len(t) > 2 and t not in _STOP_WORDS]


def _extract_bigrams(tokens: List[str]) -> List[str]:
    """Return consecutive token pairs as 'word1 word2' strings."""
    return [f"{tokens[i]} {tokens[i+1]}" for i in range(len(tokens) - 1)]


def extract_from_reddit(posts: List[Dict[str, Any]], top_n: int = 40) -> List[Tuple[str, int]]:
    """
    Count keyword frequency across all Reddit posts (title + body text).
    Higher-score posts contribute proportionally more weight.

    Returns:
        List of (keyword, weighted_count) sorted descending.
    """
    counter: Counter = Counter()
    for post in posts:
        weight = max(1, int(post.get("score", 1) ** 0.4))  # sqrt-ish dampening
        text = post.get("title", "") + " " + post.get("text", "")
        tokens = _tokenise(text)
        for t in tokens:
            counter[t] += weight
        for bg in _extract_bigrams(tokens):
            counter[bg] += weight

    return counter.most_common(top_n)


def extract_from_news(articles: List[Dict[str, Any]], top_n: int = 40) -> List[Tuple[str, int]]:
    """
    Count keyword frequency across all news articles (title + summary).

    Returns:
        List of (keyword, count) sorted descending.
    """
    counter: Counter = Counter()
    for article in articles:
        text = article.get("title", "") + " " + article.get("summary", "")
        tokens = _tokenise(text)
        for t in tokens:
            counter[t] += 1
        for bg in _extract_bigrams(tokens):
            counter[bg] += 1

    return counter.most_common(top_n)


def merge_topics(
    reddit_topics: List[Tuple[str, int]],
    news_topics: List[Tuple[str, int]],
    top_n: int = 30,
) -> List[Tuple[str, int]]:
    """
    Merge Reddit and news topic counts into a single ranked list.

    News mentions are scaled up slightly (×2) because they represent
    editorial judgment rather than upvote gaming.

    Returns:
        Combined top-N (keyword, combined_score) pairs.
    """
    combined: Counter = Counter()
    for kw, score in reddit_topics:
        combined[kw] += score
    for kw, score in news_topics:
        combined[kw] += score * 2

    return combined.most_common(top_n)


def extract(
    posts: List[Dict[str, Any]],
    articles: List[Dict[str, Any]],
    top_n: int = 30,
) -> List[Tuple[str, int]]:
    """
    High-level helper: extract and merge topics from both sources.

    Args:
        posts:    Reddit posts (from reddit_collector.collect).
        articles: News articles (from news_collector.collect).
        top_n:    Number of top topics to return.

    Returns:
        List of (topic_keyword, score) tuples, highest-score first.
    """
    reddit_topics = extract_from_reddit(posts, top_n=top_n * 2)
    news_topics = extract_from_news(articles, top_n=top_n * 2)
    merged = merge_topics(reddit_topics, news_topics, top_n=top_n)
    logger.info("Top topics: %s", [t for t, _ in merged[:10]])
    return merged
