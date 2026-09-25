"""Manual Signal Radar operations remain separate from Saxo cash and paper."""

from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from api.app import app
from api.dependencies import get_db
from data.db import SignalRadarDB


@pytest.fixture
def client_and_db(tmp_path):
    """Provide an isolated API and database for manual operation checks."""
    db = SignalRadarDB(tmp_path / "manual.db")
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield client, db
    app.dependency_overrides.clear()


def _decision(db: SignalRadarDB, strategy: str, symbol: str) -> None:
    """Store a buy without granting real-account eligibility."""
    db.upsert_decision({
        "source_session": "2026-09-24",
        "target_session": "2026-09-25",
        "strategy": strategy,
        "symbol": symbol,
        "technical_signal": "BUY",
        "eligibility": "BLOCKED",
        "reasons": ["single paper portfolio already committed"],
        "expires_at": "2026-09-25T13:30:00+00:00",
    })


def test_cash_snapshot_does_not_confirm_full_saxo_account(client_and_db) -> None:
    """Cash and the partial trade journal never unlock the full-account gate."""
    client, db = client_and_db
    saved = client.post("/api/account/manual-cash", json={"available_usd": 10000})
    assert saved.status_code == 200
    assert client.get("/api/account/manual-cash").json()["snapshot"]["available_usd"] == 10000
    assert db.get_account_confirmation("2026-09-24") is None
    assert db.get_live_summary()["n_trades"] == 0


def test_linked_stock_and_unlinked_cfd_with_real_costs(client_and_db) -> None:
    """One primary strategy links to a buy; a retroactive CFD remains usable."""
    client, db = client_and_db
    _decision(db, "rsi2", "META")
    _decision(db, "ibs", "META")
    stock = client.post("/api/live/open", params={
        "strategy": "rsi2", "symbol": "META", "instrument_type": "stock",
        "signal_session": "2026-09-24", "entry_date": "2026-09-25",
        "entry_price": 100, "shares": 5, "fees": 1,
    })
    assert stock.status_code == 200
    cfd = client.post("/api/live/open", params={
        "strategy": "tom", "symbol": "META", "instrument_type": "cfd",
        "signal_session": "2026-09-20", "entry_date": "2026-09-26",
        "entry_price": 100, "shares": 5, "fees": 10,
        "notes": "Saisie retrospective",
    })
    assert cfd.status_code == 200
    trades = db.get_open_live_trades()
    assert len(trades) == 2
    assert trades[0]["signal_linked"] == 1
    assert trades[1]["signal_linked"] == 0
    assert trades[1]["signal_session"] == "2026-09-20"
    rows = client.get("/api/live/open").json()["trades"]
    assert rows[0]["other_buy_strategies"] == ["ibs"]
    assert rows[1]["other_buy_strategies"] == []
    stock_id, cfd_id = trades[0]["id"], trades[1]["id"]
    stock_close = client.post("/api/live/close/" + str(stock_id), params={
        "exit_date": "2026-09-30", "exit_price": 110, "fees": 1,
    })
    assert stock_close.status_code == 200
    assert stock_close.json()["trade"]["pnl_dollars"] == 48
    assert stock_close.json()["trade"]["net_pnl_verified"] == 1
    assert len(db.get_open_live_trades()) == 1
    cfd_close = client.post("/api/live/close/" + str(cfd_id), params={
        "exit_date": "2026-09-30", "exit_price": 110,
        "fees": 10, "financing_cost": 8,
    })
    assert cfd_close.status_code == 200
    assert cfd_close.json()["trade"]["pnl_dollars"] == 22
    assert cfd_close.json()["trade"]["net_pnl_verified"] == 1
    assert client.get("/api/journal/entries", params={"source": "live"}).json()["total"] == 2


