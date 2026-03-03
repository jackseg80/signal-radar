"""Tests for the Telegram notifier module.

Tests format_signal_message() as a pure function.
Tests send_telegram() with mocked urllib.
"""

from __future__ import annotations

import urllib.error
from unittest.mock import MagicMock, patch

from engine.notifier import (
    format_daily_summary,
    format_signal_message,
    format_weekly_summary,
    send_telegram,
)
from scripts.daily_scanner import Signal, SignalResult


# ---------------------------------------------------------------------------
# format_signal_message tests
# ---------------------------------------------------------------------------


class TestFormatSignalMessage:
    """Tests for message formatting."""

    def test_buy_signal_produces_message(self) -> None:
        results = [
            SignalResult(
                signal=Signal.BUY,
                symbol="META",
                notes="RSI(2)=4.5 < 10, trend OK — buy at next open",
                details={"rsi2": 4.5, "close": 590.0, "sma200": 570.0, "sma5": 588.0},
            ),
        ]
        msg = format_signal_message(results, {"META": "2026-03-01"})
        assert msg is not None
        assert "BUY META" in msg
        assert "4.5" in msg

    def test_no_action_returns_none(self) -> None:
        results = [
            SignalResult(
                signal=Signal.NO_SIGNAL,
                symbol="META",
                notes="No entry conditions met",
                details={"rsi2": 55.0, "close": 590.0, "sma200": 570.0, "sma5": 588.0},
            ),
        ]
        msg = format_signal_message(results, {"META": "2026-03-01"})
        assert msg is None

    def test_sell_signal_produces_message(self) -> None:
        results = [
            SignalResult(
                signal=Signal.SELL,
                symbol="MSFT",
                notes="Close > SMA5 — sell at next open",
                details={"rsi2": 55.0, "close": 395.0, "sma200": 380.0, "sma5": 390.0},
            ),
        ]
        msg = format_signal_message(results, {"MSFT": "2026-03-01"})
        assert msg is not None
        assert "SELL MSFT" in msg

    def test_safety_exit_produces_message(self) -> None:
        results = [
            SignalResult(
                signal=Signal.SAFETY_EXIT,
                symbol="GOOGL",
                notes="Close < SMA200 — safety exit at next open",
                details={"rsi2": 30.0, "close": 240.0, "sma200": 250.0, "sma5": 245.0},
            ),
        ]
        msg = format_signal_message(results, {"GOOGL": "2026-03-01"})
        assert msg is not None
        assert "SAFETY EXIT GOOGL" in msg

    def test_watchlist_trigger_included(self) -> None:
        results = [
            SignalResult(
                signal=Signal.WATCH,
                symbol="NVDA",
                notes="Would trigger BUY (RSI=7.4 < 10.0, trend OK) — watchlist only",
                details={"rsi2": 7.4, "close": 177.0, "sma200": 175.0, "sma5": 188.0},
            ),
        ]
        msg = format_signal_message(
            results, {"NVDA": "2026-03-01"}, watchlist_symbols={"NVDA"}
        )
        assert msg is not None
        assert "WATCH NVDA" in msg
        assert "Would trigger BUY" in msg

    def test_watchlist_no_trigger_returns_none(self) -> None:
        results = [
            SignalResult(
                signal=Signal.WATCH,
                symbol="NVDA",
                notes="No entry conditions met",
                details={"rsi2": 55.0, "close": 177.0, "sma200": 175.0, "sma5": 188.0},
            ),
        ]
        msg = format_signal_message(
            results, {"NVDA": "2026-03-01"}, watchlist_symbols={"NVDA"}
        )
        assert msg is None

    def test_hold_only_returns_none(self) -> None:
        results = [
            SignalResult(
                signal=Signal.HOLD,
                symbol="META",
                notes="No exit condition met",
                details={"rsi2": 25.0, "close": 590.0, "sma200": 570.0, "sma5": 595.0},
            ),
        ]
        msg = format_signal_message(results, {"META": "2026-03-01"})
        assert msg is None

    def test_mixed_signals_includes_all_actionable(self) -> None:
        results = [
            SignalResult(
                signal=Signal.BUY, symbol="META",
                notes="buy", details={"rsi2": 5.0, "close": 590.0},
            ),
            SignalResult(
                signal=Signal.NO_SIGNAL, symbol="MSFT",
                notes="nothing", details={"rsi2": 50.0, "close": 390.0},
            ),
            SignalResult(
                signal=Signal.SELL, symbol="GOOGL",
                notes="sell", details={"rsi2": 60.0, "close": 175.0},
            ),
        ]
        msg = format_signal_message(results, {})
        assert msg is not None
        assert "BUY META" in msg
        assert "SELL GOOGL" in msg
        assert "MSFT" not in msg


