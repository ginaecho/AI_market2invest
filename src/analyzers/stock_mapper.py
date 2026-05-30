"""
Stock mapper — maps extracted topics to investable stock tickers and
generates investment rationale.

Two-tier approach
-----------------
1. **Keyword dictionary** (always available):  A curated mapping from common
   words / phrases to ticker symbols, grouped by sector theme.

2. **OpenAI / Kimi enrichment** (optional):  When ``OPENAI_API_KEY`` or
   ``KIMI_API_KEY`` is set, the top topics and most-relevant news headlines
   are fed to an LLM to produce richer, narrative-style investment reasoning.
   The keyword mapping is still used to bootstrap ticker candidates.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keyword → ticker(s) mapping
# Phrases are matched as substrings (case-insensitive) against topic text.
# The order matters: more specific phrases should come before generic ones.
# ---------------------------------------------------------------------------
KEYWORD_TICKER_MAP: Dict[str, List[str]] = {
    # ── Mega-cap Tech ────────────────────────────────────────────────────
    "apple": ["AAPL"],
    "iphone": ["AAPL"],
    "ipad": ["AAPL"],
    "macbook": ["AAPL"],
    "app store": ["AAPL"],
    "microsoft": ["MSFT"],
    "azure": ["MSFT"],
    "copilot": ["MSFT"],
    "bing": ["MSFT"],
    "google": ["GOOGL"],
    "alphabet": ["GOOGL"],
    "youtube": ["GOOGL"],
    "waymo": ["GOOGL"],
    "amazon": ["AMZN"],
    "aws": ["AMZN"],
    "alexa": ["AMZN"],
    "prime": ["AMZN"],
    "meta": ["META"],
    "facebook": ["META"],
    "instagram": ["META"],
    "whatsapp": ["META"],
    "threads": ["META"],
    "oculus": ["META"],
    "nvidia": ["NVDA"],
    "nvda": ["NVDA"],
    "cuda": ["NVDA"],
    "blackwell": ["NVDA"],
    "h100": ["NVDA"],
    "tesla": ["TSLA"],
    "elon musk": ["TSLA"],
    "autopilot": ["TSLA"],
    "supercharger": ["TSLA"],
    "netflix": ["NFLX"],
    "disney": ["DIS"],
    "disney+": ["DIS"],
    "hulu": ["DIS"],
    "espn": ["DIS"],
    # ── AI / LLM ─────────────────────────────────────────────────────────
    "artificial intelligence": ["NVDA", "MSFT", "GOOGL", "META", "AMZN"],
    "generative ai": ["NVDA", "MSFT", "GOOGL", "META"],
    "large language model": ["NVDA", "MSFT", "GOOGL"],
    "chatgpt": ["MSFT", "NVDA"],
    "openai": ["MSFT"],
    "gpt": ["MSFT", "NVDA"],
    "llm": ["NVDA", "MSFT", "GOOGL"],
    "ai agent": ["NVDA", "MSFT", "GOOGL", "AMZN"],
    "gemini": ["GOOGL"],
    "claude": ["AMZN"],
    "anthropic": ["AMZN", "GOOGL"],
    "hugging face": ["AMZN", "MSFT"],
    # ── Semiconductors ───────────────────────────────────────────────────
    "semiconductor": ["NVDA", "AMD", "INTC", "QCOM", "TSM", "ASML"],
    "chip": ["NVDA", "AMD", "INTC", "QCOM"],
    "amd": ["AMD"],
    "intel": ["INTC"],
    "qualcomm": ["QCOM"],
    "arm": ["ARM"],
    "tsmc": ["TSM"],
    "asml": ["ASML"],
    "broadcom": ["AVGO"],
    "marvell": ["MRVL"],
    # ── Cloud Computing ──────────────────────────────────────────────────
    "cloud": ["AMZN", "MSFT", "GOOGL"],
    "cloud computing": ["AMZN", "MSFT", "GOOGL"],
    "saas": ["CRM", "NOW", "WDAY", "SNOW"],
    "salesforce": ["CRM"],
    "oracle": ["ORCL"],
    "snowflake": ["SNOW"],
    "datadog": ["DDOG"],
    "cloudflare": ["NET"],
    "servicenow": ["NOW"],
    "workday": ["WDAY"],
    "palantir": ["PLTR"],
    # ── Cybersecurity ────────────────────────────────────────────────────
    "cybersecurity": ["CRWD", "PANW", "ZS", "FTNT", "S"],
    "crowdstrike": ["CRWD"],
    "palo alto": ["PANW"],
    "zscaler": ["ZS"],
    "fortinet": ["FTNT"],
    "data breach": ["CRWD", "PANW", "ZS"],
    "ransomware": ["CRWD", "PANW", "ZS", "FTNT"],
    "hack": ["CRWD", "PANW"],
    # ── EV / Clean Energy ────────────────────────────────────────────────
    "electric vehicle": ["TSLA", "RIVN", "LCID", "F", "GM"],
    "ev charging": ["TSLA", "CHPT", "BLNK"],
    "rivian": ["RIVN"],
    "lucid": ["LCID"],
    "ford": ["F"],
    "general motors": ["GM"],
    "solar": ["ENPH", "FSLR", "SEDG"],
    "clean energy": ["NEE", "ENPH", "BEP"],
    "battery": ["TSLA", "QS", "ENVX"],
    "lithium": ["ALB", "SQM", "LAC"],
    # ── Finance / Banks / Macro ──────────────────────────────────────────
    "jpmorgan": ["JPM"],
    "goldman sachs": ["GS"],
    "morgan stanley": ["MS"],
    "bank of america": ["BAC"],
    "citigroup": ["C"],
    "wells fargo": ["WFC"],
    "blackrock": ["BLK"],
    "berkshire": ["BRK.B"],
    "interest rate": ["JPM", "BAC", "TLT", "SHY"],
    "federal reserve": ["SPY", "QQQ", "TLT"],
    "fed rate": ["SPY", "QQQ", "TLT"],
    "rate cut": ["SPY", "QQQ", "TLT", "XLU"],
    "rate hike": ["SHY", "GLD", "XLF"],
    "inflation": ["TLT", "GLD", "SHY", "TIP"],
    "deflation": ["TLT", "SPY"],
    "recession": ["GLD", "TLT", "VNQ", "XLU"],
    "yield curve": ["TLT", "SHY"],
    "treasury": ["TLT", "BND"],
    "dollar": ["UUP", "GLD"],
    # ── Crypto ───────────────────────────────────────────────────────────
    "bitcoin": ["COIN", "MSTR", "RIOT", "MARA"],
    "ethereum": ["COIN"],
    "crypto": ["COIN", "MSTR", "SQ"],
    "coinbase": ["COIN"],
    "microstrategy": ["MSTR"],
    "defi": ["COIN"],
    "nft": ["COIN", "META"],
    # ── Healthcare / Pharma / Biotech ────────────────────────────────────
    "pfizer": ["PFE"],
    "moderna": ["MRNA"],
    "johnson": ["JNJ"],
    "unitedhealth": ["UNH"],
    "eli lilly": ["LLY"],
    "novo nordisk": ["NVO"],
    "weight loss": ["LLY", "NVO"],
    "ozempic": ["NVO", "LLY"],
    "wegovy": ["NVO"],
    "semaglutide": ["NVO", "LLY"],
    "cancer drug": ["BMY", "MRNA", "REGN"],
    "biotech": ["XBI", "IBB"],
    "drug approval": ["XBI", "IBB"],
    "fda": ["XBI", "IBB"],
    # ── Consumer / Retail ────────────────────────────────────────────────
    "walmart": ["WMT"],
    "target": ["TGT"],
    "costco": ["COST"],
    "amazon retail": ["AMZN"],
    "home depot": ["HD"],
    "lowe's": ["LOW"],
    "starbucks": ["SBUX"],
    "mcdonalds": ["MCD"],
    "yum brands": ["YUM"],
    "nike": ["NKE"],
    "luxury": ["LVMH", "MC.PA", "RMS.PA"],
    "consumer spending": ["XLY", "AMZN", "WMT"],
    # ── E-commerce / Payments ────────────────────────────────────────────
    "e-commerce": ["AMZN", "SHOP", "EBAY"],
    "shopify": ["SHOP"],
    "paypal": ["PYPL"],
    "stripe": ["PYPL"],  # private, but related sentiment
    "visa": ["V"],
    "mastercard": ["MA"],
    "block": ["SQ"],
    "affirm": ["AFRM"],
    "buy now pay later": ["AFRM", "PYPL"],
    "fintech": ["SQ", "PYPL", "AFRM"],
    # ── Social Media / Content ───────────────────────────────────────────
    "social media": ["META", "SNAP", "PINS"],
    "tiktok": ["META", "GOOGL"],  # competitor dynamic
    "snapchat": ["SNAP"],
    "snap": ["SNAP"],
    "pinterest": ["PINS"],
    "twitter": ["MSFT"],  # X is private, MSFT beneficiary
    "x.com": ["MSFT"],
    "advertising": ["META", "GOOGL", "TTD"],
    "programmatic": ["TTD"],
    # ── Travel / Leisure ─────────────────────────────────────────────────
    "travel": ["ABNB", "BKNG", "UAL", "DAL"],
    "airbnb": ["ABNB"],
    "booking": ["BKNG"],
    "expedia": ["EXPE"],
    "airlines": ["UAL", "DAL", "AAL"],
    "united airlines": ["UAL"],
    "delta": ["DAL"],
    "cruise": ["CCL", "RCL", "NCLH"],
    "carnival": ["CCL"],
    "hotel": ["MAR", "HLT", "H"],
    "marriott": ["MAR"],
    # ── Gig Economy / Delivery ───────────────────────────────────────────
    "uber": ["UBER"],
    "lyft": ["LYFT"],
    "doordash": ["DASH"],
    "instacart": ["CART"],
    "gig economy": ["UBER", "LYFT", "DASH"],
    # ── Gaming ───────────────────────────────────────────────────────────
    "gaming": ["ATVI", "EA", "NTDOY", "SONY"],
    "activision": ["ATVI"],
    "electronic arts": ["EA"],
    "nintendo": ["NTDOY"],
    "playstation": ["SONY"],
    "xbox": ["MSFT"],
    "roblox": ["RBLX"],
    "unity": ["U"],
    # ── Energy / Commodities ─────────────────────────────────────────────
    "oil": ["XOM", "CVX", "BP", "XLE"],
    "crude oil": ["XOM", "CVX", "USO"],
    "natural gas": ["XOM", "CVX", "LNG"],
    "exxon": ["XOM"],
    "chevron": ["CVX"],
    "energy crisis": ["XOM", "CVX", "BP"],
    "gold": ["GLD", "GDX", "NEM"],
    "silver": ["SLV", "PAAS"],
    "copper": ["FCX", "SCCO"],
    "uranium": ["URA", "CCJ"],
    # ── Real Estate ──────────────────────────────────────────────────────
    "real estate": ["VNQ", "AMT", "PLD"],
    "reit": ["VNQ", "O", "AMT"],
    "housing market": ["LEN", "DHI", "PHM"],
    "mortgage": ["RKT", "UWMC"],
    # ── Defence / Aerospace ──────────────────────────────────────────────
    "defence": ["LMT", "RTX", "NOC", "GD"],
    "defense": ["LMT", "RTX", "NOC", "GD"],
    "lockheed": ["LMT"],
    "raytheon": ["RTX"],
    "nato": ["LMT", "RTX", "NOC"],
    "space": ["SPCE", "MAXR", "IRDM"],
    # ── Broad Market ETFs ────────────────────────────────────────────────
    "s&p 500": ["SPY", "VOO"],
    "nasdaq": ["QQQ", "QQQM"],
    "dow jones": ["DIA"],
    "russell 2000": ["IWM"],
    "volatility": ["VIX", "VIXY"],
    "etf": ["SPY", "QQQ", "VTI"],
    "index fund": ["SPY", "VTI", "VXUS"],
    # ── Supply Chain / Logistics ─────────────────────────────────────────
    "supply chain": ["FDX", "UPS", "MAERSK"],
    "fedex": ["FDX"],
    "ups": ["UPS"],
    "freight": ["FDX", "UPS", "ZIM"],
    "shipping": ["ZIM", "MATX"],
    # ── Trump / Geopolitics ──────────────────────────────────────────────
    "trump": ["DJT", "XOM", "CVX", "LMT", "RTX", "GLD", "TLT"],
    "tariff": ["WMT", "AMZN", "CAT", "DE"],
    "trade war": ["AAPL", "NVDA", "TSM", "CAT", "DE"],
    "sanctions": ["XOM", "CVX", "BP", "GLD"],
    "middle east": ["XOM", "CVX", "LNG", "USO"],
    "ukraine": ["LMT", "RTX", "NOC", "GD"],
    "israel": ["LMT", "RTX", "NOC"],
    "taiwan": ["TSM", "NVDA", "AMD"],
    "china trade": ["AAPL", "AMZN", "NVDA", "TSM"],
}

# Sector-level themes mapped to sector ETFs
SECTOR_MAP: Dict[str, List[str]] = {
    "technology": ["XLK", "QQQ"],
    "healthcare": ["XLV", "XBI"],
    "financial": ["XLF", "KBE"],
    "energy": ["XLE", "VDE"],
    "consumer discretionary": ["XLY"],
    "consumer staples": ["XLP"],
    "utilities": ["XLU"],
    "industrials": ["XLI"],
    "materials": ["XLB"],
    "real estate": ["XLRE", "VNQ"],
    "communication services": ["XLC"],
}


def map_topics_to_stocks(
    topics: List[Tuple[str, int]],
    posts: List[Dict[str, Any]] | None = None,
    articles: List[Dict[str, Any]] | None = None,
    tweets: List[Dict[str, Any]] | None = None,
    videos: List[Dict[str, Any]] | None = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Map extracted topic keywords to stock tickers.

    Args:
        topics:   Output of topic_extractor.extract — (keyword, score) pairs.
        posts:    Raw Reddit posts (used for building evidence snippets).
        articles: Raw news articles (used for building evidence snippets).
        tweets:   Raw tweets.
        videos:   Raw YouTube videos.

    Returns:
        Dict keyed by ticker symbol.  Each value contains::

            {
                "ticker": "NVDA",
                "score":  750,
                "reasons": [...],
                "news_snippets": [...],
                "reddit_snippets": [...],
                "twitter_snippets": [...],
                "youtube_snippets": [...],
                "news_count": 3,
            }
    """
    posts = posts or []
    articles = articles or []
    tweets = tweets or []
    videos = videos or []

    ticker_data: Dict[str, Dict[str, Any]] = {}

    for keyword, score in topics:
        kw_lower = keyword.lower()
        matched_tickers: List[str] = []

        for phrase, tickers in KEYWORD_TICKER_MAP.items():
            if phrase in kw_lower or kw_lower in phrase:
                matched_tickers.extend(tickers)

        for ticker in set(matched_tickers):
            if ticker not in ticker_data:
                ticker_data[ticker] = {
                    "ticker": ticker,
                    "score": 0,
                    "reasons": [],
                    "news_snippets": [],
                    "reddit_snippets": [],
                    "twitter_snippets": [],
                    "youtube_snippets": [],
                    "news_sources": [],
                    "reddit_sources": [],
                    "twitter_sources": [],
                    "youtube_sources": [],
                    "news_count": 0,
                }
            ticker_data[ticker]["score"] += score
            ticker_data[ticker]["reasons"].append(f"'{keyword}' (score {score})")

    # Aggregate news count per ticker
    for article in articles:
        text = (article.get("title", "") + " " + article.get("summary", "")).lower()
        for ticker, data in ticker_data.items():
            if ticker.lower() in text:
                data["news_count"] = data.get("news_count", 0) + 1

    # Add supporting evidence snippets + source URLs
    for ticker, data in ticker_data.items():
        ticker_lower = ticker.lower()
        # News
        for article in articles:
            text = (article.get("title", "") + " " + article.get("summary", "")).lower()
            if ticker_lower in text or any(
                reason.split("'")[1] in text
                for reason in data["reasons"][:5]
                if "'" in reason
            ):
                snippet = article.get("title", "")
                url = article.get("url", "")
                if snippet and snippet not in data["news_snippets"]:
                    data["news_snippets"].append(snippet)
                    data["news_sources"].append({"title": snippet, "url": url})
                if len(data["news_snippets"]) >= 5:
                    break

        # Reddit
        for post in posts:
            text = (post.get("title", "") + " " + post.get("text", "")).lower()
            if ticker_lower in text or any(
                reason.split("'")[1] in text
                for reason in data["reasons"][:5]
                if "'" in reason
            ):
                snippet = post.get("title", "")
                url = post.get("url", "")
                if snippet and snippet not in data["reddit_snippets"]:
                    data["reddit_snippets"].append(snippet)
                    data["reddit_sources"].append({"title": snippet, "url": url})
                if len(data["reddit_snippets"]) >= 5:
                    break

        # Twitter
        for tweet in tweets:
            text = tweet.get("text", "").lower()
            if ticker_lower in text:
                snippet = tweet.get("text", "")[:200]
                url = tweet.get("url", "")
                if snippet and snippet not in data["twitter_snippets"]:
                    data["twitter_snippets"].append(snippet)
                    data["twitter_sources"].append({"text": snippet, "url": url})
                if len(data["twitter_snippets"]) >= 5:
                    break

        # YouTube
        for video in videos:
            text = (video.get("title", "") + " " + video.get("description", "")).lower()
            if ticker_lower in text:
                snippet = video.get("title", "")
                url = video.get("url", "")
                if snippet and snippet not in data["youtube_snippets"]:
                    data["youtube_snippets"].append(snippet)
                    data["youtube_sources"].append({"title": snippet, "url": url})
                if len(data["youtube_snippets"]) >= 5:
                    break

    return ticker_data


