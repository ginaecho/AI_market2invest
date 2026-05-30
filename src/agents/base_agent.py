"""
Base agent — abstract foundation for all LLM-powered swarm agents.

Each agent:
1. Uses a configurable LLM API to generate intelligent search queries.
2. Collects raw content via safe web fetcher / RSS / search.
3. Uses the LLM again to extract structured intelligence (tickers, sentiment, summary).
4. Returns standardized result dicts.

SECURITY NOTES
--------------
• API key read from env only; provider is configurable via config.yaml or env.
• All HTTP requests use HTTPS + timeouts.
• No eval/exec.
• Web fetcher enforces domain whitelist.
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from src.utils.llm_client import llm_chat

logger = logging.getLogger(__name__)

# Re-export for backward compatibility
from src.utils.llm_client import kimi_chat  # noqa: F401


class BaseAgent(ABC):
    """
    Abstract base for an LLM-powered news-collection agent.

    Subclasses implement:
      - ``name``: human-readable agent name
      - ``_build_system_prompt()``: instructions for the agent
      - ``_generate_queries()``: produce search queries
      - ``_extract_intelligence()``: turn raw text into structured results
    """

    name: str = "base_agent"
    max_queries: int = 5
    max_articles_per_query: int = 8

    def __init__(
        self,
        max_queries: int | None = None,
        tracker: Any = None,
        llm_config: Dict[str, Any] | None = None,
    ) -> None:
        if max_queries is not None:
            self.max_queries = max_queries
        self.tracker = tracker
        self.llm_config = llm_config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> List[Dict[str, Any]]:
        """
        Execute the full agent workflow and return collected articles.

        Returns:
            List of article dicts with keys:
                title, text, url, published, source, query,
                plus optional keys: tickers, sentiment, summary.
        """
        logger.info("[%s] Starting agent run …", self.name)

        # 1. Generate queries via LLM
        queries = self._generate_queries()
        if not queries:
            logger.info("[%s] No queries generated — skipping.", self.name)
            return []

        # 2. Collect raw content
        raw_results: List[Dict[str, Any]] = []
        for query in queries:
            results = self._collect(query)
            raw_results.extend(results)

        if not raw_results:
            logger.info("[%s] No raw content collected.", self.name)
            return []

        # 3. Deduplicate by URL
        seen_urls = set()
        deduped = []
        for r in raw_results:
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                deduped.append(r)

        # 4. Extract structured intelligence via LLM
        enriched = self._extract_intelligence(deduped)

        logger.info("[%s] Agent run complete — %d articles enriched.", self.name, len(enriched))
        return enriched

    # ------------------------------------------------------------------
    # Hooks for subclasses
    # ------------------------------------------------------------------

    @abstractmethod
    def _build_system_prompt(self) -> str:
        """Return the system prompt that defines this agent's expertise."""
        raise NotImplementedError

    def _generate_queries(self) -> List[str]:
        """
        Use LLM to generate targeted search queries.

        Subclasses may override for custom logic.
        """
        system = self._build_system_prompt()
        user = (
            f"You are a {self.name} research analyst. "
            f"Generate {self.max_queries} targeted web search queries to find the most "
            "important and recent news affecting stocks and markets in your domain. "
            "Return ONLY a JSON array of query strings, no extra text."
        )
        raw = llm_chat(
            system,
            user,
            config=self.llm_config,
            response_format_json=True,
            tracker=self.tracker,
            stage="agent_swarm",
            description=f"{self.name} query generation",
        )
        if not raw:
            return []
        try:
            queries = json.loads(raw)
            if isinstance(queries, list):
                return [str(q) for q in queries[: self.max_queries]]
        except json.JSONDecodeError:
            # Fallback: treat each non-empty line as a query
            return [
                line.strip("-\"' ")
                for line in raw.splitlines()
                if line.strip()
            ][: self.max_queries]
        return []

    def _collect(self, query: str) -> List[Dict[str, Any]]:
        """
        Collect articles for a single query.

        Default implementation uses Bing News RSS.
        Subclasses may override.
        """
        from src.agents.web_fetcher import search_bing_news

        return search_bing_news(query, max_results=self.max_articles_per_query)

    def _extract_intelligence(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Enrich collected articles with AI-extracted metadata.

        Uses LLM to extract:
          - summary: one-sentence summary
          - tickers: list of mentioned stock tickers
          - sentiment: bullish / bearish / neutral
          - impact_score: 1-10 estimated market impact
        """
        if not articles:
            return articles

        system = (
            "You are a senior financial analyst. For each article provided, extract: "
            "summary (one sentence), tickers (list of US stock tickers mentioned), "
            "sentiment (bullish/bearish/neutral), and impact_score (1-10). "
            "Return a JSON object where keys are article titles and values are objects "
            "with those four fields. If no tickers, use empty list."
        )

        # Batch in groups of 5 to stay within token limits
        batch_size = 5
        enriched = []
        for i in range(0, len(articles), batch_size):
            batch = articles[i : i + batch_size]
            context = "\n\n".join(
                f"Article {j+1}:\nTitle: {a.get('title', '')}\nText: {a.get('text', a.get('summary', ''))[:800]}"
                for j, a in enumerate(batch)
            )
            user = f"Analyze these articles and return structured JSON:\n\n{context}"
            raw = llm_chat(
                system,
                user,
                config=self.llm_config,
                response_format_json=True,
                max_tokens=2000,
                tracker=self.tracker,
                stage="agent_swarm",
                description=f"{self.name} article enrichment",
            )

            if raw:
                try:
                    analysis = json.loads(raw)
                    for article in batch:
                        key = article.get("title", "")
                        info = analysis.get(key, {}) if isinstance(analysis, dict) else {}
                        # If LLM didn't match by title, try first entry
                        if not info and isinstance(analysis, dict) and analysis:
                            info = list(analysis.values())[0]
                        article["ai_summary"] = info.get("summary", "")
                        article["ai_tickers"] = info.get("tickers", [])
                        article["ai_sentiment"] = info.get("sentiment", "neutral")
                        article["ai_impact"] = info.get("impact_score", 5)
                except json.JSONDecodeError:
                    logger.warning("[%s] Failed to parse LLM enrichment JSON", self.name)

            enriched.extend(batch)

        return enriched
