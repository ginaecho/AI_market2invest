"""
eToro market-data collector — resolves tickers to eToro instruments and
fetches live bid/ask rates plus display metadata (name, logo, daily change).

Requires ETORO_API_KEY and ETORO_USER_KEY in the environment.
See https://api-portal.etoro.com/
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

_BASE_URL = "https://public-api.etoro.com/api/v1"
_TIMEOUT = 20


def is_configured() -> bool:
    return bool(os.getenv("ETORO_API_KEY", "").strip() and os.getenv("ETORO_USER_KEY", "").strip())


def _headers() -> Dict[str, str]:
    return {
        "x-api-key": os.getenv("ETORO_API_KEY", "").strip(),
        "x-user-key": os.getenv("ETORO_USER_KEY", "").strip(),
        "x-request-id": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


def _search_instrument(ticker: str) -> Optional[Dict[str, Any]]:
    symbol = ticker.upper().strip()
    url = f"{_BASE_URL}/market-data/search"
    try:
        resp = requests.get(
            url,
            headers=_headers(),
            params={"internalSymbolFull": symbol},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("eToro search failed for %s: %s", symbol, exc)
        return None

    items = resp.json().get("items") or []
    for item in items:
        if (item.get("internalSymbolFull") or "").upper() == symbol:
            return item
    return items[0] if items else None


def _fetch_rate(instrument_id: int) -> Optional[Dict[str, Any]]:
    url = f"{_BASE_URL}/market-data/instruments/rates"
    try:
        resp = requests.get(
            url,
            headers=_headers(),
            params={"instrumentIds": instrument_id},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("eToro rates failed for instrument %s: %s", instrument_id, exc)
        return None

    rates = resp.json().get("rates") or []
    return rates[0] if rates else None


def collect_quotes(tickers: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Return eToro quote metadata keyed by ticker symbol.

    Each value may include: instrument_id, display_name, logo_url, bid, ask,
    last, change_pct (daily), is_tradable, exchange, error.
    """
    if not is_configured():
        logger.info("eToro keys not set — skipping eToro quotes")
        return {}

    result: Dict[str, Dict[str, Any]] = {}
    for ticker in tickers:
        symbol = ticker.upper().strip()
        if not symbol:
            continue

        search = _search_instrument(symbol)
        if not search:
            result[symbol] = {"error": "instrument not found on eToro"}
            continue

        instrument_id = search.get("internalInstrumentId")
        if instrument_id is None:
            result[symbol] = {"error": "missing instrument id"}
            continue

        rate = _fetch_rate(int(instrument_id))
        bid = rate.get("bid") if rate else search.get("currentRate")
        ask = rate.get("ask") if rate else search.get("currentRate")
        last = rate.get("lastExecution") if rate else search.get("currentRate")
        if last == 0.0:
            last = ask or bid or search.get("internalClosingPrice")

        logo = search.get("logo50x50") or search.get("logo35x35")
        if logo and logo.startswith("/"):
            logo = f"https://www.etoro.com{logo}"

        result[symbol] = {
            "instrument_id": instrument_id,
            "display_name": search.get("internalInstrumentDisplayName") or symbol,
            "logo_url": logo,
            "bid": round(float(bid), 4) if bid is not None else None,
            "ask": round(float(ask), 4) if ask is not None else None,
            "last": round(float(last), 4) if last is not None else None,
            "change_pct": round(float(search.get("dailyPriceChange") or 0), 2),
            "is_tradable": bool(search.get("isBuyEnabled")),
            "exchange": search.get("internalExchangeName"),
            "is_exchange_open": bool(search.get("isExchangeOpen")),
            "error": None,
        }

    ok = len([v for v in result.values() if not v.get("error")])
    logger.info("eToro quotes fetched for %d/%d tickers", ok, len(tickers))
    return result
