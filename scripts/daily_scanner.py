"""Multi-Strategy Daily Signal Scanner with Paper Trading.

Evaluates RSI(2), IBS, and TOM signals after US market close.
Paper trades are automatically tracked in SQLite DB (data/signal_radar.db).

Strategies:
    - RSI(2) Mean Reversion: oversold bounce on low RSI with trend filter
    - IBS Mean Reversion: close near daily low with trend filter
    - TOM (Turn of Month): calendar anomaly, last days of month

Usage:
    python scripts/daily_scanner.py
"""

from __future__ import annotations

import html
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
# Path setup
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from data.base_loader import to_cache_arrays  # noqa: E402
from data.db import SignalRadarDB  # noqa: E402
from data.yahoo_loader import YahooLoader  # noqa: E402
from engine.indicator_cache import build_cache  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONFIG_PATH = PROJECT_ROOT / "config" / "production_params.yaml"
LOG_PATH = PROJECT_ROOT / "logs" / "scanner.log"

LOOKBACK_CALENDAR_DAYS = 600  # ~400 trading days, enough for SMA(200) warmup

_STRATEGY_LABELS = {
    "rsi2": "RSI(2) Mean Reversion",
    "ibs": "IBS Mean Reversion",
    "tom": "Turn of Month",
}


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
    """Result of evaluating a signal for one ticker."""

    signal: Signal
    symbol: str = ""
    strategy: str = ""
    notes: str = ""
    details: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# RSI(2) signal logic (backward compatible with existing tests)
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
    """Evaluate RSI(2) signal for one ticker based on today's close.

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
        # Phase 3: SMA exit -- close > SMA5 (backtest line 142-146)
        if close_today > sma5_today:
            return SignalResult(
                signal=Signal.SELL,
                notes=(
                    f"Close ({close_today:.2f}) > SMA5 ({sma5_today:.2f})"
                    " -- sell at next open"
                ),
                details=details,
            )
        # Phase 5: Trend break -- close < SMA200 (backtest line 155-159)
        if close_today < sma200_today:
            return SignalResult(
                signal=Signal.SAFETY_EXIT,
                notes=(
                    f"Close ({close_today:.2f}) < SMA200 ({sma200_today:.2f})"
                    " -- safety exit at next open"
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
                    f"{rsi_entry_threshold}, trend OK) -- watchlist only"
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
                " trend OK -- buy at next open"
            ),
            details=details,
        )

    return SignalResult(
        signal=Signal.NO_SIGNAL,
        notes="No entry conditions met",
        details=details,
    )


# ---------------------------------------------------------------------------
# IBS signal logic
# ---------------------------------------------------------------------------


def evaluate_ibs_signal(
    ibs_today: float,
    close_today: float,
    high_today: float,
    high_yesterday: float,
    sma200_today: float,
    position: dict[str, Any] | None,
    *,
    ibs_entry_threshold: float = 0.2,
    ibs_exit_threshold: float = 0.8,
    watchlist: bool = False,
) -> SignalResult:
    """Evaluate IBS Mean Reversion signal for one ticker.

    Entry: IBS < threshold AND close > SMA(200).
    Exit: IBS > threshold OR close > high_yesterday OR close < SMA200 (safety).

    Parameters
    ----------
    ibs_today : float
        Internal Bar Strength = (Close - Low) / (High - Low).
    close_today : float
        Today's adjusted close price.
    high_today : float
        Today's high price.
    high_yesterday : float
        Yesterday's high price (for prev_high exit).
    sma200_today : float
        SMA(200) at today's close.
    position : dict | None
        Current position state. None = no position.
    ibs_entry_threshold : float
        IBS entry threshold (default 0.2).
    ibs_exit_threshold : float
        IBS exit threshold (default 0.8).
    watchlist : bool
        If True, no BUY signals emitted.
    """
    details: dict[str, Any] = {
        "ibs": round(ibs_today, 4),
        "close": round(close_today, 2),
        "high": round(high_today, 2),
        "high_yesterday": round(high_yesterday, 2),
        "sma200": round(sma200_today, 2),
    }

    # --- OPEN position: check exits ---
    if position is not None and position.get("status") == "open":
        # Exit 1: IBS > threshold (reversion complete)
        if ibs_today > ibs_exit_threshold:
            return SignalResult(
                signal=Signal.SELL,
                notes=(
                    f"IBS={ibs_today:.4f} > {ibs_exit_threshold}"
                    " -- sell at next open"
                ),
                details=details,
            )
        # Exit 2: Close > high_yesterday (breakout)
        if close_today > high_yesterday:
            return SignalResult(
                signal=Signal.SELL,
                notes=(
                    f"Close ({close_today:.2f}) > High yesterday"
                    f" ({high_yesterday:.2f}) -- sell at next open"
                ),
                details=details,
            )
        # Exit 3: Trend break (safety)
        if close_today < sma200_today:
            return SignalResult(
                signal=Signal.SAFETY_EXIT,
                notes=(
                    f"Close ({close_today:.2f}) < SMA200 ({sma200_today:.2f})"
                    " -- safety exit"
                ),
                details=details,
            )
        return SignalResult(
            signal=Signal.HOLD,
            notes="No exit condition met",
            details=details,
        )

    # --- NO position: check entry ---
    trend_ok = close_today > sma200_today
    ibs_ok = ibs_today < ibs_entry_threshold

    if watchlist:
        if trend_ok and ibs_ok:
            return SignalResult(
                signal=Signal.WATCH,
                notes=(
                    f"Would trigger BUY (IBS={ibs_today:.4f} < "
                    f"{ibs_entry_threshold}, trend OK) -- watchlist only"
                ),
                details=details,
            )
        return SignalResult(
            signal=Signal.WATCH,
            notes="No entry conditions met",
            details=details,
        )

    if trend_ok and ibs_ok:
        return SignalResult(
            signal=Signal.BUY,
            notes=(
                f"IBS={ibs_today:.4f} < {ibs_entry_threshold},"
                " trend OK -- buy at next open"
            ),
            details=details,
        )

    return SignalResult(
        signal=Signal.NO_SIGNAL,
        notes="No entry conditions met",
        details=details,
    )


# ---------------------------------------------------------------------------
# TOM signal logic
# ---------------------------------------------------------------------------


def evaluate_tom_signal(
    close_today: float,
    trading_days_left: int,
    trading_day_of_month: int,
    position: dict[str, Any] | None,
    *,
    entry_days_before_eom: int = 5,
    exit_day_of_new_month: int = 3,
    current_date: str = "",
    watchlist: bool = False,
) -> SignalResult:
    """Evaluate Turn of Month signal for one ticker.

    Entry: trading_days_left_in_month <= entry_days_before_eom.
    Exit: in new month AND trading_day_of_month >= exit_day_of_new_month.

    Parameters
    ----------
    close_today : float
        Today's adjusted close price.
    trading_days_left : int
        Trading days remaining in the current month (including today).
    trading_day_of_month : int
        Which trading day of the month today is (1-based).
    position : dict | None
        Current position state. Must include "entry_date" for exit logic.
    entry_days_before_eom : int
        Entry when <= this many trading days left (default 5).
    exit_day_of_new_month : int
        Exit on this trading day of the new month (default 3).
    current_date : str
        Today's date string "YYYY-MM-DD" for month comparison.
    watchlist : bool
        If True, no BUY signals emitted.
    """
    details: dict[str, Any] = {
        "close": round(close_today, 2),
        "trading_days_left": trading_days_left,
        "trading_day_of_month": trading_day_of_month,
    }

    # --- OPEN position: check exit ---
    if position is not None and position.get("status") == "open":
        entry_date = position.get("entry_date", "")
        in_new_month = False
        if entry_date and current_date:
            entry_month = entry_date[:7]  # "YYYY-MM"
            current_month = current_date[:7]
            in_new_month = current_month != entry_month

        if in_new_month and trading_day_of_month >= exit_day_of_new_month:
            return SignalResult(
                signal=Signal.SELL,
                notes=(
                    f"TOM exit: day {trading_day_of_month} >= "
                    f"{exit_day_of_new_month} of new month -- sell at next open"
                ),
                details=details,
            )
        return SignalResult(
            signal=Signal.HOLD,
            notes=f"In TOM trade, {trading_days_left} days left in month",
            details=details,
        )

    # --- NO position: check entry ---
    if trading_days_left <= entry_days_before_eom:
        if watchlist:
            return SignalResult(
                signal=Signal.WATCH,
                notes=(
                    f"Would trigger BUY ({trading_days_left} days left"
                    f" <= {entry_days_before_eom}) -- watchlist only"
                ),
                details=details,
            )
        return SignalResult(
            signal=Signal.BUY,
            notes=(
                f"TOM entry: {trading_days_left} days left in month"
                f" <= {entry_days_before_eom} -- buy at next open"
            ),
            details=details,
        )

    if watchlist:
        return SignalResult(
            signal=Signal.WATCH,
            notes=(
                f"{trading_days_left} days left in month"
                f" (window at <= {entry_days_before_eom})"
            ),
            details=details,
        )

    return SignalResult(
        signal=Signal.NO_SIGNAL,
        notes=(
            f"{trading_days_left} days left in month"
            f" (window at <= {entry_days_before_eom})"
        ),
        details=details,
    )


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def load_config() -> dict[str, Any]:
    """Load production params from config/production_params.yaml."""
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Data fetching & indicator computation
# ---------------------------------------------------------------------------


def fetch_data(symbol: str, loader: YahooLoader) -> tuple[pd.DataFrame, str]:
    """Fetch daily data for one symbol.

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


