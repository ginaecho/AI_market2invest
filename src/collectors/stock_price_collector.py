"""
Stock price collector — fetches current price, change %, and volume for
a list of tickers using the yfinance library.

SECURITY NOTES
--------------
• yfinance is a well-known, open-source Python library that queries Yahoo
  Finance public endpoints.  No API key is required.
• All data is read-only.
• Requests are batched and cached to minimise external calls.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


def collect(tickers: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Fetch current price data for the given tickers.

    Args:
        tickers: List of ticker symbols (e.g. ["AAPL", "TSLA", "NVDA"]).

    Returns:
        Dict mapping ticker symbol to a dict with keys:
            - price:          float (last close or current price)
            - change_pct:     float (1-day % change)
            - volume:         int   (latest volume)
            - market_cap:     float | None
            - fifty_two_week_high: float | None
            - fifty_two_week_low:  float | None
            - error:          str | None (if fetch failed)
    """
    try:
        import yfinance as yf  # type: ignore[import]
    except ImportError:
        logger.error("yfinance not installed — cannot fetch stock prices")
        return {}

    result: Dict[str, Dict[str, Any]] = {}
    # yfinance.Tickers allows batch download
    try:
        tickers_str = " ".join(tickers)
        data = yf.Tickers(tickers_str)
        for ticker in tickers:
            try:
                info = data.tickers[ticker].info
                hist = data.tickers[ticker].history(period="2d")
                if len(hist) >= 2:
                    prev_close = hist["Close"].iloc[-2]
                    curr_close = hist["Close"].iloc[-1]
                    change_pct = round(((curr_close - prev_close) / prev_close) * 100, 2)
                elif len(hist) == 1:
                    curr_close = hist["Close"].iloc[-1]
                    prev_close = info.get("previousClose", curr_close)
                    change_pct = round(((curr_close - prev_close) / prev_close) * 100, 2) if prev_close else 0.0
                else:
                    curr_close = info.get("currentPrice") or info.get("regularMarketPrice") or 0.0
                    prev_close = info.get("previousClose", curr_close)
                    change_pct = round(((curr_close - prev_close) / prev_close) * 100, 2) if prev_close else 0.0

                result[ticker] = {
                    "price": round(curr_close, 2) if curr_close else None,
                    "change_pct": change_pct,
                    "volume": info.get("volume") or info.get("regularMarketVolume"),
                    "market_cap": info.get("marketCap"),
                    "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
                    "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
                    "error": None,
                }
            except Exception as exc:
                logger.warning("Failed to fetch %s: %s", ticker, exc)
                result[ticker] = {"error": str(exc)}
    except Exception as exc:
        logger.error("Batch yfinance download failed: %s", exc)
        # Fallback: try one by one
        for ticker in tickers:
            try:
                stock = yf.Ticker(ticker)
                info = stock.info
                hist = stock.history(period="2d")
                if len(hist) >= 2:
                    prev_close = hist["Close"].iloc[-2]
                    curr_close = hist["Close"].iloc[-1]
                    change_pct = round(((curr_close - prev_close) / prev_close) * 100, 2)
                else:
                    curr_close = info.get("currentPrice") or info.get("regularMarketPrice") or 0.0
                    prev_close = info.get("previousClose", curr_close)
                    change_pct = round(((curr_close - prev_close) / prev_close) * 100, 2) if prev_close else 0.0
                result[ticker] = {
                    "price": round(curr_close, 2) if curr_close else None,
                    "change_pct": change_pct,
                    "volume": info.get("volume") or info.get("regularMarketVolume"),
                    "market_cap": info.get("marketCap"),
                    "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
                    "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
                    "error": None,
                }
            except Exception as exc2:
                logger.warning("Fallback fetch failed for %s: %s", ticker, exc2)
                result[ticker] = {"error": str(exc2)}

    logger.info("Stock prices fetched for %d/%d tickers", len([r for r in result.values() if not r.get("error")]), len(tickers))
    return result
