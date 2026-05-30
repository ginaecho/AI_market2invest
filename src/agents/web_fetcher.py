"""
Safe web fetcher — read-only HTTP client for news article extraction.

SECURITY NOTES
--------------
• HTTPS only — rejects http:// URLs.
• Domain whitelist — only fetches from known news / financial domains.
• No JavaScript execution — pure HTML parsing with BeautifulSoup.
• Content size cap — rejects responses > 2 MB.
• Short timeouts — 10 seconds max.
• No redirects to unknown domains — validates final URL.
• No eval/exec / no shell commands.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Set
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

_MAX_CONTENT_BYTES = 2 * 1024 * 1024  # 2 MB
_REQUEST_TIMEOUT = 10
_HEADERS = {"User-Agent": "AI_market2invest/1.0 (research bot; read-only)"}

# Whitelist of allowed domains (substrings matched against netloc)
_ALLOWED_DOMAINS: Set[str] = {
    # Major news
    "reuters.com",
    "bbc.com",
    "bbc.co.uk",
    "cnbc.com",
    "marketwatch.com",
    "bloomberg.com",
    "wsj.com",
    "ft.com",
    "economist.com",
    "aljazeera.com",
    # US politics
    "politico.com",
    "axios.com",
    "thehill.com",
    "apnews.com",
    "npr.org",
    # Finance
    "yahoo.com",
    "finance.yahoo.com",
    "investopedia.com",
    "seekingalpha.com",
    "fool.com",
    "morningstar.com",
    # Energy
    "oilprice.com",
    "energycentral.com",
    "worldoil.com",
    "rigzone.com",
    # Tech / product
    "techcrunch.com",
    "theverge.com",
    "arxiv.org",
    "producthunt.com",
    # General
    "cnn.com",
    "washingtonpost.com",
    "nytimes.com",
    "forbes.com",
    "businessinsider.com",
    "guardian.com",
    "theguardian.com",
}

# Patterns that indicate non-article content (ads, trackers, etc.)
_BLOCKED_PATH_PATTERNS = [
    r"/ads?/",
    r"/tracking/",
    r"/pixel",
    r"/beacon",
    r"/api/",
    r"/ajax/",
    r"/embed",
    r"/video",
    r".css$",
    r".js$",
    r".png$",
    r".jpg$",
    r".gif$",
]


def _is_allowed_domain(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        logger.debug("Rejected non-HTTPS URL: %s", url)
        return False
    netloc = parsed.netloc.lower()
    # Strip www. prefix for matching
    if netloc.startswith("www."):
        netloc = netloc[4:]
    allowed = any(domain in netloc for domain in _ALLOWED_DOMAINS)
    if not allowed:
        logger.warning("Domain not in whitelist: %s", netloc)
    return allowed


def _is_blocked_path(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower()
    for pattern in _BLOCKED_PATH_PATTERNS:
        if re.search(pattern, path):
            logger.debug("Blocked path pattern '%s' in URL: %s", pattern, url)
            return True
    return False


def fetch_article(url: str) -> Dict[str, Any] | None:
    """
    Safely fetch and parse a news article.

    Returns:
        Dict with keys: title, text, url, published, source
        or None if fetch blocked / failed.
    """
    if not _is_allowed_domain(url):
        return None
    if _is_blocked_path(url):
        return None

    try:
        resp = requests.get(
            url,
            headers=_HEADERS,
            timeout=_REQUEST_TIMEOUT,
            allow_redirects=True,
            stream=True,
        )
        resp.raise_for_status()

        # Validate final URL after redirects
        final_url = resp.url
        if not _is_allowed_domain(final_url):
            logger.warning("Redirect led to disallowed domain: %s", final_url)
            return None

        # Limit content size
        content_length = resp.headers.get("Content-Length")
        if content_length and int(content_length) > _MAX_CONTENT_BYTES:
            logger.warning("Content too large (%s bytes): %s", content_length, url)
            return None

        content = b""
        for chunk in resp.iter_content(chunk_size=8192):
            content += chunk
            if len(content) > _MAX_CONTENT_BYTES:
                logger.warning("Content exceeded cap while streaming: %s", url)
                return None

        text = content.decode("utf-8", errors="ignore")

        # Parse with BeautifulSoup
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.error("beautifulsoup4 not installed — cannot parse HTML")
            return {"title": "", "text": text[:2000], "url": final_url, "source": _extract_domain(final_url)}

        soup = BeautifulSoup(text, "html.parser")

        # Remove script/style/nav/footer tags
        for tag in soup(["script", "style", "nav", "footer", "aside", "header"]):
            tag.decompose()

        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()

        # Try to find article body
        article_text = ""
        for selector in ["article", "[role='main']", ".article-body", ".story-body", "main", ".content"]:
            el = soup.select_one(selector)
            if el:
                article_text = el.get_text(separator=" ", strip=True)
                break
        if not article_text:
            # Fallback: all paragraph text
            article_text = " ".join(p.get_text(strip=True) for p in soup.find_all("p") if len(p.get_text(strip=True)) > 30)

        # Truncate to reasonable length
        article_text = article_text[:8000]

        # Try to extract published date
        published = ""
        for meta in soup.find_all("meta"):
            prop = meta.get("property", "").lower()
            name = meta.get("name", "").lower()
            if prop in ("article:published_time", "og:article:published_time") or name in ("publisheddate", "datepublished"):
                published = meta.get("content", "")
                break

        return {
            "title": title,
            "text": article_text,
            "url": final_url,
            "published": published,
            "source": _extract_domain(final_url),
        }

    except requests.RequestException as exc:
        logger.warning("Fetch failed for %s: %s", url, exc)
        return None
    except Exception as exc:
        logger.warning("Parse failed for %s: %s", url, exc)
        return None


def _extract_domain(url: str) -> str:
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def search_bing_news(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """
    Search Bing News RSS for a query. No API key needed.

    SECURITY: Only parses RSS XML from Bing's public endpoint.
    """
    import feedparser

    url = "https://www.bing.com/news/search"
    params = {"q": query, "format": "rss"}
    try:
        resp = requests.get(url, params=params, headers=_HEADERS, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
        results = []
        for entry in feed.entries[:max_results]:
            results.append({
                "title": entry.get("title", ""),
                "url": entry.get("link", ""),
                "summary": entry.get("summary", ""),
                "published": entry.get("published", ""),
                "source": "Bing News",
                "query": query,
            })
        logger.info("Bing News search '%s' returned %d results", query, len(results))
        return results
    except Exception as exc:
        logger.warning("Bing News search failed for '%s': %s", query, exc)
        return []


def fetch_articles(urls: List[str]) -> List[Dict[str, Any]]:
    """Batch fetch multiple articles, skipping blocked/failed ones."""
    articles = []
    for url in urls:
        article = fetch_article(url)
        if article:
            articles.append(article)
    return articles
