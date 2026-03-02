"""Tests for the FastAPI Signal Radar API."""

import pytest
from fastapi.testclient import TestClient

from api.app import app
from api.dependencies import get_db
from data.db import SignalRadarDB


@pytest.fixture
def db(tmp_path):
    """Fresh test DB with sample data."""
    test_db = SignalRadarDB(str(tmp_path / "test.db"))

    # Sample paper positions (open)
    test_db.open_paper_position("rsi2", "NVDA", "2026-03-01", 128.50, 38.0)
    test_db.open_paper_position("ibs", "META", "2026-03-03", 605.00, 8.0)

    # Sample closed trade
    test_db.open_paper_position("rsi2", "MSFT", "2026-02-28", 420.00, 11.0)
    test_db.close_paper_position("rsi2", "MSFT", "2026-03-04", 428.40)

    # Sample signal log (single scanner run)
    test_db.log_signal(
        "2026-03-05 22:15:03", "rsi2", "META", "NO_SIGNAL", 612.30, 42.1, ""
    )
    test_db.log_signal(
        "2026-03-05 22:15:03", "rsi2", "V", "BUY", 280.20, 7.8,
        "RSI(2)=7.8 < 10"
    )
    test_db.log_signal(
        "2026-03-05 22:15:03", "rsi2", "NVDA", "HOLD", 131.40, 25.1, ""
    )
    test_db.log_signal(
        "2026-03-05 22:15:03", "ibs", "META", "HOLD", 612.30, 0.65, ""
    )
    test_db.log_signal(
        "2026-03-05 22:15:03", "ibs", "NVDA", "BUY", 131.40, 0.12,
        "IBS=0.12 < 0.2"
    )
    test_db.log_signal(
        "2026-03-05 22:15:03", "tom", "META", "BUY", 612.30, 5.0, "5 days left"
    )

    return test_db


@pytest.fixture
def client(db):
    """TestClient with injected test DB."""
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestHealth:
    def test_health(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestSignals:
    def test_today_signals(self, client):
        """GET /api/signals/today returns grouped signals."""
        r = client.get("/api/signals/today")
        assert r.status_code == 200
        data = r.json()
        assert "scanner_timestamp" in data
        assert "strategies" in data
        assert "rsi2" in data["strategies"]
        # V should have BUY signal
        rsi2_signals = data["strategies"]["rsi2"]["signals"]
        v_signal = next(s for s in rsi2_signals if s["symbol"] == "V")
        assert v_signal["signal"] == "BUY"

    def test_today_signals_filter_strategy(self, client):
        """Filter by strategy."""
        r = client.get("/api/signals/today?strategy=tom")
        assert r.status_code == 200
        data = r.json()
        assert "tom" in data["strategies"]
        assert "rsi2" not in data["strategies"]

    def test_signal_history(self, client):
        """GET /api/signals/history returns recent signals."""
        r = client.get("/api/signals/history?days=30")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] > 0

    def test_signal_history_filter(self, client):
        """Filter history by signal type."""
        r = client.get("/api/signals/history?signal_type=BUY")
        assert r.status_code == 200
        for sig in r.json()["signals"]:
            assert sig["signal"] == "BUY"


class TestPositions:
    def test_open_positions(self, client):
        """GET /api/positions/open returns positions with unrealized P&L."""
        r = client.get("/api/positions/open")
        assert r.status_code == 200
        data = r.json()
        assert len(data["positions"]) == 2
        # NVDA position should have current_price from signal_log
        nvda = next(p for p in data["positions"] if p["symbol"] == "NVDA")
        assert nvda["entry_price"] == 128.50
        assert "unrealized_pnl" in nvda

    def test_open_positions_filter(self, client):
        """Filter by strategy."""
        r = client.get("/api/positions/open?strategy=rsi2")
        assert r.status_code == 200
        assert len(r.json()["positions"]) == 1

    def test_closed_trades(self, client):
        """GET /api/positions/closed returns trades with P&L."""
        r = client.get("/api/positions/closed")
        assert r.status_code == 200
        data = r.json()
        assert len(data["trades"]) == 1
        assert data["trades"][0]["symbol"] == "MSFT"
        assert data["trades"][0]["pnl_dollars"] == pytest.approx(92.40, abs=0.1)


class TestPerformance:
    def test_summary(self, client):
        """GET /api/performance/summary returns stats."""
        r = client.get("/api/performance/summary")
        assert r.status_code == 200
        data = r.json()
        assert data["capital"] == 5000
        assert data["n_closed_trades"] == 1
        assert data["n_open_positions"] == 2

    def test_equity_curve(self, client):
        """GET /api/performance/equity-curve returns cumulative P&L."""
        r = client.get("/api/performance/equity-curve")
        assert r.status_code == 200
        data = r.json()
        assert len(data["data_points"]) == 1


class TestMarket:
    def test_overview(self, client):
        """GET /api/market/overview returns asset indicators."""
        r = client.get("/api/market/overview")
        assert r.status_code == 200
        data = r.json()
        assert len(data["assets"]) > 0
        # META should have signals from multiple strategies
        meta = next(a for a in data["assets"] if a["symbol"] == "META")
        assert "rsi2" in meta["strategies"] or "ibs" in meta["strategies"]


class TestBacktest:
    def test_screens_empty(self, client):
        """GET /api/backtest/screens returns empty when no data."""
        r = client.get("/api/backtest/screens")
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_validations_empty(self, client):
        """GET /api/backtest/validations returns empty when no data."""
        r = client.get("/api/backtest/validations")
        assert r.status_code == 200
        assert r.json()["total"] == 0