# ---------------------------------------------------------------------------
# format_weekly_summary tests
# ---------------------------------------------------------------------------


class TestFormatWeeklySummary:
    """Tests for weekly summary formatting."""

    def test_weekly_no_positions(self) -> None:
        msg = format_weekly_summary([], {"META": None, "MSFT": None})
        assert "Positions: none" in msg
        assert "Scanner running normally" in msg

    def test_weekly_with_open_position(self) -> None:
        positions = {
            "META": {"status": "open", "entry_price": 580.0},
            "MSFT": None,
        }
        msg = format_weekly_summary([], positions)
        assert "META" in msg
        assert "open" in msg
        assert "580" in msg


# ---------------------------------------------------------------------------
# send_telegram tests
# ---------------------------------------------------------------------------


class TestSendTelegram:
    """Tests for send_telegram with mocked network."""

    def test_no_token_returns_false(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            assert send_telegram("test") is False

    def test_success_returns_true(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch.dict("os.environ", {
            "TELEGRAM_BOT_TOKEN": "fake_token",
            "TELEGRAM_CHAT_ID": "12345",
        }):
            with patch(
                "engine.notifier.urllib.request.urlopen",
                return_value=mock_resp,
            ):
                assert send_telegram("test message") is True

    def test_network_error_returns_false(self) -> None:
        with patch.dict("os.environ", {
            "TELEGRAM_BOT_TOKEN": "fake_token",
            "TELEGRAM_CHAT_ID": "12345",
        }):
            with patch(
                "engine.notifier.urllib.request.urlopen",
                side_effect=urllib.error.URLError("timeout"),
            ):
                assert send_telegram("test") is False


# ---------------------------------------------------------------------------
# format_daily_summary tests
# ---------------------------------------------------------------------------


class TestFormatDailySummary:
    """Tests for format_daily_summary (always-on daily message)."""

    @staticmethod
    def _paper(**kw: float) -> dict:
        return {
            "total_pnl": kw.get("total_pnl", 0),
            "n_trades": kw.get("n_trades", 0),
            "win_rate": kw.get("win_rate", 0),
            "n_open": kw.get("n_open", 0),
        }

    def test_always_returns_string(self) -> None:
        """Even with empty data, always returns a message."""
        msg = format_daily_summary({}, self._paper(), [], {})
        assert isinstance(msg, str)
        assert "Signal Radar" in msg
        assert "No actionable signals" in msg

    def test_no_signals_shows_no_actionable(self) -> None:
        """When only NO_SIGNAL results, says so explicitly."""
        all_results = {
            "rsi2": [
                SignalResult(
                    signal=Signal.NO_SIGNAL, symbol="META",
                    strategy="rsi2", notes="No conditions met",
                    details={"rsi2": 55.0},
                ),
            ],
        }
        msg = format_daily_summary(all_results, self._paper(), [], {})
        assert "No actionable signals" in msg

    def test_with_buy_signal(self) -> None:
        """BUY signal appears in the daily summary."""
        all_results = {
            "rsi2": [
                SignalResult(
                    signal=Signal.BUY, symbol="META",
                    strategy="rsi2",
                    notes="RSI(2)=4.5 < 10, trend OK",
                    details={"rsi2": 4.5},
                ),
            ],
        }
        msg = format_daily_summary(all_results, self._paper(), [], {})
        assert "BUY META" in msg
        assert "RSI2" in msg

    def test_open_positions_with_unrealized(self) -> None:
        """Open positions show unrealized PnL."""
        positions = [
            {"strategy": "rsi2", "symbol": "META",
             "entry_price": 580.0, "entry_date": "2026-03-01", "shares": 8},
        ]
        prices = {"META": 590.0}
        msg = format_daily_summary(
            {}, self._paper(n_open=1), positions, prices,
        )
        assert "Positions" in msg
        assert "META" in msg
        assert "+$80.00" in msg  # (590 - 580) * 8

    def test_approaching_triggers(self) -> None:
        """Approaching triggers section rendered."""
        approaching = [
            {"symbol": "MSFT", "strategy": "rsi2",
             "label": "RSI=15.0/10", "pct": 50.0},
        ]
        msg = format_daily_summary(
            {}, self._paper(), [], {}, approaching,
        )
        assert "Approaching" in msg
        assert "RSI2 MSFT" in msg

    def test_paper_summary_in_header(self) -> None:
        """Paper trading stats appear in the message."""
        msg = format_daily_summary(
            {},
            self._paper(total_pnl=125.50, n_trades=10, win_rate=70.0, n_open=2),
            [], {},
        )
        assert "+$125.50" in msg
        assert "10 closed" in msg
        assert "70% WR" in msg
