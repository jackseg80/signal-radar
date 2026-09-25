"""Independent signal follow-up must never consume shared paper or Saxo cash."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from data.db import SignalRadarDB
from engine.fee_model import FEE_MODEL_SAXO_CH_USD_PROVISIONAL
from scripts import safe_scanner
from scripts.daily_scanner import Signal, SignalResult


FEE = FEE_MODEL_SAXO_CH_USD_PROVISIONAL


def _bar(session: str, opening: float, *, dividend: float = 0, split: float = 0) -> pd.DataFrame:
    """Build one raw and adjusted price bar for a controlled opening."""
    return pd.DataFrame({
        "Open": [opening], "High": [opening + 1], "Low": [opening - 1],
        "Close": [opening], "Adj_Open": [opening], "Adj_High": [opening + 1],
        "Adj_Low": [opening - 1], "Adj_Close": [opening], "Volume": [10000],
        "Dividends": [dividend], "Stock Splits": [split],
    }, index=[pd.Timestamp(session)])


def test_simultaneous_signals_fill_independently_at_next_gap(tmp_path) -> None:
    """Two strategies may track one title and another title despite shared paper cash."""
    db = SignalRadarDB(tmp_path / "radar.db")
    db.open_paper_position("tom", "OLD", "2026-09-22", 100, 2)
    for strategy, symbol in (("tom", "META"), ("ibs", "META"), ("tom", "NFLX")):
        assert db.queue_follow_order(
            "2026-09-23", "2026-09-24", strategy, symbol, "BUY",
        )
    assert len(db.get_follow_orders()) == 3
    assert db.fill_due_follow_orders("2026-09-23", FEE) == []
    assert db.get_follow_positions() == []
    db.save_prices_v2("META", _bar("2026-09-24", 120))
    db.save_prices_v2("NFLX", _bar("2026-09-24", 140))
    filled = db.fill_due_follow_orders("2026-09-24", FEE)
    assert len(filled) == 3
    assert all(order["status"] == "filled" for order in filled)
    positions = db.get_follow_positions()
    assert {(p["strategy"], p["symbol"]) for p in positions} == {
        ("tom", "META"), ("ibs", "META"), ("tom", "NFLX"),
    }
    assert all(p["entry_price"] in {120, 140} for p in positions)
    assert all(p["cost_basis"] + p["entry_fee"] <= 5000 for p in positions)
    assert len(db.get_open_positions()) == 1
    assert db.get_v2_open_positions() == []
    assert db.fill_due_follow_orders("2026-09-24", FEE) == []


def test_missing_bar_only_holds_its_own_virtual_signal(tmp_path) -> None:
    """A missing target bar must never create a fill or block another title."""
    db = SignalRadarDB(tmp_path / "radar.db")
    for symbol in ("META", "NFLX"):
        db.queue_follow_order("2026-09-23", "2026-09-24", "tom", symbol, "BUY")
    db.save_prices_v2("NFLX", _bar("2026-09-24", 120))
    filled = db.fill_due_follow_orders("2026-09-24", FEE)
    assert len(filled) == 1
    assert filled[0]["symbol"] == "NFLX"
    assert [p["symbol"] for p in db.get_follow_positions()] == ["NFLX"]
    assert [o["symbol"] for o in db.get_follow_orders()] == ["META"]


def test_virtual_exit_uses_next_open_and_corporate_actions(tmp_path) -> None:
    """A split and dividend update the virtual lot without changing paper cash."""
    db = SignalRadarDB(tmp_path / "radar.db")
    db.queue_follow_order("2026-09-21", "2026-09-22", "tom", "META", "BUY")
    db.save_prices_v2("META", _bar("2026-09-22", 100))
    db.fill_due_follow_orders("2026-09-22", FEE)
    pos = db.get_follow_positions()[0]
    db.save_prices_v2("META", _bar("2026-09-23", 51, dividend=0.5, split=2))
    db.apply_follow_actions("2026-09-23")
    updated = db.get_follow_positions()[0]
    assert updated["shares"] == pos["shares"] * 2
    assert updated["dividend_cash"] == updated["shares"] * 0.5
    db.apply_follow_actions("2026-09-23")
    assert db.get_follow_positions()[0]["dividend_cash"] == updated["dividend_cash"]
    assert db.queue_follow_order(
        "2026-09-23", "2026-09-24", "tom", "META", "SELL", position_id=pos["id"],
    )
    assert db.fill_due_follow_orders("2026-09-23", FEE) == []
    db.save_prices_v2("META", _bar("2026-09-24", 54))
    db.fill_due_follow_orders("2026-09-24", FEE)
    closed = db.get_follow_positions("closed")[0]
    assert closed["exit_price"] == 54
    assert closed["pnl_dollars"] == (
        closed["shares"] * 54 - closed["exit_fee"]
        + closed["dividend_cash"] - closed["cost_basis"] - closed["entry_fee"]
    )
    assert db.get_v2_paper_cash() == 5000


def test_scanner_tracks_all_positive_signals_without_saxo_confirmation(tmp_path, monkeypatch) -> None:
    """Saxo and the single paper portfolio cannot veto independent follow-up."""
    class Loader:
        """Return a complete synthetic series for each controlled symbol."""

        def get_daily_candles_strict(self, symbol, start, end, expected_session):
            return pd.DataFrame(
                {"Close": [100.0] * 40},
                index=pd.date_range(end=expected_session, periods=40, freq="B"),
            )

    db = SignalRadarDB(tmp_path / "radar.db")
    monkeypatch.setattr(safe_scanner, "load_config", lambda: {
        "strategies": {
            "tom": {"enabled": True, "universe": ["META", "NFLX"], "watchlist": [], "params": {}},
            "ibs": {"enabled": True, "universe": ["META"], "watchlist": [], "params": {}},
        },
    })
    monkeypatch.setattr(safe_scanner, "compute_indicators", lambda *_: {
        "close": 100.0, "open": 100.0, "high": 101.0, "low": 99.0,
        "high_yesterday": 101.0, "rsi2": 5.0, "sma200": 90.0,
        "sma5": 99.0, "ibs": 0.1, "trading_days_left_in_month": 1,
        "trading_day_of_month": 20,
    })
    monkeypatch.setattr(safe_scanner, "_technical_result",
                        lambda name, params, symbol, ind, position, *args:
                        SignalResult(signal=Signal.HOLD if position else Signal.BUY))
    monkeypatch.setattr(safe_scanner, "_score", lambda *_: (0.002, 0.1, 50))
    monkeypatch.setattr(safe_scanner, "load_saxo_ch_costs", lambda: (FEE, False))
    monkeypatch.setattr("engine.notifier.send_telegram", lambda *_: True)
    now = datetime(2026, 9, 23, 21, tzinfo=timezone.utc)
    first = safe_scanner.run_safe_scanner(db=db, loader=Loader(), now=now)
    assert all(row["eligibility"] != "ELIGIBLE" for row in first["decisions"])
    assert {(o["strategy"], o["symbol"]) for o in db.get_follow_orders()} == {
        ("tom", "META"), ("ibs", "META"), ("tom", "NFLX"),
    }
    assert len(db.get_pending_paper_orders()) == 1
    safe_scanner.run_safe_scanner(db=db, loader=Loader(), now=now)
    assert len(db.get_follow_orders()) == 3
    assert len(db.get_pending_paper_orders()) == 1


def test_follow_api_keeps_per_signal_notional_separate(tmp_path, monkeypatch) -> None:
    """The dashboard reports each virtual lot without a fictitious shared balance."""
    from api.routes.positions import get_signal_follow_positions

    db = SignalRadarDB(tmp_path / "radar.db")
    db.queue_follow_order("2026-09-23", "2026-09-24", "tom", "META", "BUY")
    db.save_prices_v2("META", _bar("2026-09-24", 120))
    db.fill_due_follow_orders("2026-09-24", FEE)
    monkeypatch.setattr(
        "engine.fee_model.load_saxo_ch_costs", lambda: (FEE, False),
    )
    payload = get_signal_follow_positions(db)
    assert payload["series"] == "independent_signal_follow"
    assert payload["notional_per_signal_usd"] == 5000
    assert payload["costs_verified"] is False
    assert payload["positions"][0]["entry_price"] == 120
    assert payload["positions"][0]["unrealized_pnl_estimate"] < 0
    assert payload["closed_count"] == 0
    assert db.get_v2_paper_cash() == 5000


def test_same_title_strategies_exit_separately(tmp_path) -> None:
    """A TOM exit must not close the simultaneous IBS virtual lot."""
    db = SignalRadarDB(tmp_path / "radar.db")
    for strategy in ("tom", "ibs"):
        db.queue_follow_order("2026-09-21", "2026-09-22", strategy, "META", "BUY")
    db.save_prices_v2("META", _bar("2026-09-22", 100))
    db.fill_due_follow_orders("2026-09-22", FEE)
    opened = {p["strategy"]: p for p in db.get_follow_positions()}
    assert len(opened) == 2
    db.queue_follow_order(
        "2026-09-23", "2026-09-24", "tom", "META", "SELL",
        position_id=opened["tom"]["id"],
    )
    db.save_prices_v2("META", _bar("2026-09-24", 105))
    db.fill_due_follow_orders("2026-09-24", FEE)
    assert [p["strategy"] for p in db.get_follow_positions()] == ["ibs"]
    assert [p["strategy"] for p in db.get_follow_positions("closed")] == ["tom"]