def compute_indicators(df: pd.DataFrame) -> dict[str, Any]:
    """Compute all indicators for the last bar (RSI2 + IBS + TOM).

    Returns dict with keys:
        close, open, high, low, high_yesterday,
        rsi2, sma200, sma5,
        ibs, trading_days_left_in_month, trading_day_of_month
    """
    arrays = to_cache_arrays(df)

    cache_grid = {
        "sma_trend_period": [200],
        "sma_exit_period": [5],
        "rsi_period": [2],
    }
    # Pass dates for calendar calculations (TOM)
    dates = df.index.values
    cache = build_cache(arrays, cache_grid, dates=dates)

    i = cache.n_candles - 1
    close = float(cache.closes[i])
    high = float(cache.highs[i])
    low = float(cache.lows[i])
    high_yesterday = float(cache.highs[i - 1]) if i > 0 else high

    # IBS from cache
    ibs_val = float(cache.ibs[i]) if cache.ibs is not None else 0.5
    if math.isnan(ibs_val):
        ibs_val = 0.5

    result: dict[str, Any] = {
        "close": close,
        "open": float(cache.opens[i]),
        "high": high,
        "low": low,
        "high_yesterday": high_yesterday,
        "rsi2": float(cache.rsi_by_period[2][i]),
        "sma200": float(cache.sma_by_period[200][i]),
        "sma5": float(cache.sma_by_period[5][i]),
        "ibs": ibs_val,
    }

    if cache.trading_days_left_in_month is not None:
        result["trading_days_left_in_month"] = int(
            cache.trading_days_left_in_month[i]
        )
    if cache.trading_day_of_month is not None:
        result["trading_day_of_month"] = int(cache.trading_day_of_month[i])

    return result


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