class TestScanner:
    def test_scanner_status(self, client):
        """GET /api/scanner/status returns running state."""
        r = client.get("/api/scanner/status")
        assert r.status_code == 200
        assert r.json()["running"] is False


class TestLive:
    def test_open_live_trade(self, client):
        r = client.post("/api/live/open", params={
            "strategy": "rsi2", "symbol": "META",
            "entry_date": "2026-03-05", "entry_price": 612.30,
            "shares": 8.0, "fees": 1.0,
        })
        assert r.status_code == 200
        assert r.json()["status"] == "created"

    def test_open_duplicate_live_trade(self, client):
        client.post("/api/live/open", params={
            "strategy": "rsi2", "symbol": "AAPL",
            "entry_date": "2026-03-05", "entry_price": 175.0,
            "shares": 28.0,
        })
        r = client.post("/api/live/open", params={
            "strategy": "rsi2", "symbol": "AAPL",
            "entry_date": "2026-03-05", "entry_price": 176.0,
            "shares": 27.0,
        })
        assert r.status_code == 409

    def test_get_open_live_trades(self, client):
        client.post("/api/live/open", params={
            "strategy": "rsi2", "symbol": "META",
            "entry_date": "2026-03-05", "entry_price": 612.30,
            "shares": 8.0,
        })
        r = client.get("/api/live/open")
        assert r.status_code == 200
        assert len(r.json()["trades"]) == 1

    def test_close_live_trade(self, client):
        client.post("/api/live/open", params={
            "strategy": "rsi2", "symbol": "META",
            "entry_date": "2026-03-05", "entry_price": 612.30,
            "shares": 8.0, "fees": 1.0,
        })
        r = client.post("/api/live/close", params={
            "strategy": "rsi2", "symbol": "META",
            "exit_date": "2026-03-08", "exit_price": 620.0,
            "fees": 1.0,
        })
        assert r.status_code == 200
        assert r.json()["status"] == "closed"

    def test_close_nonexistent_live_trade(self, client):
        r = client.post("/api/live/close", params={
            "strategy": "rsi2", "symbol": "UNKNOWN",
            "exit_date": "2026-03-08", "exit_price": 100.0,
        })
        assert r.status_code == 404

    def test_live_summary_empty(self, client):
        r = client.get("/api/live/summary")
        assert r.status_code == 200
        assert r.json()["n_trades"] == 0

    def test_delete_live_trade(self, client):
        client.post("/api/live/open", params={
            "strategy": "rsi2", "symbol": "META",
            "entry_date": "2026-03-05", "entry_price": 612.30, "shares": 8.0,
        })
        trades = client.get("/api/live/open").json()["trades"]
        r = client.delete(f"/api/live/{trades[0]['id']}")
        assert r.status_code == 200
        assert r.json()["deleted"] is True

    def test_delete_nonexistent_live_trade(self, client):
        r = client.delete("/api/live/9999")
        assert r.status_code == 404

    def test_live_compare(self, client):
        r = client.get("/api/live/compare")
        assert r.status_code == 200
        data = r.json()
        assert "paper" in data
        assert "live" in data


class TestInputValidation:
    """Tests for input validation on API endpoints."""

    def test_open_negative_price_rejected(self, client):
        r = client.post("/api/live/open", params={
            "strategy": "rsi2", "symbol": "META",
            "entry_date": "2026-03-05", "entry_price": -1.0, "shares": 8.0,
        })
        assert r.status_code == 422

    def test_open_zero_shares_rejected(self, client):
        r = client.post("/api/live/open", params={
            "strategy": "rsi2", "symbol": "META",
            "entry_date": "2026-03-05", "entry_price": 100.0, "shares": 0.0,
        })
        assert r.status_code == 422

    def test_open_negative_fees_rejected(self, client):
        r = client.post("/api/live/open", params={
            "strategy": "rsi2", "symbol": "META",
            "entry_date": "2026-03-05", "entry_price": 100.0,
            "shares": 5.0, "fees": -10.0,
        })
        assert r.status_code == 422

    def test_close_zero_price_rejected(self, client):
        client.post("/api/live/open", params={
            "strategy": "rsi2", "symbol": "META",
            "entry_date": "2026-03-05", "entry_price": 100.0, "shares": 5.0,
        })
        r = client.post("/api/live/close", params={
            "strategy": "rsi2", "symbol": "META",
            "exit_date": "2026-03-08", "exit_price": 0.0,
        })
        assert r.status_code == 422

    def test_close_negative_fees_rejected(self, client):
        client.post("/api/live/open", params={
            "strategy": "rsi2", "symbol": "META",
            "entry_date": "2026-03-05", "entry_price": 100.0, "shares": 5.0,
        })
        r = client.post("/api/live/close", params={
            "strategy": "rsi2", "symbol": "META",
            "exit_date": "2026-03-08", "exit_price": 105.0, "fees": -5.0,
        })
        assert r.status_code == 422

    def test_closed_limit_negative_rejected(self, client):
        r = client.get("/api/live/closed?limit=-1")
        assert r.status_code == 422

    def test_closed_limit_too_large_rejected(self, client):
        r = client.get("/api/live/closed?limit=5000")
        assert r.status_code == 422

    def test_positions_closed_limit_negative_rejected(self, client):
        r = client.get("/api/positions/closed?limit=-1")
        assert r.status_code == 422

    def test_scanner_status_while_not_running(self, client):
        r = client.get("/api/scanner/status")
        assert r.status_code == 200
        assert r.json()["running"] is False
