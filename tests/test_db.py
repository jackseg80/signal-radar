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


# ------------------------------------------------------------------ #
# PAPER TRADING
# ------------------------------------------------------------------ #


class TestPaperPositions:
    """Tests pour paper trading positions."""

    def test_open_paper_position(self, db: SignalRadarDB) -> None:
        opened = db.open_paper_position("rsi2", "META", "2026-03-01", 612.30, 8.0)
        assert opened is True
        positions = db.get_open_positions()
        assert len(positions) == 1
        assert positions[0]["symbol"] == "META"
        assert positions[0]["strategy"] == "rsi2"
        assert positions[0]["shares"] == 8.0
        assert positions[0]["status"] == "open"

    def test_close_paper_position(self, db: SignalRadarDB) -> None:
        db.open_paper_position("rsi2", "META", "2026-03-01", 612.30, 8.0)
        trade = db.close_paper_position("rsi2", "META", "2026-03-04", 620.00)
        assert trade is not None
        assert trade["symbol"] == "META"
        assert trade["entry_price"] == 612.30
        assert trade["exit_price"] == 620.00
        assert trade["shares"] == 8.0
        # PnL = (620 - 612.30) * 8 = 61.60
        assert trade["pnl_dollars"] == pytest.approx(61.60, abs=0.01)
        # Pct = (620 - 612.30) / 612.30 * 100 = 1.257%
        assert trade["pnl_pct"] == pytest.approx(1.26, abs=0.1)
        # Position should now be closed
        assert db.get_open_positions() == []

    def test_close_nonexistent_position(self, db: SignalRadarDB) -> None:
        result = db.close_paper_position("rsi2", "META", "2026-03-04", 620.00)
        assert result is None

    def test_duplicate_position_rejected(self, db: SignalRadarDB) -> None:
        db.open_paper_position("rsi2", "META", "2026-03-01", 612.30, 8.0)
        opened = db.open_paper_position("rsi2", "META", "2026-03-02", 615.00, 7.0)
        assert opened is False
        # Only original position exists
        positions = db.get_open_positions()
        assert len(positions) == 1
        assert positions[0]["entry_price"] == 612.30

    def test_different_strategies_same_symbol(self, db: SignalRadarDB) -> None:
        """Can have positions on same symbol from different strategies."""
        db.open_paper_position("rsi2", "META", "2026-03-01", 612.30, 8.0)
        opened = db.open_paper_position("ibs", "META", "2026-03-01", 612.30, 8.0)
        assert opened is True
        positions = db.get_open_positions()
        assert len(positions) == 2

    def test_get_open_positions_by_strategy(self, db: SignalRadarDB) -> None:
        db.open_paper_position("rsi2", "META", "2026-03-01", 612.30, 8.0)
        db.open_paper_position("ibs", "NVDA", "2026-03-01", 130.00, 38.0)
        rsi2_pos = db.get_open_positions(strategy="rsi2")
        assert len(rsi2_pos) == 1
        assert rsi2_pos[0]["symbol"] == "META"

    def test_get_closed_trades(self, db: SignalRadarDB) -> None:
        db.open_paper_position("rsi2", "META", "2026-03-01", 100.0, 10.0)
        db.close_paper_position("rsi2", "META", "2026-03-04", 110.0)
        trades = db.get_closed_trades()
        assert len(trades) == 1
        assert trades[0]["pnl_dollars"] == 100.0

    def test_paper_summary(self, db: SignalRadarDB) -> None:
        # Trade 1: win (+100)
        db.open_paper_position("rsi2", "META", "2026-03-01", 100.0, 10.0)
        db.close_paper_position("rsi2", "META", "2026-03-04", 110.0)
        # Trade 2: loss (-25)
        db.open_paper_position("ibs", "NVDA", "2026-03-02", 130.0, 5.0)
        db.close_paper_position("ibs", "NVDA", "2026-03-05", 125.0)
        # Trade 3: open (not counted in summary)
        db.open_paper_position("tom", "AAPL", "2026-03-03", 175.0, 28.0)

        summary = db.get_paper_summary()
        assert summary["n_trades"] == 2
        assert summary["n_wins"] == 1
        assert summary["win_rate"] == 50.0
        assert summary["total_pnl"] == pytest.approx(75.0, abs=0.01)
        assert summary["n_open"] == 1
        assert "rsi2" in summary["by_strategy"]
        assert summary["by_strategy"]["rsi2"]["pnl"] == 100.0
        assert summary["by_strategy"]["ibs"]["pnl"] == -25.0

    def test_paper_summary_empty(self, db: SignalRadarDB) -> None:
        summary = db.get_paper_summary()
        assert summary["n_trades"] == 0
        assert summary["win_rate"] == 0.0
        assert summary["total_pnl"] == 0.0
        assert summary["n_open"] == 0


