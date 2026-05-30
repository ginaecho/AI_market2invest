"""
Coordinator — orchestrates the Kimi agent swarm.

Runs multiple specialized agents in parallel, deduplicates results,
and merges them into the pipeline's standard article format.

SECURITY NOTES
--------------
• Uses ThreadPoolExecutor for parallelism — no subprocesses.
• No eval/exec.
• All agent I/O goes through base_agent / web_fetcher security layers.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List

from src.agents.news_agents import (
    TrumpAgent,
    GeopoliticsAgent,
    EnergyAgent,
    ProductTrendAgent,
    SocialMediaAgent,
)

logger = logging.getLogger(__name__)

_AGENT_REGISTRY: Dict[str, type] = {
    "trump": TrumpAgent,
    "geopolitics": GeopoliticsAgent,
    "energy": EnergyAgent,
    "products": ProductTrendAgent,
    "social": SocialMediaAgent,
}


def run_swarm(
    enabled_agents: List[str] | None = None,
    max_workers: int = 5,
    max_queries_per_agent: int | None = None,
    tracker: Any = None,
    llm_config: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    """
    Run the full agent swarm and return collected articles.

    Args:
        enabled_agents: List of agent names to run (e.g. ["trump", "energy"]).
                        Defaults to all registered agents.
        max_workers:    Number of parallel threads.
        max_queries_per_agent: Override max queries per agent.
        tracker:        CostTracker instance for logging API usage.

    Returns:
        Flat list of article dicts with standard keys + AI enrichment keys.
    """
    if enabled_agents is None:
        enabled_agents = list(_AGENT_REGISTRY.keys())

    agents = []
    for name in enabled_agents:
        cls = _AGENT_REGISTRY.get(name)
        if cls:
            agents.append(
                cls(
                    max_queries=max_queries_per_agent,
                    tracker=tracker,
                    llm_config=llm_config,
                )
            )
        else:
            logger.warning("Unknown agent '%s' — skipping.", name)

    if not agents:
        logger.warning("No agents enabled — swarm returning empty.")
        return []

    logger.info("Starting agent swarm with %d agents …", len(agents))

    all_articles: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_agent = {executor.submit(agent.run): agent for agent in agents}
        for future in as_completed(future_to_agent):
            agent = future_to_agent[future]
            try:
                articles = future.result()
                logger.info("[%s] returned %d articles", agent.name, len(articles))
                all_articles.extend(articles)
            except Exception as exc:
                logger.error("[%s] agent crashed: %s", agent.name, exc)

    # Global deduplication by URL
    seen_urls = set()
    deduped = []
    for article in all_articles:
        url = article.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            deduped.append(article)

    logger.info(
        "Agent swarm complete — %d total articles, %d unique.",
        len(all_articles),
        len(deduped),
    )
    return deduped


def list_agents() -> List[str]:
    """Return list of available agent names."""
    return list(_AGENT_REGISTRY.keys())