# ---------------------------------------------------------------------------
# Generic LLM enrichment
# ---------------------------------------------------------------------------

def enrich_with_llm(
    ticker_data: Dict[str, Dict[str, Any]],
    topics: List[Tuple[str, int]],
    articles: List[Dict[str, Any]],
    tracker: Any = None,
    config: Dict[str, Any] | None = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Use the configured LLM to produce narrative investment rationale for each ticker.

    Only runs when an API key is available for the configured provider.
    Augments each ticker entry with an ``"ai_analysis"`` key.
    """
    from src.utils.llm_client import get_llm_config, is_llm_configured, llm_chat

    if not is_llm_configured(config):
        logger.info("No LLM API key configured — skipping LLM ticker enrichment")
        return ticker_data

    cfg = get_llm_config(config)

    top_topics = [f"{kw} ({s})" for kw, s in topics[:20]]
    top_news = [a.get("title", "") for a in articles[:15] if a.get("title")]
    top_tickers = sorted(ticker_data.values(), key=lambda x: x["score"], reverse=True)[:15]
    ticker_list = [t["ticker"] for t in top_tickers]

    system_prompt = (
        "You are a senior equity analyst. Given trending topics from Reddit and "
        "financial news, provide concise investment analysis for each stock ticker "
        "provided.  For each ticker give: signal (BUY/HOLD/WATCH/SELL), one-sentence "
        "thesis, key catalysts from the data, and risk factors.  Be factual and concise."
    )
    user_prompt = (
        f"Trending topics (keyword, engagement score):\n{json.dumps(top_topics, indent=2)}\n\n"
        f"Recent news headlines:\n" + "\n".join(f"- {h}" for h in top_news) + "\n\n"
        f"Analyse these tickers: {', '.join(ticker_list)}\n\n"
        "Respond as a JSON object where each key is a ticker symbol and the value "
        "is an object with fields: signal, thesis, catalysts (list), risks (list)."
    )

    content = llm_chat(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        config=config,
        response_format_json=True,
        temperature=0.3,
        max_tokens=2000,
        tracker=tracker,
        stage="llm_enrichment",
        description=f"{cfg['provider']} ticker enrichment",
    )

    if not content:
        return ticker_data

    try:
        analysis: Dict[str, Any] = json.loads(content)
        for ticker, info in analysis.items():
            if ticker in ticker_data:
                ticker_data[ticker]["ai_analysis"] = info
        logger.info("LLM enrichment complete for %d tickers", len(analysis))
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM ticker enrichment JSON")

    return ticker_data


# ---------------------------------------------------------------------------
# Backward-compatible aliases
# ---------------------------------------------------------------------------

def enrich_with_openai(
    ticker_data: Dict[str, Dict[str, Any]],
    topics: List[Tuple[str, int]],
    articles: List[Dict[str, Any]],
    tracker: Any = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Backward-compatible alias that forces the **OpenAI** provider.

    New code should call :func:`enrich_with_llm` directly.
    """
    return enrich_with_llm(
        ticker_data=ticker_data,
        topics=topics,
        articles=articles,
        tracker=tracker,
        config={"provider": "openai"},
    )