def _format_indicator_row(
    r: SignalResult, last_date: str, strat_name: str,
) -> str:
    """Format one signal result as a dashboard row."""
    marker = f"[{_SIGNAL_MARKERS.get(r.signal, '?')}]"
    d = r.details
    close_str = f"{d.get('close', 0):8.2f}" if d else "     N/A"

    if strat_name == "rsi2":
        rsi_str = f"{d.get('rsi2', 0):5.1f}" if d else "  N/A"
        sma_str = f"{d.get('sma200', 0):8.2f}" if d else "     N/A"
        line = (
            f"  {r.symbol:5s} {marker:15s}"
            f"  RSI(2)={rsi_str}  Close={close_str}  SMA200={sma_str}"
            f"  [{last_date}]"
        )
    elif strat_name == "ibs":
        ibs_str = f"{d.get('ibs', 0):.4f}" if d else " N/A"
        sma_str = f"{d.get('sma200', 0):8.2f}" if d else "     N/A"
        line = (
            f"  {r.symbol:5s} {marker:15s}"
            f"  IBS={ibs_str}  Close={close_str}  SMA200={sma_str}"
            f"  [{last_date}]"
        )
    elif strat_name == "tom":
        dl = d.get("trading_days_left", "?")
        dm = d.get("trading_day_of_month", "?")
        line = (
            f"  {r.symbol:5s} {marker:15s}"
            f"  Close={close_str}  DaysLeft={dl}  DayOfMonth={dm}"
            f"  [{last_date}]"
        )
    else:
        line = f"  {r.symbol:5s} {marker:15s}  Close={close_str}  [{last_date}]"

    return line