def test_missing_costs_and_legacy_instrument_are_provisional(client_and_db) -> None:
    """Missing actual costs and old rows must not masquerade as verified net P&L."""
    client, db = client_and_db
    db.open_live_trade("rsi2", "META", "2026-09-20", 100, 1)
    old = db.get_open_live_trades()[0]
    assert old["instrument_type"] is None
    close = client.post("/api/live/close/" + str(old["id"]), params={
        "exit_date": "2026-09-21", "exit_price": 105,
    })
    assert close.json()["trade"]["net_pnl_verified"] == 0
    fresh = client.post("/api/live/open", params={
        "strategy": "ibs", "symbol": "META", "instrument_type": "cfd",
        "entry_date": "2026-09-22", "entry_price": 100, "shares": 1,
    })
    assert fresh.status_code == 200
    trade_id = db.get_open_live_trades()[0]["id"]
    result = client.post("/api/live/close/" + str(trade_id), params={
        "exit_date": "2026-09-23", "exit_price": 105,
        "fees": 10,
    })
    assert result.json()["trade"]["net_pnl_verified"] == 0


def test_invalid_manual_operations_rejected(client_and_db) -> None:
    """The manual form accepts only known long stock instruments and valid closes."""
    client, db = client_and_db
    assert client.post("/api/live/open", params={
        "strategy": "rsi2", "symbol": "SPY", "instrument_type": "stock",
        "entry_date": "2026-09-22", "entry_price": 100, "shares": 1,
    }).status_code == 422
    created = client.post("/api/live/open", params={
        "strategy": "rsi2", "symbol": "META", "instrument_type": "stock",
        "entry_date": "2026-09-22", "entry_price": 100, "shares": 1, "fees": 0,
    })
    assert created.status_code == 200
    trade_id = db.get_open_live_trades()[0]["id"]
    assert client.post("/api/live/close/" + str(trade_id), params={
        "exit_date": "2026-09-21", "exit_price": 110, "fees": 0,
    }).status_code == 422
    assert len(db.get_open_live_trades()) == 1


def test_old_live_row_survives_schema_migration(tmp_path) -> None:
    """Existing rows stay present and keep an unknown instrument on upgrade."""
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as conn:
        conn.execute("""CREATE TABLE live_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy TEXT NOT NULL, symbol TEXT NOT NULL,
            entry_date TEXT NOT NULL, entry_price REAL NOT NULL,
            shares REAL NOT NULL, fees_entry REAL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'open', exit_date TEXT,
            exit_price REAL, fees_exit REAL DEFAULT 0,
            pnl_dollars REAL, pnl_pct REAL, notes TEXT DEFAULT '',
            paper_position_id INTEGER, created_at TEXT
        )""")
        conn.execute(
            "INSERT INTO live_trades (strategy, symbol, entry_date, entry_price, shares) "
            "VALUES ('rsi2', 'META', '2026-08-01', 100, 2)"
        )
    db = SignalRadarDB(path)
    rows = db.get_open_live_trades()
    assert len(rows) == 1
    assert rows[0]["symbol"] == "META"
    assert rows[0]["instrument_type"] is None
    assert rows[0]["net_pnl_verified"] == 0


def test_radar_shows_technical_stock_buy_without_real_gate(client_and_db) -> None:
    """A blocked real recommendation and an ETF do not hide the stock trigger."""
    client, db = client_and_db
    db.upsert_scanner_session("2026-09-24", "2026-09-25", "complete")
    _decision(db, "rsi2", "META")
    _decision(db, "ibs", "META")
    _decision(db, "rsi2", "SPY")
    response = client.get("/api/signals/today")
    assert response.status_code == 200
    symbols = [item["symbol"] for item in response.json()["strategies"]["rsi2"]["signals"]]
    assert symbols == ["META"]
    assert response.json()["strategies"]["rsi2"]["signals"][0]["technical_signal"] == "BUY"
    candidates = client.get("/api/signals/candidates").json()["candidates"]
    assert len(candidates) == 1
    assert set(candidates[0]["strategies"]) == {"rsi2", "ibs"}
    assert candidates[0]["eligibility"] == "TECHNICAL"
    overview = client.get("/api/market/overview").json()
    meta = next(item for item in overview["assets"] if item["symbol"] == "META")
    assert meta["strategies"]["rsi2"]["signal"] == "BUY"


def test_future_signal_date_rejected(client_and_db) -> None:
    """A retrospective link cannot point after the recorded purchase."""
    client, _ = client_and_db
    response = client.post("/api/live/open", params={
        "strategy": "rsi2", "symbol": "META", "instrument_type": "stock",
        "signal_session": "2026-09-25", "entry_date": "2026-09-24",
        "entry_price": 100, "shares": 1,
    })
    assert response.status_code == 422
