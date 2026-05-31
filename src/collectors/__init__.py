"""Data collectors package."""

from src.collectors import news_collector, reddit_collector
from src.collectors import stock_price_collector, twitter_collector, youtube_collector
from src.collectors import tiktok_collector, meta_collector
from src.collectors import etoro_collector, market_chart_collector

__all__ = [
    "news_collector",
    "reddit_collector",
    "stock_price_collector",
    "twitter_collector",
    "youtube_collector",
    "tiktok_collector",
    "meta_collector",
    "etoro_collector",
    "market_chart_collector",
]
