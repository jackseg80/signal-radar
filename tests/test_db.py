"""Tests pour data/db.py -- SignalRadarDB (base SQLite unique)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from data.db import SignalRadarDB


@pytest.fixture
def db(tmp_path: Path) -> SignalRadarDB:
    """SignalRadarDB avec un fichier temporaire."""
    return SignalRadarDB(db_path=tmp_path / "test.db")


def _make_ohlcv(n: int = 100, start: str = "2020-01-01") -> pd.DataFrame:
    """Cree un DataFrame OHLCV factice."""
    dates = pd.bdate_range(start, periods=n)
    rng = np.random.default_rng(42)
    close = 100.0 + rng.standard_normal(n).cumsum()
    return pd.DataFrame(
        {
            "Open": close - 0.5,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
            "Adj_Close": close,
            "Volume": rng.integers(1_000_000, 10_000_000, size=n).astype(float),
        },
        index=dates,
    )


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


# ------------------------------------------------------------------ #
# OHLCV
# ------------------------------------------------------------------ #


class TestSaveAndGetOHLCV:
    """Tests pour save_ohlcv / get_ohlcv."""

    def test_save_and_get_ohlcv(self, db: SignalRadarDB) -> None:
        df = _make_ohlcv(50)
        db.save_ohlcv("AAPL", df)
        result = db.get_ohlcv("AAPL")
        assert len(result) == 50
        # Colonnes attendues
        assert list(result.columns) == ["Open", "High", "Low", "Close", "Volume", "Adj_Close"]
        # Adj_Close == Close (donnees deja ajustees)
        assert (result["Adj_Close"] == result["Close"]).all()
        # Valeurs preservees
        np.testing.assert_allclose(result["Close"].values, df["Close"].values, rtol=1e-10)

    def test_has_ohlcv_false(self, db: SignalRadarDB) -> None:
        assert db.has_ohlcv("AAPL") is False

    def test_has_ohlcv_true(self, db: SignalRadarDB) -> None:
        db.save_ohlcv("AAPL", _make_ohlcv())
        assert db.has_ohlcv("AAPL") is True

    def test_ohlcv_date_range(self, db: SignalRadarDB) -> None:
        df = _make_ohlcv(50, "2022-01-03")
        db.save_ohlcv("MSFT", df)
        date_range = db.ohlcv_date_range("MSFT")
        assert date_range is not None
        assert date_range[0] == "2022-01-03"
        # La fin depend du nombre de jours ouvrables
        assert date_range[1] > "2022-01-03"

    def test_ohlcv_date_range_absent(self, db: SignalRadarDB) -> None:
        assert db.ohlcv_date_range("AAPL") is None

    def test_ohlcv_date_filter(self, db: SignalRadarDB) -> None:
        df = _make_ohlcv(200, "2020-01-01")
        db.save_ohlcv("AAPL", df)
        filtered = db.get_ohlcv("AAPL", start="2020-06-01", end="2020-08-01")
        assert len(filtered) > 0
        assert str(filtered.index.min().date()) >= "2020-06-01"
        assert str(filtered.index.max().date()) <= "2020-08-01"


class TestListAssets:
    """Tests pour list_assets."""

    def test_list_assets(self, db: SignalRadarDB) -> None:
        db.save_ohlcv("AAPL", _make_ohlcv(50, "2022-01-03"))
        db.save_ohlcv("MSFT", _make_ohlcv(30, "2023-01-02"))
        assets = db.list_assets()
        assert len(assets) == 2
        symbols = [a["symbol"] for a in assets]
        assert "AAPL" in symbols
        assert "MSFT" in symbols
        aapl = next(a for a in assets if a["symbol"] == "AAPL")
        assert aapl["rows"] == 50

    def test_list_assets_empty(self, db: SignalRadarDB) -> None:
        assert db.list_assets() == []


class TestClearOHLCV:
    """Tests pour clear_ohlcv."""

    def test_clear_specific(self, db: SignalRadarDB) -> None:
        df = _make_ohlcv()
        db.save_ohlcv("AAPL", df)
        db.save_ohlcv("MSFT", df)
        db.clear_ohlcv("AAPL")
        assert not db.has_ohlcv("AAPL")
        assert db.has_ohlcv("MSFT")

    def test_clear_all(self, db: SignalRadarDB) -> None:
        df = _make_ohlcv()
        for sym in ["AAPL", "MSFT", "GOOGL"]:
            db.save_ohlcv(sym, df)
        db.clear_ohlcv()
        assert db.list_assets() == []


# ------------------------------------------------------------------ #
# SCREENS
# ------------------------------------------------------------------ #


class TestSaveScreen:
    """Tests pour save_screen."""

    def test_save_screen(self, db: SignalRadarDB) -> None:
        db.save_screen("rsi2", "us_stocks_large", _screen_results(), timestamp="2026-03-01T00:00:00Z")
        rows = db.get_best_assets("rsi2", min_pf=0.0)
        assert len(rows) == 3

    def test_save_screen_duplicate(self, db: SignalRadarDB) -> None:
        ts = "2026-03-01T00:00:00Z"
        db.save_screen("rsi2", "us_stocks_large", _screen_results(), timestamp=ts)
        db.save_screen("rsi2", "us_stocks_large", _screen_results(), timestamp=ts)
        rows = db.get_best_assets("rsi2", min_pf=0.0)
        assert len(rows) == 3


class TestGetBestAssets:
    """Tests pour get_best_assets."""

    def test_get_best_assets_filter(self, db: SignalRadarDB) -> None:
        db.save_screen("rsi2", "us_stocks_large", _screen_results(), timestamp="2026-03-01T00:00:00Z")
        rows = db.get_best_assets("rsi2", min_pf=1.3)
        assert len(rows) == 2
        assert rows[0]["symbol"] == "AAPL"
        assert rows[1]["symbol"] == "MSFT"


class TestCompareStrategies:
    """Tests pour compare_strategies."""

    def test_compare_strategies(self, db: SignalRadarDB) -> None:
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
    """Tests pour get_cross_strategy."""

    def test_get_cross_strategy(self, db: SignalRadarDB) -> None:
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


# ------------------------------------------------------------------ #
# SUMMARY + EMPTY
# ------------------------------------------------------------------ #


class TestEmptyDB:
    """Tests sur DB vide."""

    def test_empty_db(self, db: SignalRadarDB) -> None:
        assert db.get_best_assets("rsi2") == []
        assert db.compare_strategies(["rsi2"], "us_stocks_large") == []
        assert db.get_cross_strategy("META") == []
        assert db.get_strategies() == []
        assert db.get_universes() == []
        assert db.count() == 0
        assert db.list_assets() == []
        assert db.has_ohlcv("AAPL") is False
