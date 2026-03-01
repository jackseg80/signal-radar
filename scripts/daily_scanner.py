"""RSI(2) Daily Signal Scanner -- Phase 2.

Evaluates RSI(2) mean reversion signals after US market close.
Universe: validated stocks (META, MSFT, GOOGL) + watchlist (NVDA).
Reads production params from config/production_params.yaml.
Writes position state to data/positions.json.
Appends signal history to data/signal_history.csv.

Usage:
    python scripts/daily_scanner.py
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from loguru import logger

# ---------------------------------------------------------------------------
# Path setup (same pattern as validate_rsi2_final.py)
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from data.base_loader import to_cache_arrays  # noqa: E402
from data.yahoo_loader import YahooLoader  # noqa: E402
from engine.indicator_cache import build_cache  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONFIG_PATH = PROJECT_ROOT / "config" / "production_params.yaml"
POSITIONS_PATH = PROJECT_ROOT / "data" / "positions.json"
HISTORY_PATH = PROJECT_ROOT / "data" / "signal_history.csv"
LOG_PATH = PROJECT_ROOT / "logs" / "scanner.log"

LOOKBACK_CALENDAR_DAYS = 600  # ~400 trading days, enough for SMA(200) warmup

HISTORY_COLUMNS = [
    "timestamp", "symbol", "signal", "rsi2", "close",
    "sma200", "sma5", "entry_price", "notes",
]


# ---------------------------------------------------------------------------
# Signal types and result
# ---------------------------------------------------------------------------


class Signal(str, Enum):
    """Signal types for the daily scanner."""

    BUY = "BUY"
    SELL = "SELL"
    SAFETY_EXIT = "SAFETY_EXIT"
    HOLD = "HOLD"
    NO_SIGNAL = "NO_SIGNAL"
    PENDING_VALID = "PENDING_VALID"
    PENDING_EXPIRED = "PENDING_EXPIRED"
    WATCH = "WATCH"


@dataclass
class SignalResult:
    """Result of evaluating a signal for one ETF."""

    signal: Signal
    symbol: str = ""
    notes: str = ""
    details: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Core signal logic (pure function — no I/O)
# ---------------------------------------------------------------------------


def evaluate_signal(
    rsi2_today: float,
    close_today: float,
    sma200_today: float,
    sma5_today: float,
    position: dict[str, Any] | None,
    *,
    rsi_entry_threshold: float = 10.0,
    sma_trend_buffer: float = 1.01,
    watchlist: bool = False,
) -> SignalResult:
    """Evaluate signal for one ticker based on today's close.

    Mirrors the exact logic from mean_reversion_backtest.py lines 129-185.
    Entry: signal on today (= backtest [i-1]), action at tomorrow's open (= [i]).
    Exit: evaluated on today's close (SMA exit / trend break).

    Parameters
    ----------
    rsi2_today : float
        RSI(2) value at today's close.
    close_today : float
        Today's adjusted close price.
    sma200_today : float
        SMA(200) at today's close.
    sma5_today : float
        SMA(5) at today's close.
    position : dict | None
        Current position state. None = no position.
        Expected keys: "status" ("pending" | "open"), optionally "entry_price".
    rsi_entry_threshold : float
        RSI threshold for BUY signal (default 10.0).
    sma_trend_buffer : float
        Buffer multiplier for SMA(200) trend filter (default 1.01).
    watchlist : bool
        If True, ticker is watchlist-only: no BUY signals emitted,
        but exits (SELL/SAFETY_EXIT) work normally on open positions.

    Returns
    -------
    SignalResult
    """
    details: dict[str, Any] = {
        "rsi2": round(rsi2_today, 2),
        "close": round(close_today, 2),
        "sma200": round(sma200_today, 2),
        "sma5": round(sma5_today, 2),
        "sma200_buffered": round(sma200_today * sma_trend_buffer, 2),
    }

    # --- PENDING position ---
    if position is not None and position.get("status") == "pending":
        trend_ok = close_today > sma200_today * sma_trend_buffer
        rsi_ok = rsi2_today < rsi_entry_threshold
        if trend_ok and rsi_ok:
            return SignalResult(
                signal=Signal.PENDING_VALID,
                notes=f"Pending BUY still valid (RSI={rsi2_today:.1f})",
                details=details,
            )
        reasons: list[str] = []
        if not rsi_ok:
            reasons.append(f"RSI(2)={rsi2_today:.1f} >= {rsi_entry_threshold}")
        if not trend_ok:
            reasons.append(f"Close < SMA200*{sma_trend_buffer}")
        return SignalResult(
            signal=Signal.PENDING_EXPIRED,
            notes=f"Pending expired: {', '.join(reasons)}",
            details=details,
        )

    # --- OPEN position: check exits (priority order matches backtest) ---
    if position is not None and position.get("status") == "open":
        # Phase 3: SMA exit — close > SMA5 (backtest line 142-146)
        if close_today > sma5_today:
            return SignalResult(
                signal=Signal.SELL,
                notes=(
                    f"Close ({close_today:.2f}) > SMA5 ({sma5_today:.2f})"
                    " — sell at next open"
                ),
                details=details,
            )
        # Phase 5: Trend break — close < SMA200 (backtest line 155-159)
        if close_today < sma200_today:
            return SignalResult(
                signal=Signal.SAFETY_EXIT,
                notes=(
                    f"Close ({close_today:.2f}) < SMA200 ({sma200_today:.2f})"
                    " — safety exit at next open"
                ),
                details=details,
            )
        return SignalResult(
            signal=Signal.HOLD,
            notes="No exit condition met",
            details=details,
        )

    # --- NO position: check entry ---
    trend_ok = close_today > sma200_today * sma_trend_buffer
    rsi_ok = rsi2_today < rsi_entry_threshold

    if watchlist:
        if trend_ok and rsi_ok:
            return SignalResult(
                signal=Signal.WATCH,
                notes=(
                    f"Would trigger BUY (RSI={rsi2_today:.1f} < "
                    f"{rsi_entry_threshold}, trend OK) — watchlist only"
                ),
                details=details,
            )
        return SignalResult(
            signal=Signal.WATCH,
            notes="No entry conditions met",
            details=details,
        )

    if trend_ok and rsi_ok:
        return SignalResult(
            signal=Signal.BUY,
            notes=(
                f"RSI(2)={rsi2_today:.1f} < {rsi_entry_threshold},"
                " trend OK — buy at next open"
            ),
            details=details,
        )

    return SignalResult(
        signal=Signal.NO_SIGNAL,
        notes="No entry conditions met",
        details=details,
    )


# ---------------------------------------------------------------------------
# Config & positions I/O
# ---------------------------------------------------------------------------


def load_config() -> dict[str, Any]:
    """Load production params from config/production_params.yaml."""
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_positions() -> dict[str, Any]:
    """Load positions from data/positions.json. Returns {} if file missing."""
    if not POSITIONS_PATH.exists():
        return {}
    with open(POSITIONS_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_positions(positions: dict[str, Any]) -> None:
    """Save positions to data/positions.json."""
    POSITIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(POSITIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(positions, f, indent=2, default=str)


# ---------------------------------------------------------------------------
# Data fetching & indicator computation
# ---------------------------------------------------------------------------


def fetch_data(symbol: str, loader: YahooLoader) -> tuple[pd.DataFrame, str]:
    """Fetch daily data for one ETF.

    Returns (dataframe, last_bar_date_str). Fetches ~600 calendar days
    of history to ensure SMA(200) warmup.
    """
    end = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=LOOKBACK_CALENDAR_DAYS)).strftime(
        "%Y-%m-%d"
    )
    df = loader.get_daily_candles(symbol, start, end)
    last_date = str(df.index[-1].date())
    return df, last_date


def compute_indicators(
    df: pd.DataFrame, params: dict[str, Any]
) -> dict[str, float]:
    """Compute indicators for one ETF, return latest values.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV data from YahooLoader.
    params : dict
        Production params (rsi_period, sma_trend_period, sma_exit_period).

    Returns
    -------
    dict with keys: close, rsi2, sma200, sma5
    """
    arrays = to_cache_arrays(df)

    cache_grid = {
        "sma_trend_period": [params["sma_trend_period"]],
        "sma_exit_period": [params["sma_exit_period"]],
        "rsi_period": [params["rsi_period"]],
    }
    cache = build_cache(arrays, cache_grid)

    i = cache.n_candles - 1
    return {
        "close": float(cache.closes[i]),
        "rsi2": float(cache.rsi_by_period[params["rsi_period"]][i]),
        "sma200": float(cache.sma_by_period[params["sma_trend_period"]][i]),
        "sma5": float(cache.sma_by_period[params["sma_exit_period"]][i]),
    }


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

_SIGNAL_MARKERS = {
    Signal.BUY: "***BUY***",
    Signal.SELL: "SELL",
    Signal.SAFETY_EXIT: "!SAFETY!",
    Signal.HOLD: "hold",
    Signal.NO_SIGNAL: "---",
    Signal.PENDING_VALID: "pending OK",
    Signal.PENDING_EXPIRED: "pending X",
    Signal.WATCH: "watch",
}


def print_dashboard(
    results: list[SignalResult],
    last_dates: dict[str, str],
    watchlist_symbols: set[str] | None = None,
) -> None:
    """Print formatted signal dashboard to console."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sep = "=" * 72
    wl = watchlist_symbols or set()

    main_results = [r for r in results if r.symbol not in wl]
    watch_results = [r for r in results if r.symbol in wl]

    print()
    print(sep)
    print(f"  RSI(2) Daily Scanner — {now}")
    print(sep)
    print()

    def _print_row(r: SignalResult) -> None:
        marker = f"[{_SIGNAL_MARKERS.get(r.signal, '?')}]"
        d = r.details
        data_date = last_dates.get(r.symbol, "?")
        rsi_str = f"{d.get('rsi2', 0):5.1f}" if d else "  N/A"
        close_str = f"{d.get('close', 0):8.2f}" if d else "     N/A"
        sma5_str = f"{d.get('sma5', 0):8.2f}" if d else "     N/A"
        print(
            f"  {r.symbol:5s} {marker:15s}  RSI(2)={rsi_str}"
            f"  Close={close_str}  SMA5={sma5_str}  [{data_date}]"
        )
        if r.notes:
            print(f"        {r.notes}")
        print()

    for r in main_results:
        _print_row(r)

    if watch_results:
        print(f"  -- Watchlist {'-' * 55}")
        for r in watch_results:
            _print_row(r)

    actions = [
        r
        for r in results
        if r.signal in (Signal.BUY, Signal.SELL, Signal.SAFETY_EXIT)
    ]
    if actions:
        print("-" * 72)
        print("  ACTION REQUIRED:")
        for r in actions:
            print(f"    {r.signal.value} {r.symbol} — {r.notes}")
        print("-" * 72)
    else:
        print("  No action required today.")
    print()