class TestClearPaperPositions:
    """Tests pour clear_paper_positions."""

    def test_clear_all_open(self, db: SignalRadarDB) -> None:
        db.open_paper_position("rsi2", "META", "2026-03-01", 612.30, 8.0)
        db.open_paper_position("ibs", "NVDA", "2026-03-01", 130.00, 38.0)
        db.open_paper_position("tom", "AAPL", "2026-03-01", 175.00, 28.0)
        n = db.clear_paper_positions()
        assert n == 3
        assert db.get_open_positions() == []

    def test_clear_by_strategy(self, db: SignalRadarDB) -> None:
        db.open_paper_position("rsi2", "META", "2026-03-01", 612.30, 8.0)
        db.open_paper_position("tom", "AAPL", "2026-03-01", 175.00, 28.0)
        db.open_paper_position("tom", "NVDA", "2026-03-01", 130.00, 38.0)
        n = db.clear_paper_positions(strategy="tom")
        assert n == 2
        remaining = db.get_open_positions()
        assert len(remaining) == 1
        assert remaining[0]["strategy"] == "rsi2"

    def test_clear_preserves_closed(self, db: SignalRadarDB) -> None:
        """Closed trades should NOT be deleted."""
        db.open_paper_position("rsi2", "META", "2026-03-01", 100.0, 10.0)
        db.close_paper_position("rsi2", "META", "2026-03-04", 110.0)
        db.open_paper_position("rsi2", "NVDA", "2026-03-01", 130.0, 5.0)
        n = db.clear_paper_positions()
        assert n == 1  # only open NVDA cleared
        trades = db.get_closed_trades()
        assert len(trades) == 1  # closed META preserved
        assert trades[0]["symbol"] == "META"

    def test_clear_empty(self, db: SignalRadarDB) -> None:
        n = db.clear_paper_positions()
        assert n == 0


