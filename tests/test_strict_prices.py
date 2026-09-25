"""Exact-session Yahoo ingestion and raw/adjusted price separation."""

from __future__ import annotations

import sqlite3
import pandas as pd
import pytest

from data.db import SignalRadarDB
from data.yahoo_loader import YahooLoader
from data import yahoo_loader


def _yahoo_frame(dates: list[str]) -> pd.DataFrame:
    """Make a small Yahoo-style frame with different raw and adjusted OHLC."""
    return pd.DataFrame({
        "Open": [100.0] * len(dates),
        "High": [104.0] * len(dates),
        "Low": [99.0] * len(dates),
        "Close": [102.0] * len(dates),
        "Adj Close": [101.0] * len(dates),
        "Volume": [10000.0] * len(dates),
        "Dividends": [0.0] * len(dates),
        "Stock Splits": [0.0] * len(dates),
    }, index=pd.to_datetime(dates))


class FakeTicker:
    """Return the prepared history and count refresh calls."""

    frame: pd.DataFrame
    calls = 0

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol

    def history(self, **kwargs) -> pd.DataFrame:
        FakeTicker.calls += 1
        return FakeTicker.frame.copy()


def test_old_cache_is_refreshed_and_raw_open_is_preserved(tmp_path, monkeypatch) -> None:
    """A legacy cache cannot satisfy a strict next-open scan."""
    db = SignalRadarDB(tmp_path / "radar.db")
    old = pd.DataFrame({
        "Open": [90.0], "High": [92.0], "Low": [89.0],
        "Close": [91.0], "Volume": [1000],
    }, index=[pd.Timestamp("2026-09-21")])
    db.save_ohlcv("META", old)
    monkeypatch.setattr(yahoo_loader, "_db", db)
    monkeypatch.setattr("yfinance.Ticker", FakeTicker)
    FakeTicker.frame = _yahoo_frame(["2026-09-22", "2026-09-23"])
    FakeTicker.calls = 0

    result = YahooLoader().get_daily_candles_strict(
        "META", "2026-09-22", "2026-09-24", "2026-09-23",
    )
    assert FakeTicker.calls == 1
    assert result["Open"].iloc[-1] == 100.0
    assert result["Adj_Open"].iloc[-1] == pytest.approx(100 * 101 / 102)
    assert db.get_raw_open("META", "2026-09-23") == 100.0
    YahooLoader().get_daily_candles_strict(
        "META", "2026-09-22", "2026-09-24", "2026-09-23",
    )
    assert FakeTicker.calls == 1  # complete verified v2 cache is reusable


@pytest.mark.parametrize("dates", [
    ["2026-09-21", "2026-09-22"],  # final bar absent
    ["2026-09-21", "2026-09-23"],  # internal XNYS bar absent
    ["2026-09-22", "2026-09-22", "2026-09-23"],  # duplicate
])
def test_missing_or_duplicate_bar_blocks_scan(tmp_path, monkeypatch, dates) -> None:
    """No partial Yahoo result is silently accepted."""
    monkeypatch.setattr(yahoo_loader, "_db", SignalRadarDB(tmp_path / "radar.db"))
    monkeypatch.setattr("yfinance.Ticker", FakeTicker)
    monkeypatch.setattr(
        yahoo_loader, "fetch_historical_bars",
        lambda *_: (_ for _ in ()).throw(OSError("source unavailable")),
    )
    FakeTicker.frame = _yahoo_frame(dates)
    with pytest.raises(ValueError):
        YahooLoader().get_daily_candles_strict(
            "META", "2026-09-21", "2026-09-24", "2026-09-23",
        )


