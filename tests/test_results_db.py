"""Tests pour validation/results_db.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from validation.results_db import ResultsDB


@pytest.fixture
def db(tmp_path: Path) -> ResultsDB:
    """ResultsDB avec un fichier temporaire."""
    return ResultsDB(db_path=tmp_path / "test.db")


def _screen_results() -> list[dict]:
    """Resultats de screening factices."""
    return [
        {
            "symbol": "AAPL",
            "n_trades": 90,
            "win_rate": 0.70,
            "profit_factor": 1.80,
            "sharpe": 2.5,
            "net_return_pct": 15.3,
        },
        {
            "symbol": "MSFT",
            "n_trades": 85,
            "win_rate": 0.65,
            "profit_factor": 1.45,
            "sharpe": 1.8,
            "net_return_pct": 10.1,
        },
        {
            "symbol": "GOOGL",
            "n_trades": 70,
            "win_rate": 0.55,
            "profit_factor": 0.95,
            "sharpe": 0.3,
            "net_return_pct": -2.1,
        },
    ]


class TestSaveScreen:
    """Tests pour save_screen()."""

    def test_save_screen(self, db: ResultsDB) -> None:
        db.save_screen("rsi2", "us_stocks_large", _screen_results(), timestamp="2026-03-01T00:00:00Z")
        rows = db.get_best_assets("rsi2", min_pf=0.0)
        assert len(rows) == 3

    def test_save_screen_duplicate(self, db: ResultsDB) -> None:
        ts = "2026-03-01T00:00:00Z"
        db.save_screen("rsi2", "us_stocks_large", _screen_results(), timestamp=ts)
        # Save again with same timestamp -> should replace
        db.save_screen("rsi2", "us_stocks_large", _screen_results(), timestamp=ts)
        rows = db.get_best_assets("rsi2", min_pf=0.0)
        assert len(rows) == 3


class TestGetBestAssets:
    """Tests pour get_best_assets()."""

    def test_get_best_assets_filter(self, db: ResultsDB) -> None:
        db.save_screen("rsi2", "us_stocks_large", _screen_results(), timestamp="2026-03-01T00:00:00Z")
        rows = db.get_best_assets("rsi2", min_pf=1.3)
        assert len(rows) == 2
        # Sorted by PF desc
        assert rows[0]["symbol"] == "AAPL"
        assert rows[1]["symbol"] == "MSFT"


class TestCompareStrategies:
    """Tests pour compare_strategies()."""

    def test_compare_strategies(self, db: ResultsDB) -> None:
        ts = "2026-03-01T00:00:00Z"
        db.save_screen("rsi2", "us_stocks_large", [
            {"symbol": "AAPL", "n_trades": 90, "win_rate": 0.70,
             "profit_factor": 1.80, "sharpe": 2.5, "net_return_pct": 15.3},
        ], timestamp=ts)
        db.save_screen("ibs", "us_stocks_large", [
            {"symbol": "AAPL", "n_trades": 200, "win_rate": 0.68,
             "profit_factor": 1.50, "sharpe": 2.0, "net_return_pct": 20.1},
        ], timestamp=ts)

        rows = db.compare_strategies(["rsi2", "ibs"], "us_stocks_large")
        assert len(rows) == 1
        assert rows[0]["symbol"] == "AAPL"
        assert rows[0]["rsi2_pf"] == 1.80
        assert rows[0]["ibs_pf"] == 1.50


class TestGetCrossStrategy:
    """Tests pour get_cross_strategy()."""

    def test_get_cross_strategy(self, db: ResultsDB) -> None:
        ts = "2026-03-01T00:00:00Z"
        db.save_screen("rsi2", "us_stocks_large", [
            {"symbol": "META", "n_trades": 93, "win_rate": 0.74,
             "profit_factor": 3.49, "sharpe": 6.86, "net_return_pct": 27.1},
        ], timestamp=ts)
        db.save_screen("ibs", "us_stocks_large", [
            {"symbol": "META", "n_trades": 302, "win_rate": 0.72,
             "profit_factor": 1.68, "sharpe": 2.69, "net_return_pct": 30.2},
        ], timestamp=ts)

        rows = db.get_cross_strategy("META")
        assert len(rows) == 2
        strategies = {r["strategy"] for r in rows}
        assert strategies == {"rsi2", "ibs"}


class TestEmptyDB:
    """Tests sur DB vide."""

    def test_empty_db(self, db: ResultsDB) -> None:
        assert db.get_best_assets("rsi2") == []
        assert db.compare_strategies(["rsi2"], "us_stocks_large") == []
        assert db.get_cross_strategy("META") == []
        assert db.get_strategies() == []
        assert db.get_universes() == []
        assert db.count() == 0
