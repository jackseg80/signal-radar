"""Tests for the RSI(2) daily signal scanner signal logic.

Tests evaluate_signal() as a pure function with synthetic inputs.
No Yahoo Finance calls, no file I/O.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.daily_scanner import (
    Signal,
    _is_data_stale,
    evaluate_signal,
    evaluate_ibs_signal,
    evaluate_tom_signal,
)


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


# ---------------------------------------------------------------------------
# IBS signals
# ---------------------------------------------------------------------------


class TestIBSEntrySignals:
    """Tests for IBS BUY / NO_SIGNAL when no position is held."""

    def test_ibs_buy_signal(self) -> None:
        """IBS < 0.2, close > SMA200, no position -> BUY."""
        result = evaluate_ibs_signal(
            ibs_today=0.12,
            close_today=131.40,
            high_today=135.00,
            high_yesterday=133.00,
            sma200_today=120.00,
            position=None,
        )
        assert result.signal == Signal.BUY

    def test_ibs_no_buy_above_threshold(self) -> None:
        """IBS = 0.45 -> NO_SIGNAL even with trend OK."""
        result = evaluate_ibs_signal(
            ibs_today=0.45,
            close_today=131.40,
            high_today=135.00,
            high_yesterday=133.00,
            sma200_today=120.00,
            position=None,
        )
        assert result.signal == Signal.NO_SIGNAL

    def test_ibs_no_buy_below_trend(self) -> None:
        """IBS = 0.12 but close < SMA200 -> NO_SIGNAL."""
        result = evaluate_ibs_signal(
            ibs_today=0.12,
            close_today=115.00,
            high_today=118.00,
            high_yesterday=119.00,
            sma200_today=120.00,
            position=None,
        )
        assert result.signal == Signal.NO_SIGNAL

    def test_ibs_buy_at_threshold(self) -> None:
        """IBS exactly at 0.2 -> NO_SIGNAL (must be strictly less)."""
        result = evaluate_ibs_signal(
            ibs_today=0.2,
            close_today=131.40,
            high_today=135.00,
            high_yesterday=133.00,
            sma200_today=120.00,
            position=None,
        )
        assert result.signal == Signal.NO_SIGNAL


class TestIBSExitSignals:
    """Tests for IBS SELL / SAFETY_EXIT / HOLD when position is open."""

    def test_ibs_sell_ibs_high(self) -> None:
        """Open position, IBS > 0.8 -> SELL."""
        result = evaluate_ibs_signal(
            ibs_today=0.85,
            close_today=140.00,
            high_today=141.00,
            high_yesterday=139.00,
            sma200_today=120.00,
            position={"status": "open"},
        )
        assert result.signal == Signal.SELL

    def test_ibs_sell_above_high_yesterday(self) -> None:
        """Open position, close > high_yesterday -> SELL."""
        result = evaluate_ibs_signal(
            ibs_today=0.55,
            close_today=134.00,
            high_today=135.00,
            high_yesterday=133.00,
            sma200_today=120.00,
            position={"status": "open"},
        )
        assert result.signal == Signal.SELL

    def test_ibs_safety_exit(self) -> None:
        """Open position, close < SMA200 -> SAFETY_EXIT."""
        result = evaluate_ibs_signal(
            ibs_today=0.55,
            close_today=118.00,
            high_today=119.00,
            high_yesterday=121.00,
            sma200_today=120.00,
            position={"status": "open"},
        )
        assert result.signal == Signal.SAFETY_EXIT

    def test_ibs_hold(self) -> None:
        """Open position, no exit condition -> HOLD."""
        result = evaluate_ibs_signal(
            ibs_today=0.55,
            close_today=130.00,
            high_today=131.00,
            high_yesterday=133.00,
            sma200_today=120.00,
            position={"status": "open"},
        )
        assert result.signal == Signal.HOLD

    def test_ibs_sell_priority(self) -> None:
        """IBS > threshold takes priority over high_yesterday check."""
        result = evaluate_ibs_signal(
            ibs_today=0.90,
            close_today=134.00,
            high_today=135.00,
            high_yesterday=133.00,
            sma200_today=120.00,
            position={"status": "open"},
        )
        assert result.signal == Signal.SELL
        assert "IBS=" in result.notes


class TestIBSWatchlist:
    """Tests for IBS watchlist signals."""

    def test_ibs_watch_would_buy(self) -> None:
        """Watchlist ticker, IBS < 0.2, trend OK -> WATCH with buy note."""
        result = evaluate_ibs_signal(
            ibs_today=0.12,
            close_today=131.40,
            high_today=135.00,
            high_yesterday=133.00,
            sma200_today=120.00,
            position=None,
            watchlist=True,
        )
        assert result.signal == Signal.WATCH
        assert "Would trigger BUY" in result.notes


# ---------------------------------------------------------------------------
# TOM signals
# ---------------------------------------------------------------------------


class TestTOMEntrySignals:
    """Tests for TOM BUY / NO_SIGNAL when no position is held."""

    def test_tom_buy_in_window(self) -> None:
        """5 trading days left (<= 5) -> BUY."""
        result = evaluate_tom_signal(
            close_today=612.30,
            trading_days_left=5,
            trading_day_of_month=17,
            position=None,
        )
        assert result.signal == Signal.BUY

    def test_tom_buy_last_day(self) -> None:
        """1 trading day left -> BUY."""
        result = evaluate_tom_signal(
            close_today=612.30,
            trading_days_left=1,
            trading_day_of_month=22,
            position=None,
        )
        assert result.signal == Signal.BUY

    def test_tom_no_buy_outside_window(self) -> None:
        """10 trading days left (> 5) -> NO_SIGNAL."""
        result = evaluate_tom_signal(
            close_today=612.30,
            trading_days_left=10,
            trading_day_of_month=12,
            position=None,
        )
        assert result.signal == Signal.NO_SIGNAL

    def test_tom_no_buy_at_boundary(self) -> None:
        """6 trading days left (> 5) -> NO_SIGNAL."""
        result = evaluate_tom_signal(
            close_today=612.30,
            trading_days_left=6,
            trading_day_of_month=16,
            position=None,
        )
        assert result.signal == Signal.NO_SIGNAL


class TestTOMExitSignals:
    """Tests for TOM SELL / HOLD when position is open."""

    def test_tom_sell_new_month(self) -> None:
        """In new month, day 3 >= exit_day 3 -> SELL."""
        result = evaluate_tom_signal(
            close_today=620.00,
            trading_days_left=19,
            trading_day_of_month=3,
            position={"status": "open", "entry_date": "2026-02-25"},
            current_date="2026-03-05",
        )
        assert result.signal == Signal.SELL

    def test_tom_hold_same_month(self) -> None:
        """Still in same month -> HOLD."""
        result = evaluate_tom_signal(
            close_today=615.00,
            trading_days_left=2,
            trading_day_of_month=20,
            position={"status": "open", "entry_date": "2026-03-25"},
            current_date="2026-03-27",
        )
        assert result.signal == Signal.HOLD

    def test_tom_hold_new_month_early(self) -> None:
        """New month but day 1 < exit_day 3 -> HOLD."""
        result = evaluate_tom_signal(
            close_today=618.00,
            trading_days_left=21,
            trading_day_of_month=1,
            position={"status": "open", "entry_date": "2026-02-25"},
            current_date="2026-03-01",
        )
        assert result.signal == Signal.HOLD

    def test_tom_sell_day_exceeds_exit(self) -> None:
        """New month, day 4 > exit_day 3 -> SELL."""
        result = evaluate_tom_signal(
            close_today=625.00,
            trading_days_left=18,
            trading_day_of_month=4,
            position={"status": "open", "entry_date": "2026-02-25"},
            current_date="2026-03-06",
        )
        assert result.signal == Signal.SELL


class TestTOMWatchlist:
    """Tests for TOM watchlist signals."""

    def test_tom_watch_would_buy(self) -> None:
        """Watchlist ticker in TOM window -> WATCH with buy note."""
        result = evaluate_tom_signal(
            close_today=612.30,
            trading_days_left=3,
            trading_day_of_month=19,
            position=None,
            watchlist=True,
        )
        assert result.signal == Signal.WATCH
        assert "Would trigger BUY" in result.notes

    def test_tom_watch_outside_window(self) -> None:
        """Watchlist ticker outside window -> WATCH."""
        result = evaluate_tom_signal(
            close_today=612.30,
            trading_days_left=10,
            trading_day_of_month=12,
            position=None,
            watchlist=True,
        )
        assert result.signal == Signal.WATCH


# ---------------------------------------------------------------------------
# Signal.SKIP enum
# ---------------------------------------------------------------------------


class TestSkipSignal:
    """Tests for Signal.SKIP enum value."""

    def test_skip_exists(self) -> None:
        """Signal.SKIP should exist as a valid enum value."""
        assert Signal.SKIP == "SKIP"
        assert Signal.SKIP.value == "SKIP"

    def test_skip_distinct_from_buy(self) -> None:
        """SKIP is not BUY."""
        assert Signal.SKIP != Signal.BUY


# ---------------------------------------------------------------------------
# Stale data check
# ---------------------------------------------------------------------------


class TestStaleDataCheck:
    """Tests for _is_data_stale()."""

    def test_fresh_data(self) -> None:
        """Data from today -> not stale."""
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        assert _is_data_stale(today) is False

    def test_stale_data(self) -> None:
        """Data from 5 days ago -> stale."""
        from datetime import datetime, timedelta
        old_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
        assert _is_data_stale(old_date) is True

    def test_borderline_data(self) -> None:
        """Data from 2 days ago -> not stale (exactly at threshold)."""
        from datetime import datetime, timedelta
        border_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        assert _is_data_stale(border_date) is False

    def test_three_days_old(self) -> None:
        """Data from 3 days ago -> stale (> 2)."""
        from datetime import datetime, timedelta
        old_date = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
        assert _is_data_stale(old_date) is True