# ---------------------------------------------------------------------------
# Signal history CSV
# ---------------------------------------------------------------------------


def append_history(results: list[SignalResult], positions: dict[str, Any]) -> None:
    """Append signal results to data/signal_history.csv."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows: list[dict[str, Any]] = []
    for r in results:
        pos = positions.get(r.symbol)
        entry_price = ""
        if isinstance(pos, dict):
            entry_price = pos.get("entry_price", pos.get("close", ""))
        rows.append(
            {
                "timestamp": timestamp,
                "symbol": r.symbol,
                "signal": r.signal.value,
                "rsi2": r.details.get("rsi2", ""),
                "close": r.details.get("close", ""),
                "sma200": r.details.get("sma200", ""),
                "sma5": r.details.get("sma5", ""),
                "entry_price": entry_price,
                "notes": r.notes,
            }
        )

    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_header = not HISTORY_PATH.exists()
    df = pd.DataFrame(rows, columns=HISTORY_COLUMNS)
    df.to_csv(HISTORY_PATH, mode="a", header=write_header, index=False)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def _configure_logging() -> None:
    """Configure loguru: stderr for dashboard, file for detailed log."""
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{message}")
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger.add(
        str(LOG_PATH),
        level="DEBUG",
        rotation="1 MB",
        retention="30 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<7} | {message}",
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the daily signal scanner."""
    _configure_logging()
    logger.info("Starting RSI(2) daily scanner")

    config = load_config()
    universe: list[str] = config["universe"]
    watchlist_syms: list[str] = config.get("watchlist", [])
    all_symbols = universe + watchlist_syms
    watchlist_set = set(watchlist_syms)
    params: dict[str, Any] = config["params"]

    positions = load_positions()
    for sym in all_symbols:
        if sym not in positions:
            positions[sym] = None

    loader = YahooLoader()
    results: list[SignalResult] = []
    last_dates: dict[str, str] = {}

    for sym in all_symbols:
        is_watch = sym in watchlist_set
        logger.debug("Processing {} {}", sym, "(watchlist)" if is_watch else "")
        try:
            df, last_date = fetch_data(sym, loader)
            last_dates[sym] = last_date

            days_old = (datetime.now() - pd.Timestamp(last_date)).days
            if days_old > 3:
                logger.warning(
                    "{}: data is {} days old (last bar: {})",
                    sym, days_old, last_date,
                )

            indicators = compute_indicators(df, params)

            if any(math.isnan(v) for v in indicators.values()):
                logger.error("{}: NaN in indicators — skipping", sym)
                results.append(
                    SignalResult(
                        signal=Signal.NO_SIGNAL,
                        symbol=sym,
                        notes="ERROR: NaN indicators",
                        details=indicators,
                    )
                )
                continue

            result = evaluate_signal(
                rsi2_today=indicators["rsi2"],
                close_today=indicators["close"],
                sma200_today=indicators["sma200"],
                sma5_today=indicators["sma5"],
                position=positions.get(sym),
                rsi_entry_threshold=params["rsi_entry_threshold"],
                sma_trend_buffer=params["sma_trend_buffer"],
                watchlist=is_watch,
            )
            result.symbol = sym
            results.append(result)

            # Auto-write pending on BUY (never for watchlist)
            if result.signal == Signal.BUY:
                positions[sym] = {
                    "status": "pending",
                    "signal_date": last_date,
                    "rsi2": indicators["rsi2"],
                    "close": indicators["close"],
                    "sma200": indicators["sma200"],
                    "sma5": indicators["sma5"],
                }
                logger.info("{}: BUY signal — pending written to positions.json", sym)

        except Exception as e:
            logger.error("{}: fetch/compute failed — {}", sym, e)
            results.append(
                SignalResult(
                    signal=Signal.NO_SIGNAL,
                    symbol=sym,
                    notes=f"ERROR: {e}",
                )
            )

    save_positions(positions)
    print_dashboard(results, last_dates, watchlist_set)
    append_history(results, positions)

    # --- Telegram notification ---
    from engine.notifier import (  # noqa: E402
        format_signal_message,
        format_weekly_summary,
        send_telegram,
    )

    is_sunday = datetime.now().weekday() == 6
    if is_sunday:
        weekly_msg = format_weekly_summary(results, positions)
        if send_telegram(weekly_msg):
            logger.info("Telegram weekly summary sent")

    telegram_msg = format_signal_message(results, last_dates, watchlist_set)
    if telegram_msg is not None:
        if send_telegram(telegram_msg):
            logger.info("Telegram notification sent")
    else:
        logger.debug("No actionable signals — no Telegram message")

    logger.info("Scanner complete — {} signals evaluated", len(results))


if __name__ == "__main__":
    main()
