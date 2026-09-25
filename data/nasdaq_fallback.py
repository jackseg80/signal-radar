"""Read official Nasdaq daily quotes only to verify isolated Yahoo gaps."""

from __future__ import annotations

import json
import re
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def historical_url(symbol: str, previous: str, following: str) -> str:
    """Build a bounded official historical quote URL for a US ticker."""
    if not re.fullmatch(r"[A-Z0-9.\-]{1,12}", symbol):
        raise ValueError("invalid Nasdaq symbol")
    params = urlencode({
        "assetclass": "stocks", "limit": "10",
        "fromdate": previous, "todate": following,
    })
    return f"https://api.nasdaq.com/api/quote/{symbol}/historical?{params}"


def _number(value: object) -> float:
    """Parse a quoted USD price or exchange volume."""
    return float(str(value).replace("$", "").replace(",", "").strip())


def fetch_historical_bars(
    symbol: str, previous: str, following: str,
) -> tuple[str, dict[str, dict[str, float]]]:
    """Return daily OHLCV from Nasdaq, with strict response validation."""
    url = historical_url(symbol, previous, following)
    request = Request(
        url, headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
            "Origin": "https://www.nasdaq.com",
        },
    )
    with urlopen(request, timeout=12) as response:
        payload = json.load(response)
    if payload.get("status", {}).get("rCode") != 200:
        raise ValueError(f"Nasdaq did not return historical prices for {symbol}")
    rows = ((payload.get("data") or {}).get("tradesTable") or {}).get("rows")
    if not isinstance(rows, list):
        raise ValueError(f"Nasdaq historical response missing rows for {symbol}")
    bars: dict[str, dict[str, float]] = {}
    for row in rows:
        try:
            session = datetime.strptime(row["date"], "%m/%d/%Y").date().isoformat()
            bar = {
                "open": _number(row["open"]), "high": _number(row["high"]),
                "low": _number(row["low"]), "close": _number(row["close"]),
                "volume": _number(row["volume"]),
            }
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid Nasdaq historical bar for {symbol}") from exc
        if (min(bar["open"], bar["high"], bar["low"], bar["close"]) <= 0
                or bar["volume"] < 0
                or bar["low"] > min(bar["open"], bar["close"])
                or bar["high"] < max(bar["open"], bar["close"])):
            raise ValueError(f"Impossible Nasdaq OHLC for {symbol} on {session}")
        if session in bars:
            raise ValueError(f"Duplicate Nasdaq date for {symbol}: {session}")
        bars[session] = bar
    return url, bars