def print_dashboard(
    all_results: dict[str, list[SignalResult]],
    last_dates: dict[str, str],
    open_positions: list[dict],
    closed_trades: list[dict],
    paper_summary: dict,
    config: dict,
    indicators_by_symbol: dict[str, dict],
) -> None:
    """Print multi-strategy signal dashboard to console."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sep = "=" * 72
    capital = config.get("capital", 5000)
    total_pnl = paper_summary.get("total_pnl", 0)
    n_closed = paper_summary.get("n_trades", 0)
    n_open = paper_summary.get("n_open", 0)
    pnl_sign = "+" if total_pnl >= 0 else ""

    print()
    print(sep)
    print(f"  Signal Radar -- Multi-Strategy Scanner -- {now}")
    print(
        f"  Capital: ${capital:,.0f} | Paper P&L: {pnl_sign}${total_pnl:.2f}"
        f" ({n_closed} closed, {n_open} open)"
    )
    print(sep)

    strategies_config = config.get("strategies", {})

    for strat_name, results in all_results.items():
        strat_cfg = strategies_config.get(strat_name, {})
        watchlist_set = set(strat_cfg.get("watchlist", []))
        label = _STRATEGY_LABELS.get(strat_name, strat_name)

        print()
        print(f"  -- {label} {'-' * (55 - len(label))}")

        if strat_name == "tom":
            # Show TOM window status
            any_ind = next(
                (indicators_by_symbol.get(r.symbol)
                 for r in results if r.symbol in indicators_by_symbol),
                None,
            )
            if any_ind and "trading_days_left_in_month" in any_ind:
                dl = any_ind["trading_days_left_in_month"]
                threshold = strat_cfg.get("params", {}).get(
                    "entry_days_before_eom", 5
                )
                status = "OPEN" if dl <= threshold else "closed"
                print(
                    f"  ({dl} trading days left in month"
                    f" -- entry window {status})"
                )

        main_results = [r for r in results if r.symbol not in watchlist_set]
        watch_results = [r for r in results if r.symbol in watchlist_set]

        for r in main_results:
            last_date = last_dates.get(r.symbol, "?")
            line = _format_indicator_row(r, last_date, strat_name)
            print(line)
            # Show paper position info
            pos = _find_open_position(open_positions, strat_name, r.symbol)
            if pos:
                ind = indicators_by_symbol.get(r.symbol, {})
                current = ind.get("close", pos["entry_price"])
                unreal = (current - pos["entry_price"]) * pos["shares"]
                unreal_sign = "+" if unreal >= 0 else ""
                print(
                    f"        In position since {pos['entry_date']}"
                    f" ({pos['shares']:.0f} shares @ ${pos['entry_price']:.2f},"
                    f" unrealized {unreal_sign}${unreal:.2f})"
                )
            elif r.notes and r.signal not in (Signal.NO_SIGNAL, Signal.HOLD):
                print(f"        {r.notes}")

        if watch_results:
            print(f"  -- watch --")
            for r in watch_results:
                last_date = last_dates.get(r.symbol, "?")
                line = _format_indicator_row(r, last_date, strat_name)
                print(line)

    # --- Open Paper Positions ---
    if open_positions:
        print()
        print(f"  -- Open Paper Positions {'-' * 46}")
        print(
            f"  {'Strategy':10s} {'Symbol':7s} {'Entry Date':12s}"
            f" {'Entry':>8s} {'Shares':>7s} {'Current':>8s} {'Unreal P&L':>11s}"
        )
        for pos in open_positions:
            ind = indicators_by_symbol.get(pos["symbol"], {})
            current = ind.get("close", pos["entry_price"])
            unreal = (current - pos["entry_price"]) * pos["shares"]
            unreal_sign = "+" if unreal >= 0 else ""
            print(
                f"  {pos['strategy']:10s} {pos['symbol']:7s}"
                f" {pos['entry_date']:12s}"
                f" ${pos['entry_price']:>7.2f} {pos['shares']:>7.0f}"
                f" ${current:>7.2f} {unreal_sign}${unreal:>7.2f}"
            )

    # --- Recent Closed Trades ---
    if closed_trades:
        print()
        print(f"  -- Recent Closed Trades {'-' * 46}")
        print(
            f"  {'Strategy':10s} {'Symbol':7s}"
            f" {'Entry':>10s} {'Exit':>10s} {'Shares':>7s} {'P&L':>10s}"
        )
        for t in closed_trades[:10]:
            pnl = t.get("pnl_dollars", 0) or 0
            pnl_sign = "+" if pnl >= 0 else ""
            entry_short = t.get("entry_date", "")[-5:]  # MM-DD
            exit_short = t.get("exit_date", "")[-5:]
            print(
                f"  {t['strategy']:10s} {t['symbol']:7s}"
                f" {entry_short:>10s} {exit_short:>10s}"
                f" {t['shares']:>7.0f} {pnl_sign}${pnl:>7.2f}"
            )

    # --- Paper Performance ---
    print()
    print(f"  -- Paper Performance {'-' * 49}")
    wr = paper_summary.get("win_rate", 0)
    print(
        f"  Total closed: {n_closed} trades"
        f" | Win rate: {wr:.0f}% | Net P&L: {pnl_sign}${total_pnl:.2f}"
    )

    by_strat = paper_summary.get("by_strategy", {})
    if by_strat:
        parts = []
        for s, info in by_strat.items():
            w = info.get("wins", 0)
            l = info["trades"] - w
            p = info.get("pnl", 0)
            ps = "+" if p >= 0 else ""
            parts.append(f"{s.upper()} {ps}${p:.2f} ({w}W/{l}L)")
        print(f"  By strategy: {' | '.join(parts)}")

    # --- Action required ---
    actions = []
    for strat_name, results in all_results.items():
        for r in results:
            if r.signal in (Signal.BUY, Signal.SELL, Signal.SAFETY_EXIT):
                actions.append(r)

    if actions:
        print()
        print("-" * 72)
        print("  ACTION REQUIRED:")
        for r in actions:
            print(f"    [{r.strategy.upper()}] {r.signal.value} {r.symbol} -- {r.notes}")
        print("-" * 72)

    print(sep)
    print()


def _find_open_position(
    positions: list[dict], strategy: str, symbol: str,
) -> dict | None:
    """Find an open paper position for a strategy+symbol pair."""
    for p in positions:
        if p["strategy"] == strategy and p["symbol"] == symbol:
            return p
    return None


# ---------------------------------------------------------------------------
# Telegram notification
# ---------------------------------------------------------------------------

_SIGNAL_EMOJI = {
    "BUY": "\U0001f7e2",       # green circle
    "SELL": "\U0001f534",       # red circle
    "SAFETY_EXIT": "\u26a0\ufe0f",  # warning
}


def _format_telegram_message(
    all_results: dict[str, list[SignalResult]],
    paper_summary: dict,
) -> str | None:
    """Format actionable signals as a Telegram HTML message.

    Returns None if no actionable signals.
    """
    actionable: list[SignalResult] = []
    watch_triggers: list[SignalResult] = []

    for strat_name, results in all_results.items():
        for r in results:
            if r.signal in (Signal.BUY, Signal.SELL, Signal.SAFETY_EXIT):
                actionable.append(r)
            elif r.signal == Signal.WATCH and "Would trigger BUY" in r.notes:
                watch_triggers.append(r)

    if not actionable and not watch_triggers:
        return None

    today = datetime.now().strftime("%Y-%m-%d")
    total_pnl = paper_summary.get("total_pnl", 0)
    n_open = paper_summary.get("n_open", 0)
    pnl_sign = "+" if total_pnl >= 0 else ""

    lines: list[str] = [
        f"\U0001f4ca <b>Signal Radar</b> -- {today}",
        f"Paper P&amp;L: {pnl_sign}${total_pnl:.2f} | Open: {n_open}",
        "",
    ]

    for r in actionable:
        sig = r.signal.value
        emoji = _SIGNAL_EMOJI.get(sig, "\u2753")
        label = "SAFETY EXIT" if sig == "SAFETY_EXIT" else sig
        strat_label = r.strategy.upper()

        lines.append(f"{emoji} <b>{label} {r.symbol}</b> ({strat_label})")
        lines.append(f"  {html.escape(r.notes)}")
        lines.append("")

    for r in watch_triggers:
        strat_label = r.strategy.upper()
        lines.append(
            f"\U0001f440 <b>WATCH {r.symbol}</b> ({strat_label})"
        )
        lines.append(f"  {html.escape(r.notes)}")
        lines.append("")

    return "\n".join(lines).strip()


def _format_weekly_summary(
    all_results: dict[str, list[SignalResult]],
    paper_summary: dict,
    open_positions: list[dict],
) -> str:
    """Format weekly summary (sent every Sunday)."""
    today = datetime.now().strftime("%Y-%m-%d")
    total_pnl = paper_summary.get("total_pnl", 0)
    n_trades = paper_summary.get("n_trades", 0)
    wr = paper_summary.get("win_rate", 0)
    n_open = paper_summary.get("n_open", 0)
    pnl_sign = "+" if total_pnl >= 0 else ""

    lines: list[str] = [
        f"\U0001f4ca <b>Signal Radar Weekly</b> -- {today}",
        "",
        f"<b>Paper Trading:</b>",
        f"  Closed: {n_trades} trades | WR: {wr:.0f}%"
        f" | P&amp;L: {pnl_sign}${total_pnl:.2f}",
        f"  Open positions: {n_open}",
    ]

    if open_positions:
        lines.append("")
        lines.append("<b>Positions:</b>")
        for pos in open_positions:
            lines.append(
                f"  {pos['strategy'].upper()} {pos['symbol']}"
                f" @ ${pos['entry_price']:.2f} ({pos['entry_date']})"
            )

    # Signal counts per strategy
    lines.append("")
    for strat_name, results in all_results.items():
        buy_count = sum(1 for r in results if r.signal == Signal.BUY)
        sell_count = sum(
            1 for r in results
            if r.signal in (Signal.SELL, Signal.SAFETY_EXIT)
        )
        if buy_count or sell_count:
            lines.append(
                f"  {strat_name.upper()}: {buy_count} BUY, {sell_count} SELL"
            )

    lines.append("")
    lines.append("Scanner running normally. \u2705")

    return "\n".join(lines)


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
    """Run the multi-strategy daily signal scanner with paper trading."""
    _configure_logging()
    logger.info("Starting multi-strategy scanner")

    config = load_config()
    capital = config.get("capital", 5000)
    whole_shares = config.get("whole_shares", True)
    strategies_config = config.get("strategies", {})

    db = SignalRadarDB()
    loader = YahooLoader()

    # --- Collect all unique symbols across strategies ---
    all_symbols: set[str] = set()
    for strat_cfg in strategies_config.values():
        if not strat_cfg.get("enabled", True):
            continue
        all_symbols.update(strat_cfg.get("universe", []))
        all_symbols.update(strat_cfg.get("watchlist", []))

    # --- Fetch data & compute indicators for each symbol (once) ---
    indicators_by_symbol: dict[str, dict] = {}
    last_dates: dict[str, str] = {}

    for sym in sorted(all_symbols):
        logger.debug("Fetching {}", sym)
        try:
            df, last_date = fetch_data(sym, loader)
            last_dates[sym] = last_date

            days_old = (datetime.now() - pd.Timestamp(last_date)).days
            if days_old > 3:
                logger.warning(
                    "{}: data is {} days old (last bar: {})",
                    sym, days_old, last_date,
                )

            ind = compute_indicators(df)

            # Check for NaN in float values
            has_nan = any(
                math.isnan(v) for v in ind.values()
                if isinstance(v, float)
            )
            if has_nan:
                logger.error("{}: NaN in indicators -- skipping", sym)
                continue

            indicators_by_symbol[sym] = ind

        except Exception as e:
            logger.error("{}: fetch/compute failed -- {}", sym, e)

    # --- Evaluate signals per strategy ---
    all_results: dict[str, list[SignalResult]] = {}
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today_date = datetime.now().strftime("%Y-%m-%d")

    for strat_name, strat_cfg in strategies_config.items():
        if not strat_cfg.get("enabled", True):
            continue

        universe = strat_cfg.get("universe", [])
        watchlist = strat_cfg.get("watchlist", [])
        params = strat_cfg.get("params", {})
        strat_symbols = universe + watchlist
        watchlist_set = set(watchlist)
        position_fraction = params.get("position_fraction", 1.0)

        results: list[SignalResult] = []

        for sym in strat_symbols:
            if sym not in indicators_by_symbol:
                results.append(SignalResult(
                    signal=Signal.NO_SIGNAL, symbol=sym, strategy=strat_name,
                    notes="ERROR: no data",
                ))
                continue

            ind = indicators_by_symbol[sym]
            is_watch = sym in watchlist_set

            # Check for open paper position
            open_pos_list = db.get_open_positions(strategy=strat_name)
            open_pos = _find_open_position(open_pos_list, strat_name, sym)
            pos_dict = (
                {"status": "open", **open_pos} if open_pos else None
            )

            # --- Evaluate signal ---
            if strat_name == "rsi2":
                result = evaluate_signal(
                    rsi2_today=ind["rsi2"],
                    close_today=ind["close"],
                    sma200_today=ind["sma200"],
                    sma5_today=ind["sma5"],
                    position=pos_dict,
                    rsi_entry_threshold=params.get("rsi_entry_threshold", 10.0),
                    sma_trend_buffer=params.get("sma_trend_buffer", 1.01),
                    watchlist=is_watch,
                )
            elif strat_name == "ibs":
                result = evaluate_ibs_signal(
                    ibs_today=ind["ibs"],
                    close_today=ind["close"],
                    high_today=ind["high"],
                    high_yesterday=ind["high_yesterday"],
                    sma200_today=ind["sma200"],
                    position=pos_dict,
                    ibs_entry_threshold=params.get("ibs_entry_threshold", 0.2),
                    ibs_exit_threshold=params.get("ibs_exit_threshold", 0.8),
                    watchlist=is_watch,
                )
            elif strat_name == "tom":
                result = evaluate_tom_signal(
                    close_today=ind["close"],
                    trading_days_left=ind.get("trading_days_left_in_month", 99),
                    trading_day_of_month=ind.get("trading_day_of_month", 1),
                    position=pos_dict,
                    entry_days_before_eom=params.get("entry_days_before_eom", 5),
                    exit_day_of_new_month=params.get("exit_day_of_new_month", 3),
                    current_date=last_dates.get(sym, today_date),
                    watchlist=is_watch,
                )
            else:
                logger.warning("Unknown strategy: {}", strat_name)
                continue

            result.symbol = sym
            result.strategy = strat_name
            results.append(result)

            # --- Paper trading ---
            if result.signal == Signal.BUY and not is_watch:
                trade_capital = capital * position_fraction
                if whole_shares:
                    shares = math.floor(trade_capital / ind["close"])
                else:
                    shares = trade_capital / ind["close"]

                if shares > 0:
                    opened = db.open_paper_position(
                        strat_name, sym,
                        last_dates.get(sym, today_date),
                        ind["close"], shares,
                    )
                    if opened:
                        logger.info(
                            "{} {}: BUY -- paper {} shares @ ${:.2f}",
                            strat_name, sym, shares, ind["close"],
                        )
                    else:
                        logger.debug(
                            "{} {}: BUY signal but already in position",
                            strat_name, sym,
                        )
                else:
                    logger.warning(
                        "{} {}: BUY signal but 0 shares at ${:.2f}"
                        " (capital ${:.0f})",
                        strat_name, sym, ind["close"], trade_capital,
                    )

            elif result.signal in (Signal.SELL, Signal.SAFETY_EXIT):
                trade = db.close_paper_position(
                    strat_name, sym,
                    last_dates.get(sym, today_date),
                    ind["close"],
                )
                if trade:
                    logger.info(
                        "{} {}: {} -- paper closed, PnL ${:.2f}",
                        strat_name, sym, result.signal.value,
                        trade["pnl_dollars"],
                    )

            # --- Log signal ---
            indicator_value = None
            if strat_name == "rsi2":
                indicator_value = ind.get("rsi2")
            elif strat_name == "ibs":
                indicator_value = ind.get("ibs")
            elif strat_name == "tom":
                tdl = ind.get("trading_days_left_in_month")
                indicator_value = float(tdl) if tdl is not None else None

            db.log_signal(
                timestamp, strat_name, sym, result.signal.value,
                ind["close"], indicator_value, result.notes,
            )

        all_results[strat_name] = results

    # --- Dashboard ---
    open_positions = db.get_open_positions()
    closed_trades = db.get_closed_trades(limit=10)
    paper_summary = db.get_paper_summary()

    print_dashboard(
        all_results, last_dates, open_positions, closed_trades,
        paper_summary, config, indicators_by_symbol,
    )

    # --- Telegram ---
    from engine.notifier import send_telegram  # noqa: E402

    is_sunday = datetime.now().weekday() == 6

    if is_sunday:
        weekly_msg = _format_weekly_summary(
            all_results, paper_summary, open_positions,
        )
        if send_telegram(weekly_msg):
            logger.info("Telegram weekly summary sent")

    telegram_msg = _format_telegram_message(all_results, paper_summary)
    if telegram_msg is not None:
        if send_telegram(telegram_msg):
            logger.info("Telegram notification sent")
    else:
        logger.debug("No actionable signals -- no Telegram message")

    logger.info(
        "Scanner complete -- {} strategies, {} symbols evaluated",
        len(all_results),
        sum(len(v) for v in all_results.values()),
    )


if __name__ == "__main__":
    main()
