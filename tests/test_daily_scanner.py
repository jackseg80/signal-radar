"""Tests for the RSI(2) daily signal scanner signal logic.

Tests evaluate_signal() as a pure function with synthetic inputs.
No Yahoo Finance calls, no file I/O.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.daily_scanner import Signal, evaluate_signal


# ---------------------------------------------------------------------------
# Entry signals (no position)
# ---------------------------------------------------------------------------


class TestEntrySignals:
    """Tests for BUY / NO_SIGNAL when no position is held."""

    def test_buy_signal(self) -> None:
        """RSI < 10, close > SMA200*1.01, no position -> BUY."""
        result = evaluate_signal(
            rsi2_today=4.5,
            close_today=590.0,
            sma200_today=570.0,  # 570 * 1.01 = 575.7 < 590
            sma5_today=588.0,
            position=None,
        )
        assert result.signal == Signal.BUY

    def test_no_buy_rsi_above_threshold(self) -> None:
        """RSI = 15 -> NO_SIGNAL even with trend OK."""
        result = evaluate_signal(
            rsi2_today=15.0,
            close_today=590.0,
            sma200_today=570.0,
            sma5_today=588.0,
            position=None,
        )
        assert result.signal == Signal.NO_SIGNAL

    def test_no_buy_below_trend(self) -> None:
        """RSI = 5 but close < SMA200*1.01 -> NO_SIGNAL."""
        result = evaluate_signal(
            rsi2_today=5.0,
            close_today=570.0,  # 575 * 1.01 = 580.75 > 570
            sma200_today=575.0,
            sma5_today=572.0,
            position=None,
        )
        assert result.signal == Signal.NO_SIGNAL


# ---------------------------------------------------------------------------
# Exit signals (open position)
# ---------------------------------------------------------------------------


class TestExitSignals:
    """Tests for SELL / SAFETY_EXIT / HOLD when position is open."""

    def test_sell_sma_exit(self) -> None:
        """Open position, close > SMA5 -> SELL."""
        result = evaluate_signal(
            rsi2_today=55.0,
            close_today=595.0,
            sma200_today=570.0,
            sma5_today=590.0,  # close 595 > sma5 590
            position={"status": "open", "entry_price": 580.0},
        )
        assert result.signal == Signal.SELL

    def test_safety_exit(self) -> None:
        """Open position, close < SMA200 (and close < SMA5) -> SAFETY_EXIT."""
        result = evaluate_signal(
            rsi2_today=30.0,
            close_today=565.0,  # below SMA200=570 and below SMA5=580
            sma200_today=570.0,
            sma5_today=580.0,
            position={"status": "open", "entry_price": 580.0},
        )
        assert result.signal == Signal.SAFETY_EXIT

    def test_hold(self) -> None:
        """Open position, close < SMA5 and close > SMA200 -> HOLD."""
        result = evaluate_signal(
            rsi2_today=30.0,
            close_today=575.0,  # > SMA200=570, < SMA5=580
            sma200_today=570.0,
            sma5_today=580.0,
            position={"status": "open", "entry_price": 580.0},
        )
        assert result.signal == Signal.HOLD

    def test_sell_priority_over_safety(self) -> None:
        """close > SMA5 AND close < SMA200 -> SELL wins (not SAFETY_EXIT)."""
        result = evaluate_signal(
            rsi2_today=55.0,
            close_today=575.0,
            sma200_today=580.0,  # close < SMA200 -> safety candidate
            sma5_today=570.0,  # close > SMA5 -> sell candidate
            position={"status": "open", "entry_price": 590.0},
        )
        assert result.signal == Signal.SELL


# ---------------------------------------------------------------------------
# Pending position
# ---------------------------------------------------------------------------


class TestPendingSignals:
    """Tests for PENDING_VALID / PENDING_EXPIRED states."""

    def test_pending_still_valid(self) -> None:
        """Pending position, RSI still < 10 and trend OK -> PENDING_VALID."""
        result = evaluate_signal(
            rsi2_today=7.0,
            close_today=590.0,
            sma200_today=570.0,
            sma5_today=588.0,
            position={"status": "pending", "signal_date": "2026-02-28"},
        )
        assert result.signal == Signal.PENDING_VALID

    def test_pending_expired(self) -> None:
        """Pending position, RSI > 10 -> PENDING_EXPIRED."""
        result = evaluate_signal(
            rsi2_today=25.0,
            close_today=590.0,
            sma200_today=570.0,
            sma5_today=588.0,
            position={"status": "pending", "signal_date": "2026-02-28"},
        )
        assert result.signal == Signal.PENDING_EXPIRED

    def test_no_duplicate_buy(self) -> None:
        """Pending position, RSI < 10 -> PENDING_VALID, NOT a new BUY."""
        result = evaluate_signal(
            rsi2_today=4.5,
            close_today=590.0,
            sma200_today=570.0,
            sma5_today=588.0,
            position={"status": "pending", "signal_date": "2026-02-28"},
        )
        assert result.signal == Signal.PENDING_VALID
        assert result.signal != Signal.BUY


# ---------------------------------------------------------------------------
# Watchlist signals
# ---------------------------------------------------------------------------


class TestWatchlistSignals:
    """Tests for WATCH signal on watchlist tickers."""

    def test_watch_no_position(self) -> None:
        """Watchlist ticker, RSI < 10, trend OK, no position -> WATCH (not BUY)."""
        result = evaluate_signal(
            rsi2_today=4.5,
            close_today=590.0,
            sma200_today=570.0,
            sma5_today=588.0,
            position=None,
            watchlist=True,
        )
        assert result.signal == Signal.WATCH
        assert result.signal != Signal.BUY
        assert "Would trigger BUY" in result.notes

    def test_watch_with_open_position(self) -> None:
        """Watchlist ticker with open position, close > SMA5 -> SELL (normal)."""
        result = evaluate_signal(
            rsi2_today=55.0,
            close_today=595.0,
            sma200_today=570.0,
            sma5_today=590.0,
            position={"status": "open", "entry_price": 580.0},
            watchlist=True,
        )
        assert result.signal == Signal.SELL
