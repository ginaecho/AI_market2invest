"""
Market chart collector — OHLCV candle series for multiple intraday/daily
timeframes via yfinance (used for eToro-style price charts in the dashboard).

eToro's public candles endpoint is not available on all API tiers; yfinance
provides reliable intraday history for US equities and ETFs.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# UI label → (yfinance interval, period, max points to embed)
TIMEFRAMES: Dict[str, Tuple[str, str, int]] = {
    "1M": ("1m", "1d", 180),
    "5M": ("5m", "5d", 180),
    "10M": ("5m", "5d", 120),  # nearest available; sampled every 2nd bar in UI
    "15M": ("15m", "5d", 120),
    "30M": ("30m", "5d", 100),
    "1H": ("1h", "1mo", 120),
    "1D": ("1d", "3mo", 90),
    "1W": ("1wk", "2y", 104),
    "1MO": ("1mo", "5y", 60),
}


def collect(
    tickers: List[str],
    timeframes: Optional[List[str]] = None,
) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """
    Fetch OHLCV series for each ticker and timeframe label.

    Returns:
        { "AAPL": { "1M": [{t, o, h, l, c, v}, ...], "5M": [...], ... }, ... }
    """
    try:
        import yfinance as yf  # type: ignore[import]
    except ImportError:
        logger.error("yfinance not installed — cannot fetch market charts")
        return {}

    labels = timeframes or list(TIMEFRAMES.keys())
    result: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

    for ticker in tickers:
        symbol = ticker.upper().strip()
        if not symbol:
            continue
        ticker_frames: Dict[str, List[Dict[str, Any]]] = {}
        try:
            stock = yf.Ticker(symbol)
            for label in labels:
                spec = TIMEFRAMES.get(label)
                if not spec:
                    continue
                interval, period, max_points = spec
                hist = stock.history(period=period, interval=interval)
                if hist is None or hist.empty:
                    continue
                rows = _history_to_candles(hist, max_points, sample_every=2 if label == "10M" else 1)
                if rows:
                    ticker_frames[label] = rows
        except Exception as exc:
            logger.warning("Market chart fetch failed for %s: %s", symbol, exc)
        if ticker_frames:
            result[symbol] = ticker_frames

    logger.info(
        "Market charts fetched for %d/%d tickers (%d timeframes each max)",
        len(result),
        len(tickers),
        len(labels),
    )
    return result


def _history_to_candles(hist: Any, max_points: int, sample_every: int = 1) -> List[Dict[str, Any]]:
    """Convert a yfinance history DataFrame to compact candle dicts."""
    candles: List[Dict[str, Any]] = []
    df = hist.tail(max_points * sample_every)
    for idx, row in df.iterrows():
        ts = int(idx.timestamp()) if hasattr(idx, "timestamp") else 0
        candles.append(
            {
                "t": ts,
                "o": round(float(row["Open"]), 4),
                "h": round(float(row["High"]), 4),
                "l": round(float(row["Low"]), 4),
                "c": round(float(row["Close"]), 4),
                "v": int(row.get("Volume", 0) or 0),
            }
        )
    if sample_every > 1:
        candles = candles[::sample_every]
    return candles[-max_points:]
