"""
Specialized news-collection agents powered by Kimi.

Each agent focuses on a specific domain and uses the Kimi API to:
1. Generate targeted search queries.
2. Collect articles via Bing News RSS (no API key needed).
3. Extract structured intelligence (tickers, sentiment, impact).

SECURITY NOTES
--------------
• Inherits all security from BaseAgent and web_fetcher.
• No arbitrary code execution.
• HTTPS-only, domain-whitelisted fetches.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from src.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class TrumpAgent(BaseAgent):
    """Agent focused on Trump policies, tariffs, executive orders, and political market impact."""

    name = "TrumpAgent"
    max_queries = 5
    max_articles_per_query = 8

    def _build_system_prompt(self) -> str:
        return (
            "You are an expert political-risk analyst specializing in U.S. presidential policy, "
            "particularly the Trump administration. You track executive orders, tariff announcements, "
            "trade negotiations, regulatory changes, and their direct impact on stock markets. "
            "You know which sectors and tickers are most sensitive to Trump policy shifts."
        )

    def _generate_queries(self) -> List[str]:
        # Use Kimi for dynamic queries, but seed with strong defaults
        base_queries = [
            "Trump tariff announcement today",
            "Trump executive order stock market impact",
            "Trump trade war China sanctions",
            "Trump policy change energy sector",
            "Trump election 2026 market reaction",
        ]
        kimi_queries = super()._generate_queries()
        # Merge: Kimi queries first, then base as fallback / supplement
        combined = kimi_queries + [q for q in base_queries if q not in kimi_queries]
        return combined[:self.max_queries]


class GeopoliticsAgent(BaseAgent):
    """Agent focused on international conflicts, sanctions, diplomacy, and defense stocks."""

    name = "GeopoliticsAgent"
    max_queries = 5
    max_articles_per_query = 8

    def _build_system_prompt(self) -> str:
        return (
            "You are a geopolitical risk analyst. You monitor international conflicts, "
            "sanctions regimes, diplomatic breakthroughs or breakdowns, NATO dynamics, "
            "Middle East tensions, and Taiwan/China relations. You identify which defense, "
            "energy, semiconductor, and commodity stocks are most exposed."
        )

    def _generate_queries(self) -> List[str]:
        base_queries = [
            "Middle East conflict oil price impact",
            "NATO defense spending Lockheed Raytheon",
            "China Taiwan semiconductor sanctions",
            "Russia Ukraine sanctions energy stocks",
            "geopolitical risk market sell-off today",
        ]
        kimi_queries = super()._generate_queries()
        combined = kimi_queries + [q for q in base_queries if q not in kimi_queries]
        return combined[:self.max_queries]


class EnergyAgent(BaseAgent):
    """Agent focused on oil, gas, renewables, OPEC, and energy-transition stocks."""

    name = "EnergyAgent"
    max_queries = 5
    max_articles_per_query = 8

    def _build_system_prompt(self) -> str:
        return (
            "You are an energy-sector analyst. You track oil and natural gas prices, "
            "OPEC+ decisions, renewable energy policy, EV adoption trends, battery technology, "
            "and geopolitical disruptions to energy supply chains. You map news to tickers "
            "like XOM, CVX, TSLA, ENPH, FSLR, LNG, USO."
        )

    def _generate_queries(self) -> List[str]:
        base_queries = [
            "OPEC oil production cut decision",
            "crude oil price today Exxon Chevron",
            "renewable energy policy solar wind stocks",
            "natural gas price LNG export",
            "EV battery lithium Albemarle SQM",
        ]
        kimi_queries = super()._generate_queries()
        combined = kimi_queries + [q for q in base_queries if q not in kimi_queries]
        return combined[:self.max_queries]


class ProductTrendAgent(BaseAgent):
    """Agent focused on trending consumer products, tech launches, and viral items."""

    name = "ProductTrendAgent"
    max_queries = 4
    max_articles_per_query = 6

    def _build_system_prompt(self) -> str:
        return (
            "You are a consumer-trends analyst. You identify viral products, tech product launches, "
            "fashion trends, gaming releases, and breakout consumer brands. You connect these trends "
            "to publicly traded companies (e.g., AAPL for iPhone, NVDA for AI chips, NKE for sneakers). "
            "You focus on products that are currently gaining social-media momentum."
        )

    def _generate_queries(self) -> List[str]:
        base_queries = [
            "viral product trend TikTok",
            "tech product launch 2026 Apple Samsung",
            "gaming release Nintendo Sony Xbox",
            "consumer brand trending social media",
        ]
        kimi_queries = super()._generate_queries()
        combined = kimi_queries + [q for q in base_queries if q not in kimi_queries]
        return combined[:self.max_queries]


class SocialMediaAgent(BaseAgent):
    """
    Agent focused on social-media buzz and trending discussions.
    Uses Kimi to analyze what's hot on X/Twitter, Reddit, YouTube.
    """

    name = "SocialMediaAgent"
    max_queries = 4
    max_articles_per_query = 6

    def _build_system_prompt(self) -> str:
        return (
            "You are a social-media intelligence analyst. You track trending hashtags, "
            "viral financial discussions, meme-stock movements, and influencer sentiment. "
            "You identify which stocks are being discussed most intensely and whether "
            "the sentiment is bullish, bearish, or speculative."
        )

    def _generate_queries(self) -> List[str]:
        base_queries = [
            "trending stock Twitter X today",
            "meme stock Reddit wallstreetbets",
            "viral financial influencer stock pick",
            "YouTube finance trending video",
        ]
        kimi_queries = super()._generate_queries()
        combined = kimi_queries + [q for q in base_queries if q not in kimi_queries]
        return combined[:self.max_queries]