class TestSignalLog:
    """Tests pour signal_log."""

    def test_log_signal(self, db: SignalRadarDB) -> None:
        db.log_signal(
            "2026-03-01 22:00:00", "rsi2", "META", "BUY",
            612.30, 4.5, "RSI low",
        )
        # Verify it was written (query directly)
        import sqlite3
        with sqlite3.connect(db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM signal_log").fetchall()
        assert len(rows) == 1
        assert rows[0]["strategy"] == "rsi2"
        assert rows[0]["signal"] == "BUY"

    def test_log_multiple_signals(self, db: SignalRadarDB) -> None:
        db.log_signal("2026-03-01 22:00:00", "rsi2", "META", "BUY", 612.0, 4.5, "")
        db.log_signal("2026-03-01 22:00:00", "ibs", "META", "NO_SIGNAL", 612.0, 0.6, "")
        db.log_signal("2026-03-01 22:00:00", "tom", "META", "BUY", 612.0, 5.0, "")
        import sqlite3
        with sqlite3.connect(db.db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM signal_log").fetchone()[0]
        assert count == 3


class TestAPIDBMethods:
    """Tests pour les methodes DB utilisees par l'API."""

    def test_get_latest_signals_empty(self, db: SignalRadarDB) -> None:
        ts, signals = db.get_latest_signals()
        assert ts is None
        assert signals == []

    def test_get_latest_signals(self, db: SignalRadarDB) -> None:
        db.log_signal("2026-03-04 22:15:00", "rsi2", "META", "BUY", 600.0, 4.5, "")
        db.log_signal("2026-03-04 22:15:00", "ibs", "META", "NO_SIGNAL", 600.0, 0.6, "")
        db.log_signal("2026-03-05 22:15:00", "rsi2", "META", "SELL", 610.0, 55.0, "")
        db.log_signal("2026-03-05 22:15:00", "ibs", "NVDA", "BUY", 130.0, 0.1, "")

        ts, signals = db.get_latest_signals()
        assert ts == "2026-03-05 22:15:00"
        assert len(signals) == 2

    def test_get_latest_signals_filter(self, db: SignalRadarDB) -> None:
        db.log_signal("2026-03-05 22:15:00", "rsi2", "META", "SELL", 610.0, 55.0, "")
        db.log_signal("2026-03-05 22:15:00", "ibs", "NVDA", "BUY", 130.0, 0.1, "")

        ts, signals = db.get_latest_signals(strategy="rsi2")
        assert len(signals) == 1
        assert signals[0]["strategy"] == "rsi2"

    def test_get_latest_price(self, db: SignalRadarDB) -> None:
        db.log_signal("2026-03-04 22:15:00", "rsi2", "META", "BUY", 600.0, 4.5, "")
        db.log_signal("2026-03-05 22:15:00", "rsi2", "META", "SELL", 610.0, 55.0, "")
        assert db.get_latest_price("META") == 610.0
        assert db.get_latest_price("UNKNOWN") is None

    def test_get_latest_prices(self, db: SignalRadarDB) -> None:
        db.log_signal("2026-03-05 22:15:00", "rsi2", "META", "SELL", 610.0, 55.0, "")
        db.log_signal("2026-03-05 22:15:00", "rsi2", "NVDA", "BUY", 130.0, 4.0, "")

        prices = db.get_latest_prices(["META", "NVDA", "UNKNOWN"])
        assert prices["META"] == 610.0
        assert prices["NVDA"] == 130.0
        assert "UNKNOWN" not in prices

    def test_get_signal_history(self, db: SignalRadarDB) -> None:
        db.log_signal("2026-03-05 22:15:00", "rsi2", "META", "BUY", 610.0, 4.5, "")
        db.log_signal("2026-03-05 22:15:00", "ibs", "META", "NO_SIGNAL", 610.0, 0.6, "")

        all_sigs = db.get_signal_history(days=30)
        assert len(all_sigs) == 2

        buys = db.get_signal_history(signal_type="BUY", days=30)
        assert len(buys) == 1
        assert buys[0]["signal"] == "BUY"

    def test_get_screens_filtered(self, db: SignalRadarDB) -> None:
        results = db.get_screens_filtered(min_pf=1.0)
        assert isinstance(results, list)

    def test_get_screens_filtered_dedup(self, db: SignalRadarDB) -> None:
        """Multiple runs of same screen should return only the latest."""
        import sqlite3 as _sqlite3

        with _sqlite3.connect(db.db_path) as conn:
            conn.execute(
                "INSERT INTO screens (timestamp, strategy, universe, symbol, "
                "n_trades, win_rate, profit_factor, sharpe, net_return_pct) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("2026-03-01 10:00:00", "rsi2", "us_stocks_large", "META",
                 90, 73.0, 3.40, 6.5, 150.0),
            )
            conn.execute(
                "INSERT INTO screens (timestamp, strategy, universe, symbol, "
                "n_trades, win_rate, profit_factor, sharpe, net_return_pct) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("2026-03-02 10:00:00", "rsi2", "us_stocks_large", "META",
                 93, 74.2, 3.49, 6.86, 160.0),
            )

        results = db.get_screens_filtered()
        meta = [r for r in results if r["symbol"] == "META" and r["strategy"] == "rsi2"]
        assert len(meta) == 1
        assert meta[0]["profit_factor"] == 3.49  # latest run

    def test_get_validations_filtered(self, db: SignalRadarDB) -> None:
        results = db.get_validations_filtered()
        assert isinstance(results, list)

    def test_get_validations_filtered_dedup(self, db: SignalRadarDB) -> None:
        """Multiple runs of same validation should return only the latest."""
        import sqlite3 as _sqlite3

        with _sqlite3.connect(db.db_path) as conn:
            conn.execute(
                "INSERT INTO validations (timestamp, strategy, universe, symbol, "
                "n_trades, win_rate, profit_factor, sharpe, net_return_pct, "
                "robustness_pct, stable, ttest_p, verdict) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("2026-03-01 10:00:00", "rsi2", "us_stocks_large", "NVDA",
                 90, 67.0, 1.40, 0.5, 80.0, 100.0, 1, 0.001, "VALIDATED"),
            )
            conn.execute(
                "INSERT INTO validations (timestamp, strategy, universe, symbol, "
                "n_trades, win_rate, profit_factor, sharpe, net_return_pct, "
                "robustness_pct, stable, ttest_p, verdict) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("2026-03-02 10:00:00", "rsi2", "us_stocks_large", "NVDA",
                 96, 67.5, 1.48, 0.55, 85.0, 100.0, 1, 0.0005, "VALIDATED"),
            )

        results = db.get_validations_filtered()
        nvda = [r for r in results if r["symbol"] == "NVDA" and r["strategy"] == "rsi2"]
        assert len(nvda) == 1
        assert nvda[0]["profit_factor"] == 1.48  # latest run


