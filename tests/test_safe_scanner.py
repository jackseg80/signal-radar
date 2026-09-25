"""Decision gates and next-opening accounting for scanner v2."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from data.db import SignalRadarDB
from engine.fee_model import FEE_MODEL_SAXO_CH_USD_PROVISIONAL
from engine.trading_calendar import (
    is_expired, last_completed_session, next_session, session_month_progress,
    session_open,
)
from scripts import safe_scanner


def test_nyse_month_holiday_and_early_close() -> None:
    """Calendar counts future sessions and does not confuse a half day with closure."""
    assert session_month_progress("2026-09-23") == (16, 6)
    assert next_session("2026-11-25") == "2026-11-27"  # Thanksgiving
    assert session_month_progress("2026-11-27")[1] == 2
    assert session_open("2026-11-27").hour == 14  # 09:30 ET / 14:30 UTC
    assert last_completed_session(datetime(2026, 9, 28, 13, tzinfo=timezone.utc)) == "2026-09-25"
    assert is_expired("2026-09-28", datetime(2026, 9, 28, 13, tzinfo=timezone.utc)) is False


def _frame(source: str) -> pd.DataFrame:
    """Construct a small verified-looking frame for isolated scanner tests."""
    dates = pd.date_range("2026-08-01", source, freq="B")
    return pd.DataFrame({"Close": [100.0] * len(dates)}, index=dates)


def _indicator(*_args: object) -> dict:
    """Trigger the calendar strategy without relying on synthetic price history."""
    return {
        "close": 100.0, "open": 99.0, "high": 101.0, "low": 98.0,
        "high_yesterday": 101.0, "rsi2": 5.0, "sma200": 90.0,
        "sma5": 99.0, "ibs": 0.1,
        "trading_days_left_in_month": 1, "trading_day_of_month": 20,
    }


class FakeLoader:
    """Return a fixed frame for one exact completed exchange session."""

    def get_daily_candles_strict(
        self, symbol: str, start: str, end: str, expected_session: str,
    ) -> pd.DataFrame:
        assert symbol == "META"
        return _frame(expected_session)


def test_confirmation_and_rerun_are_fail_closed_and_idempotent(
    tmp_path, monkeypatch,
) -> None:
    """The same session cannot create a second recommendation or paper order."""
    db = SignalRadarDB(tmp_path / "radar.db")
    monkeypatch.setattr(safe_scanner, "load_config", lambda: {
        "strategies": {"tom": {"enabled": True, "universe": ["META"],
                                "watchlist": [], "params": {}}}
    })
    monkeypatch.setattr(safe_scanner, "compute_indicators", _indicator)
    monkeypatch.setattr(safe_scanner, "_score", lambda *_: (0.002, 0.1, 50))
    monkeypatch.setattr(safe_scanner, "load_saxo_ch_costs",
                        lambda: (FEE_MODEL_SAXO_CH_USD_PROVISIONAL, True))
    monkeypatch.setattr("engine.notifier.send_telegram", lambda *_: True)
    now = datetime(2026, 9, 23, 21, tzinfo=timezone.utc)

    first = safe_scanner.run_safe_scanner(db=db, loader=FakeLoader(), now=now)
    assert first["decisions"][0]["eligibility"] == "BLOCKED"
    assert "not confirmed" in first["decisions"][0]["reasons"][0]
    assert not any("cash cannot buy" in reason for reason in first["decisions"][0]["reasons"])
    assert first["decisions"][0]["details"]["paper_status"] == "PENDING_BUY"
    assert len(db.get_pending_paper_orders()) == 1
    _, legacy_api_rows = db.get_latest_signals()
    assert legacy_api_rows[0]["signal"] == "SKIP"
    assert legacy_api_rows[0]["paper_signal"] == "BUY"
    assert legacy_api_rows[0]["paper_status"] == "PENDING_BUY"

    db.confirm_account("2026-09-23", 5000.0, [])
    with db._connect() as conn:
        conn.execute(
            "INSERT INTO strategy_scores "
            "(strategy,symbol,asof_session,n_trades,monthly_lower_bound,max_drawdown,calibrated,verdict) "
            "VALUES ('tom','META','2026-09-23',50,0.002,0.1,1,'VALIDATED')"
        )
    second = safe_scanner.run_safe_scanner(db=db, loader=FakeLoader(), now=now)
    assert second["decisions"][0]["eligibility"] == "ELIGIBLE"
    assert len(db.get_pending_paper_orders()) == 1
    assert second["decisions"][0]["details"]["paper_indicative_shares"] == first["decisions"][0]["details"]["paper_indicative_shares"]
    third = safe_scanner.run_safe_scanner(db=db, loader=FakeLoader(), now=now)
    assert third["decisions"][0]["eligibility"] == "ELIGIBLE"
    assert len(db.get_pending_paper_orders()) == 1


def test_paper_fill_waits_for_next_open_and_preserves_legacy(tmp_path) -> None:
    """Opening gaps re-size whole shares and do not rewrite the old series."""
    db = SignalRadarDB(tmp_path / "radar.db")
    db.open_paper_position("tom", "META", "2026-09-22", 100, 10)
    assert db.queue_paper_order("2026-09-22", "2026-09-23", "tom", "META", "BUY", 5000, 48)
    assert db.fill_due_paper_orders("2026-09-22", FEE_MODEL_SAXO_CH_USD_PROVISIONAL) == []
    assert db.get_v2_open_positions() == []
    df = pd.DataFrame({
        "Open": [120.0], "High": [123.0], "Low": [119.0], "Close": [121.0],
        "Adj_Open": [120.0], "Adj_High": [123.0], "Adj_Low": [119.0],
        "Adj_Close": [121.0], "Volume": [10000],
        "Dividends": [0.0], "Stock Splits": [0.0],
    }, index=[pd.Timestamp("2026-09-23")])
    db.save_prices_v2("META", df)
    filled = db.fill_due_paper_orders("2026-09-23", FEE_MODEL_SAXO_CH_USD_PROVISIONAL)
    assert filled[0]["filled_price"] == 120.0
    assert filled[0]["filled_shares"] < 48
    assert len(db.get_v2_open_positions()) == 1
    assert len(db.get_open_positions()) == 1
    assert db.fill_due_paper_orders("2026-09-23", FEE_MODEL_SAXO_CH_USD_PROVISIONAL) == []


def test_saxo_costs_apply_on_both_sides() -> None:
    """Public provisional stamp duty and commission floor affect both sides."""
    model = FEE_MODEL_SAXO_CH_USD_PROVISIONAL
    assert model.tax_pct == pytest.approx(0.0015)
    assert model.exit_tax_pct == pytest.approx(0.0015)
    assert model.total_entry_cost(5000) == pytest.approx(12.75)
    assert model.regulatory_exit_pct == pytest.approx(0.0000206)
    assert model.total_exit_cost(5000) == pytest.approx(12.853)


@pytest.mark.parametrize(
    ("cash", "holdings", "expected_reason"),
    [
        (5000.0, ["META"], "title already held at Saxo"),
        (50.0, [], "cannot buy one share"),
    ],
)
def test_confirmed_holdings_and_cash_block_an_infeasible_buy(
    tmp_path, monkeypatch, cash, holdings, expected_reason,
) -> None:
    """A technically valid signal is never an order when Saxo cannot fund it."""
    db = SignalRadarDB(tmp_path / "radar.db")
    monkeypatch.setattr(safe_scanner, "load_config", lambda: {
        "strategies": {"tom": {"enabled": True, "universe": ["META"],
                                "watchlist": [], "params": {}}}
    })
    monkeypatch.setattr(safe_scanner, "compute_indicators", _indicator)
    monkeypatch.setattr(safe_scanner, "_score", lambda *_: (0.002, 0.1, 50))
    monkeypatch.setattr(safe_scanner, "load_saxo_ch_costs",
                        lambda: (FEE_MODEL_SAXO_CH_USD_PROVISIONAL, True))
    monkeypatch.setattr("engine.notifier.send_telegram", lambda *_: True)
    db.confirm_account("2026-09-23", cash, holdings)
    with db._connect() as conn:
        conn.execute(
            "INSERT INTO strategy_scores "
            "(strategy,symbol,asof_session,n_trades,monthly_lower_bound,max_drawdown,calibrated,verdict) "
            "VALUES ('tom','META','2026-09-23',50,0.002,0.1,1,'VALIDATED')"
        )
    result = safe_scanner.run_safe_scanner(
        db=db, loader=FakeLoader(),
        now=datetime(2026, 9, 23, 21, tzinfo=timezone.utc),
    )
    assert result["decisions"][0]["eligibility"] == "BLOCKED"
    assert any(expected_reason in reason for reason in result["decisions"][0]["reasons"])
    assert result["decisions"][0]["details"]["paper_status"] == "PENDING_BUY"
    assert [(order["side"], order["symbol"]) for order in db.get_pending_paper_orders()] == [
        ("BUY", "META")
    ]


def test_exit_signal_cannot_fund_another_buy_at_the_same_open(tmp_path, monkeypatch) -> None:
    """The global paper portfolio remains occupied until a sale actually fills."""
    from scripts.daily_scanner import Signal, SignalResult

    class TwoSymbolLoader:
        """Supply the same closed session for both synthetic titles."""

        def get_daily_candles_strict(self, symbol, start, end, expected_session):
            return _frame(expected_session)

    db = SignalRadarDB(tmp_path / "radar.db")
    with db._connect() as conn:
        conn.execute(
            "INSERT INTO paper_positions_v2 "
            "(strategy,symbol,entry_session,entry_price,shares,cost_basis,entry_fee) "
            "VALUES ('tom','META','2026-09-22',100,40,4000,16)"
        )
        conn.execute(
            "INSERT INTO strategy_scores "
            "(strategy,symbol,asof_session,n_trades,monthly_lower_bound,max_drawdown,calibrated,verdict) "
            "VALUES ('tom','NVDA','2026-09-23',50,0.002,0.1,1,'VALIDATED')"
        )
    db.confirm_account("2026-09-23", 5000, ["META"])
    monkeypatch.setattr(safe_scanner, "load_config", lambda: {
        "strategies": {"tom": {"enabled": True, "universe": ["META", "NVDA"],
                                "watchlist": [], "params": {}}}
    })
    monkeypatch.setattr(safe_scanner, "compute_indicators", _indicator)
    monkeypatch.setattr(safe_scanner, "_score", lambda *_: (0.002, 0.1, 50))
    monkeypatch.setattr(safe_scanner, "load_saxo_ch_costs",
                        lambda: (FEE_MODEL_SAXO_CH_USD_PROVISIONAL, True))
    monkeypatch.setattr(safe_scanner, "_technical_result",
                        lambda name, params, symbol, ind, position, *args: SignalResult(
                            signal=(Signal.SELL if position else Signal.NO_SIGNAL)
                            if symbol == "META" else Signal.BUY,
                        ))
    monkeypatch.setattr("engine.notifier.send_telegram", lambda *_: True)
    result = safe_scanner.run_safe_scanner(
        db=db, loader=TwoSymbolLoader(),
        now=datetime(2026, 9, 23, 21, tzinfo=timezone.utc),
    )
    decisions = {row["symbol"]: row for row in result["decisions"]}
    assert decisions["META"]["details"]["paper_status"] == "PENDING_SELL"
    assert decisions["NVDA"]["eligibility"] == "ELIGIBLE"
    assert decisions["NVDA"]["details"]["paper_status"] == "BLOCKED"
    assert any("single paper portfolio" in reason for reason
               in decisions["NVDA"]["details"]["paper_reasons"])
    assert not any("cannot buy one share" in reason for reason
                   in decisions["NVDA"]["details"]["paper_reasons"])
    assert [(row["side"], row["symbol"]) for row in db.get_pending_paper_orders()] == [
        ("SELL", "META")
    ]


def test_next_ranked_title_is_selected_when_the_first_is_held(tmp_path, monkeypatch) -> None:
    """The highest feasible candidate wins, not merely the highest raw score."""
    from scripts.daily_scanner import Signal, SignalResult

    class RankedLoader:
        """Supply a separate identifiable frame for each title."""

        def get_daily_candles_strict(self, symbol, start, end, expected_session):
            frame = _frame(expected_session)
            frame.attrs["symbol"] = symbol
            return frame

    db = SignalRadarDB(tmp_path / "radar.db")
    db.confirm_account("2026-09-23", 5000, ["META"])
    with db._connect() as conn:
        for symbol in ("META", "NVDA"):
            conn.execute(
                "INSERT INTO strategy_scores "
                "(strategy,symbol,asof_session,n_trades,monthly_lower_bound,max_drawdown,calibrated,verdict) "
                "VALUES ('tom',?, '2026-09-23',50,0.002,0.1,1,'VALIDATED')",
                (symbol,),
            )
    monkeypatch.setattr(safe_scanner, "load_config", lambda: {
        "strategies": {"tom": {"enabled": True, "universe": ["META", "NVDA"],
                                "watchlist": [], "params": {}}}
    })
    monkeypatch.setattr(safe_scanner, "compute_indicators", _indicator)
    monkeypatch.setattr(safe_scanner, "_score",
                        lambda df, *_: (0.003 if df.attrs["symbol"] == "META" else 0.002,
                                        0.1, 50))
    monkeypatch.setattr(safe_scanner, "load_saxo_ch_costs",
                        lambda: (FEE_MODEL_SAXO_CH_USD_PROVISIONAL, True))
    monkeypatch.setattr(safe_scanner, "_technical_result",
                        lambda *args: SignalResult(signal=Signal.BUY))
    monkeypatch.setattr("engine.notifier.send_telegram", lambda *_: True)
    result = safe_scanner.run_safe_scanner(
        db=db, loader=RankedLoader(),
        now=datetime(2026, 9, 23, 21, tzinfo=timezone.utc),
    )
    decisions = {row["symbol"]: row for row in result["decisions"]}
    assert decisions["META"]["eligibility"] == "BLOCKED"
    assert decisions["NVDA"]["eligibility"] == "ELIGIBLE"
    assert decisions["META"]["details"]["paper_status"] == "PENDING_BUY"
    assert decisions["NVDA"]["details"]["paper_status"] == "BLOCKED"
    assert [(row["side"], row["symbol"]) for row in db.get_pending_paper_orders()] == [
        ("BUY", "META")
    ]


def test_overdue_paper_fills_apply_actions_in_session_order(tmp_path) -> None:
    """A late Yahoo bar cannot give a past sale future split shares."""
    from engine.fee_model import FeeModel

    def bar(session: str, price: float, split: float = 0.0) -> pd.DataFrame:
        """Build one raw and adjusted candle for the paper-order ledger."""
        return pd.DataFrame({
            "Open": [price], "High": [price], "Low": [price],
            "Close": [price], "Adj_Open": [price],
            "Adj_High": [price], "Adj_Low": [price],
            "Adj_Close": [price], "Volume": [1000.0],
            "Dividends": [0.0], "Stock Splits": [split],
        }, index=[pd.Timestamp(session)])

    sale_db = SignalRadarDB(tmp_path / "sale.db")
    with sale_db._connect() as conn:
        conn.execute(
            "INSERT INTO paper_positions_v2 "
            "(strategy,symbol,entry_session,entry_price,shares,cost_basis,entry_fee) "
            "VALUES ('tom','META','2026-09-21',100,10,1000,0)"
        )
    assert sale_db.queue_paper_order(
        "2026-09-21", "2026-09-22", "tom", "META", "SELL",
    )
    sale_db.save_prices_v2("META", bar("2026-09-23", 50, split=2))
    assert sale_db.fill_due_paper_orders("2026-09-24", FeeModel()) == []
    assert sale_db.get_v2_open_positions()[0]["shares"] == 10

    sale_db.save_prices_v2("META", bar("2026-09-22", 100))
    filled_sale = sale_db.fill_due_paper_orders("2026-09-24", FeeModel())
    assert filled_sale[0]["filled_shares"] == 10
    assert sale_db.get_v2_closed_trades()[0]["pnl_dollars"] == 0
    assert sale_db._query("SELECT * FROM paper_actions_v2") == []

    buy_db = SignalRadarDB(tmp_path / "buy.db")
    assert buy_db.queue_paper_order(
        "2026-09-21", "2026-09-22", "tom", "META", "BUY", 5000, 50,
    )
    buy_db.save_prices_v2("META", bar("2026-09-22", 100))
    buy_db.save_prices_v2("META", bar("2026-09-23", 50, split=2))
    filled_buy = buy_db.fill_due_paper_orders("2026-09-24", FeeModel())
    assert filled_buy[0]["filled_shares"] == 50
    assert buy_db.get_v2_open_positions()[0]["shares"] == 100

def test_real_position_does_not_change_paper_entry(tmp_path, monkeypatch) -> None:
    """A live Saxo position may exit while the independent paper ledger enters."""
    from scripts.daily_scanner import Signal, SignalResult

    db = SignalRadarDB(tmp_path / "radar.db")
    assert db.open_live_trade("tom", "META", "2026-09-21", 100, 2)
    db.confirm_account("2026-09-23", 5000, ["META"])
    monkeypatch.setattr(safe_scanner, "load_config", lambda: {
        "strategies": {"tom": {"enabled": True, "universe": ["META"],
                                "watchlist": [], "params": {}}}
    })
    monkeypatch.setattr(safe_scanner, "compute_indicators", _indicator)
    monkeypatch.setattr(safe_scanner, "_score", lambda *_: (0.002, 0.1, 50))
    monkeypatch.setattr(safe_scanner, "load_saxo_ch_costs",
                        lambda: (FEE_MODEL_SAXO_CH_USD_PROVISIONAL, False))
    monkeypatch.setattr(safe_scanner, "_technical_result",
                        lambda name, params, symbol, ind, position, *args: SignalResult(
                            signal=Signal.SELL if position else Signal.BUY,
                        ))
    monkeypatch.setattr("engine.notifier.send_telegram", lambda *_: True)
    result = safe_scanner.run_safe_scanner(
        db=db, loader=FakeLoader(),
        now=datetime(2026, 9, 23, 21, tzinfo=timezone.utc),
    )
    row = result["decisions"][0]
    assert row["technical_signal"] == "SELL"
    assert row["eligibility"] == "EXIT_SIGNAL"
    assert row["details"]["paper_signal"] == "BUY"
    assert row["details"]["paper_status"] == "PENDING_BUY"
    assert [(order["side"], order["symbol"]) for order in db.get_pending_paper_orders()] == [
        ("BUY", "META")
    ]

def test_paper_observes_complete_symbols_when_another_has_missing_data(
    tmp_path, monkeypatch,
) -> None:
    """Incomplete Yahoo coverage blocks real buys but labels partial paper."""
    from scripts.daily_scanner import Signal, SignalResult

    class IncompleteLoader:
        """Return META while Yahoo has no verified V session."""

        def get_daily_candles_strict(
            self, symbol: str, start: str, end: str, expected_session: str,
        ) -> pd.DataFrame:
            if symbol == "V":
                raise ValueError("V: missing XNYS bar 2026-09-22")
            return _frame(expected_session)

    db = SignalRadarDB(tmp_path / "radar.db")
    monkeypatch.setattr(safe_scanner, "load_config", lambda: {
        "strategies": {"ibs": {"enabled": True, "universe": ["META", "V"],
                                "watchlist": [], "params": {}}}
    })
    monkeypatch.setattr(safe_scanner, "compute_indicators", _indicator)
    monkeypatch.setattr(safe_scanner, "_score", lambda *_: (0.002, 0.1, 50))
    monkeypatch.setattr(safe_scanner, "load_saxo_ch_costs",
                        lambda: (FEE_MODEL_SAXO_CH_USD_PROVISIONAL, False))
    monkeypatch.setattr(safe_scanner, "_technical_result",
                        lambda *args: SignalResult(signal=Signal.BUY))
    monkeypatch.setattr("engine.notifier.send_telegram", lambda *_: True)

    result = safe_scanner.run_safe_scanner(
        db=db, loader=IncompleteLoader(),
        now=datetime(2026, 9, 23, 21, tzinfo=timezone.utc),
    )
    rows = {row["symbol"]: row for row in result["decisions"]}
    assert rows["V"]["eligibility"] == "DATA_MISSING"
    assert rows["META"]["eligibility"] == "BLOCKED"
    assert any("market data missing" in reason for reason in rows["META"]["reasons"])
    assert rows["META"]["details"]["paper_status"] == "PENDING_BUY"
    assert "V" in rows["META"]["details"]["paper_warnings"][0]
    assert [(order["side"], order["symbol"]) for order in db.get_pending_paper_orders()] == [
        ("BUY", "META")
    ]
    _, api_rows = db.get_latest_signals()
    paper_meta = next(row for row in api_rows if row["symbol"] == "META")
    assert paper_meta["signal"] == "SKIP"
    assert paper_meta["paper_status"] == "PENDING_BUY"
    assert paper_meta["paper_warnings"]

def test_real_exit_uses_only_the_chosen_primary_strategy(tmp_path, monkeypatch) -> None:
    """A real TOM purchase exits by TOM while IBS stays a separate signal."""
    from scripts.daily_scanner import Signal, SignalResult

    db = SignalRadarDB(tmp_path / "primary.db")
    assert db.open_live_trade(
        "tom", "META", "2026-09-21", 100, 2, instrument_type="stock",
    )
    monkeypatch.setattr(safe_scanner, "load_config", lambda: {
        "strategies": {
            "tom": {"enabled": True, "universe": ["META"],
                    "watchlist": [], "params": {}},
            "ibs": {"enabled": True, "universe": ["META"],
                    "watchlist": [], "params": {}},
        }
    })
    monkeypatch.setattr(safe_scanner, "compute_indicators", _indicator)
    monkeypatch.setattr(safe_scanner, "_score", lambda *_: (0.002, 0.1, 50))
    monkeypatch.setattr(
        safe_scanner, "load_saxo_ch_costs",
        lambda: (FEE_MODEL_SAXO_CH_USD_PROVISIONAL, False),
    )
    monkeypatch.setattr(
        safe_scanner, "_technical_result",
        lambda name, params, symbol, ind, position, *args: SignalResult(
            signal=Signal.SELL if position else Signal.BUY,
        ),
    )
    monkeypatch.setattr("engine.notifier.send_telegram", lambda *_: True)
    result = safe_scanner.run_safe_scanner(
        db=db, loader=FakeLoader(),
        now=datetime(2026, 9, 23, 21, tzinfo=timezone.utc),
    )
    by_strategy = {row["strategy"]: row for row in result["decisions"]}
    assert by_strategy["tom"]["technical_signal"] == "SELL"
    assert by_strategy["ibs"]["technical_signal"] == "BUY"
    assert len(db.get_open_live_trades()) == 1
