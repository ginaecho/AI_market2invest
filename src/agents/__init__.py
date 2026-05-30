"""Agent swarm package — specialized Kimi-powered agents for news collection."""

from src.agents import coordinator
from src.agents.news_agents import TrumpAgent, GeopoliticsAgent, EnergyAgent
from src.agents.news_agents import ProductTrendAgent, SocialMediaAgent

__all__ = [
    "coordinator",
    "TrumpAgent",
    "GeopoliticsAgent",
    "EnergyAgent",
    "ProductTrendAgent",
    "SocialMediaAgent",
]