# ------------------------------------------------------------------ #
# LIVE TRADES
# ------------------------------------------------------------------ #


class TestLiveTrades:
    """Tests pour live trades."""

    def test_open_live_trade(self, db: SignalRadarDB) -> None:
        opened = db.open_live_trade("rsi2", "META", "2026-03-05", 612.30, 8.0, fees=1.0)
        assert opened is True
        trades = db.get_open_live_trades()
        assert len(trades) == 1
        assert trades[0]["entry_price"] == 612.30
        assert trades[0]["fees_entry"] == 1.0

    def test_close_live_trade(self, db: SignalRadarDB) -> None:
        db.open_live_trade("rsi2", "META", "2026-03-05", 612.30, 8.0, fees=1.0)
        trade = db.close_live_trade("rsi2", "META", "2026-03-08", 620.00, fees=1.0)
        assert trade is not None
        # PnL = (620 - 612.30) * 8 - 1.0 - 1.0 = 59.60
        assert trade["pnl_dollars"] == pytest.approx(59.60, abs=0.1)

    def test_close_nonexistent_live_trade(self, db: SignalRadarDB) -> None:
        result = db.close_live_trade("rsi2", "META", "2026-03-08", 620.00)
        assert result is None

    def test_duplicate_live_trade_rejected(self, db: SignalRadarDB) -> None:
        db.open_live_trade("rsi2", "META", "2026-03-05", 612.30, 8.0)
        opened = db.open_live_trade("rsi2", "META", "2026-03-05", 615.00, 7.0)
        assert opened is False

    def test_live_summary(self, db: SignalRadarDB) -> None:
        db.open_live_trade("rsi2", "META", "2026-03-05", 100.0, 10.0, fees=1.0)
        db.close_live_trade("rsi2", "META", "2026-03-08", 110.0, fees=1.0)
        summary = db.get_live_summary()
        assert summary["n_trades"] == 1
        # PnL = (110-100)*10 - 1 - 1 = 98.0
        assert summary["total_pnl"] == pytest.approx(98.0, abs=0.1)

    def test_live_summary_empty(self, db: SignalRadarDB) -> None:
        summary = db.get_live_summary()
        assert summary["n_trades"] == 0
        assert summary["win_rate"] == 0.0
        assert summary["total_pnl"] == 0.0

    def test_get_closed_live_trades(self, db: SignalRadarDB) -> None:
        db.open_live_trade("rsi2", "META", "2026-03-05", 100.0, 10.0)
        db.close_live_trade("rsi2", "META", "2026-03-08", 110.0)
        trades = db.get_closed_live_trades()
        assert len(trades) == 1
        assert trades[0]["symbol"] == "META"

    def test_delete_live_trade(self, db: SignalRadarDB) -> None:
        db.open_live_trade("rsi2", "META", "2026-03-05", 612.30, 8.0)
        trades = db.get_open_live_trades()
        assert len(trades) == 1
        deleted = db.delete_live_trade(trades[0]["id"])
        assert deleted is True
        assert db.get_open_live_trades() == []

    def test_delete_nonexistent_live_trade(self, db: SignalRadarDB) -> None:
        assert db.delete_live_trade(9999) is False

    def test_paper_position_id_link(self, db: SignalRadarDB) -> None:
        db.open_live_trade(
            "rsi2", "META", "2026-03-05", 612.30, 8.0,
            paper_position_id=42,
        )
        trades = db.get_open_live_trades()
        assert trades[0]["paper_position_id"] == 42