def test_adjusted_ohlc_allows_only_roundoff(tmp_path, monkeypatch) -> None:
    """One-ulp adjusted-close noise is accepted; a real bad bar is rejected."""
    monkeypatch.setattr(yahoo_loader, "_db", SignalRadarDB(tmp_path / "radar.db"))
    frame = _yahoo_frame(["2026-09-22", "2026-09-23"])
    frame["High"] = frame["Close"]
    ratio = frame["Adj Close"] / frame["Close"]
    adjusted = frame.rename(columns={"Adj Close": "Adj_Close"}).copy()
    for field in ("Open", "High", "Low"):
        adjusted[f"Adj_{field}"] = adjusted[field] * ratio
    adjusted.loc[pd.Timestamp("2026-09-23"), "Adj_Close"] += 1e-12
    YahooLoader._validate_strict(adjusted, "META", "2026-09-23")
    adjusted.loc[pd.Timestamp("2026-09-23"), "Adj_Close"] += 0.01
    with pytest.raises(ValueError, match="impossible Adj_OHLC"):
        YahooLoader._validate_strict(adjusted, "META", "2026-09-23")


def test_split_adjusted_yahoo_history_recovers_tradeable_pre_split_prices(
    tmp_path, monkeypatch,
) -> None:
    """A historical split changes share count once, at the ex-date only."""
    db = SignalRadarDB(tmp_path / "radar.db")
    monkeypatch.setattr(yahoo_loader, "_db", db)
    monkeypatch.setattr("yfinance.Ticker", FakeTicker)
    frame = _yahoo_frame(["2022-06-03", "2022-06-06"])
    frame.loc[pd.Timestamp("2022-06-03"), "Dividends"] = 0.5
    frame.loc[pd.Timestamp("2022-06-06"), "Stock Splits"] = 2.0
    FakeTicker.frame = frame
    FakeTicker.calls = 0

    result = YahooLoader().get_daily_candles_strict(
        "AMZN", "2022-06-03", "2022-06-07", "2022-06-06",
    )
    assert result["Open"].tolist() == [200.0, 100.0]
    assert result["Adj_Open"].tolist() == pytest.approx([100 * 101 / 102] * 2)
    assert result["Dividends"].tolist() == [1.0, 0.0]
    assert db.get_raw_open("AMZN", "2022-06-03") == 200.0
    assert db.get_raw_open("AMZN", "2022-06-06") == 100.0

    YahooLoader().get_daily_candles_strict(
        "AMZN", "2022-06-03", "2022-06-07", "2022-06-06",
    )
    assert FakeTicker.calls == 1
    with db._connect() as conn:
        conn.execute(
            "UPDATE prices_v2 SET price_basis_version=1 WHERE symbol='AMZN'"
        )
    assert db.get_raw_open("AMZN", "2022-06-03") is None
    YahooLoader().get_daily_candles_strict(
        "AMZN", "2022-06-03", "2022-06-07", "2022-06-06",
    )
    assert FakeTicker.calls == 2
    assert db.get_raw_open("AMZN", "2022-06-03") == 200.0

def test_price_basis_migration_backups_old_schema_before_alter(tmp_path) -> None:
    """Keep an exact SQLite copy before old split-adjusted rows are marked stale."""
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as conn:
        conn.execute("""CREATE TABLE prices_v2 (
            symbol TEXT NOT NULL, date TEXT NOT NULL,
            raw_open REAL NOT NULL, raw_high REAL NOT NULL,
            raw_low REAL NOT NULL, raw_close REAL NOT NULL,
            adj_open REAL NOT NULL, adj_high REAL NOT NULL,
            adj_low REAL NOT NULL, adj_close REAL NOT NULL,
            volume REAL NOT NULL, dividend REAL NOT NULL DEFAULT 0,
            split REAL NOT NULL DEFAULT 0, PRIMARY KEY(symbol, date)
        )""")
        conn.execute(
            "INSERT INTO prices_v2 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("AMZN", "2022-06-03", 100, 104, 99, 102,
             100, 104, 99, 102, 10000, 0, 0),
        )
    db = SignalRadarDB(path)
    backup = path.with_suffix(path.suffix + ".pre-price-basis.bak")
    assert backup.exists()
    with sqlite3.connect(backup) as old:
        assert "price_basis_version" not in {
            row[1] for row in old.execute("PRAGMA table_info(prices_v2)")
        }
    with db._connect() as current:
        assert current.execute(
            "SELECT price_basis_version FROM prices_v2"
        ).fetchone()[0] == 1
    assert db.get_raw_open("AMZN", "2022-06-03") is None