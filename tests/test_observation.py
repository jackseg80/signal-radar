"""Manual account and broker comparison workflow for the v2 scanner."""

from __future__ import annotations

import pandas as pd
from fastapi.testclient import TestClient

from api.app import app
from api.dependencies import get_db
from api.routes import account, observation
from data.db import SignalRadarDB


def test_account_confirmation_is_scoped_to_the_completed_session(
    tmp_path, monkeypatch,
) -> None:
    """A stale confirmation cannot authorize a later next-open order."""
    db = SignalRadarDB(tmp_path / "radar.db")
    monkeypatch.setattr(account, "last_completed_session", lambda: "2026-09-23")
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            stale = client.post("/api/account/confirm", json={
                "source_session": "2026-09-22", "cash_usd": 5000,
                "holdings": [],
            })
            assert stale.status_code == 409
            assert db.get_account_confirmation("2026-09-23") is None
            current = client.post("/api/account/confirm", json={
                "source_session": "2026-09-23", "cash_usd": 4200,
                "holdings": ["meta", "MSFT", "META"],
            })
            assert current.status_code == 200
            assert current.json()["holdings"] == ["META", "MSFT"]
    finally:
        app.dependency_overrides.clear()


def test_observation_uses_raw_open_even_when_buy_was_blocked(
    tmp_path, monkeypatch,
) -> None:
    """Every candidate can be compared to Saxo during the twenty sessions."""
    db = SignalRadarDB(tmp_path / "radar.db")
    source, target = "2026-09-23", "2026-09-24"
    db.upsert_scanner_session(source, target, "complete")
    db.upsert_decision({
        "source_session": source, "target_session": target,
        "strategy": "tom", "symbol": "META", "technical_signal": "BUY",
        "eligibility": "BLOCKED", "reasons": ["fees unverified"],
        "expires_at": "2026-09-24T13:30:00+00:00",
    })
    frame = pd.DataFrame({
        "Open": [120.0], "High": [122.0], "Low": [119.0],
        "Close": [121.0], "Adj_Open": [120.0], "Adj_High": [122.0],
        "Adj_Low": [119.0], "Adj_Close": [121.0], "Volume": [10000],
        "Dividends": [0.0], "Stock Splits": [0.0],
    }, index=[pd.Timestamp(target)])
    db.save_prices_v2("META", frame)
    db.start_observation(source)
    assert db.log_observation_check(source, "META", 121.0, 121.5, 19.0)
    status = db.get_observation_status(target)
    assert status["candidate_count"] == 1
    assert status["missing_broker_checks"] == 0
    assert status["comparisons"][0]["simulated_open"] == 120.0
    assert status["comparisons"][0]["paper_open"] is None
    assert status["comparisons"][0]["open_gap_pct"] == 100 * (121 / 120 - 1)
    monkeypatch.setattr(observation, "last_completed_session", lambda: target)
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            response = client.get("/api/observation/status")
            assert response.status_code == 200
            assert response.json()["comparisons"][0]["simulated_open"] == 120.0
    finally:
        app.dependency_overrides.clear()


def test_observation_starts_on_next_unobserved_session(tmp_path, monkeypatch) -> None:
    """Starting after a close never counts the earlier session retrospectively."""
    db = SignalRadarDB(tmp_path / "radar.db")
    monkeypatch.setattr(observation, "last_completed_session", lambda: "2026-09-23")
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            started = client.post("/api/observation/start")
            assert started.status_code == 200
            assert started.json()["start_session"] == "2026-09-24"
            status = client.get("/api/observation/status")
            assert status.status_code == 200
            assert status.json()["sessions_elapsed"] == 0
            assert status.json()["sessions_scanned"] == 0
    finally:
        app.dependency_overrides.clear()