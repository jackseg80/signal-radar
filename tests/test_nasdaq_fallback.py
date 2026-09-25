"""A secondary daily source is accepted only when Yahoo neighbors agree."""

from __future__ import annotations

import io
import json

import pandas as pd
import pytest

from data.db import SignalRadarDB
from data import yahoo_loader, nasdaq_fallback
from data.yahoo_loader import YahooLoader
from tests.test_strict_prices import FakeTicker, _yahoo_frame


URL = nasdaq_fallback.historical_url("META", "2026-09-21", "2026-09-23")


def _bars(previous_close: float = 102.0, next_close: float = 102.0) -> dict:
    """Return three coherent official-style Nasdaq bars."""
    return {
        "2026-09-21": {
            "open": 100.0, "high": 104.0, "low": 99.0,
            "close": previous_close, "volume": 10000.0,
        },
        "2026-09-22": {
            "open": 101.0, "high": 105.0, "low": 100.0,
            "close": 103.0, "volume": 12000.0,
        },
        "2026-09-23": {
            "open": 100.0, "high": 104.0, "low": 99.0,
            "close": next_close, "volume": 10000.0,
        },
    }


def _setup(tmp_path, monkeypatch, bars: dict | None = None) -> SignalRadarDB:
    """Isolate Yahoo cache and Nasdaq network for one missing XNYS session."""
    db = SignalRadarDB(tmp_path / "radar.db")
    monkeypatch.setattr(yahoo_loader, "_db", db)
    monkeypatch.setattr("yfinance.Ticker", FakeTicker)
    monkeypatch.setattr(
        yahoo_loader, "fetch_historical_bars",
        lambda *_: (URL, bars if bars is not None else _bars()),
    )
    FakeTicker.frame = _yahoo_frame(["2026-09-21", "2026-09-23"])
    FakeTicker.calls = 0
    return db


def test_verified_nasdaq_gap_fills_exact_session_and_audits_source(
    tmp_path, monkeypatch,
) -> None:
    """One corroborated missing day is saved in both price bases and provenance."""
    db = _setup(tmp_path, monkeypatch)
    result = YahooLoader().get_daily_candles_strict(
        "META", "2026-09-21", "2026-09-24", "2026-09-23",
    )
    assert list(result.index.strftime("%Y-%m-%d")) == [
        "2026-09-21", "2026-09-22", "2026-09-23",
    ]
    assert db.get_raw_open("META", "2026-09-22") == 101.0
    assert result.loc[pd.Timestamp("2026-09-22"), "Adj_Close"] == pytest.approx(
        103 * 101 / 102
    )
    audit = db.get_price_repair("META", "2026-09-22")
    assert audit and audit["source_url"] == URL
    assert audit["raw_close"] == 103.0
    YahooLoader().get_daily_candles_strict(
        "META", "2026-09-21", "2026-09-24", "2026-09-23",
    )
    assert FakeTicker.calls == 1


def test_nasdaq_neighbor_disagreement_blocks_all_writes(tmp_path, monkeypatch) -> None:
    """An external bar cannot hide a neighboring Yahoo/Nasdaq price conflict."""
    db = _setup(tmp_path, monkeypatch, _bars(previous_close=999.0))
    with pytest.raises(ValueError, match="neighbor disagreement"):
        YahooLoader().get_daily_candles_strict(
            "META", "2026-09-21", "2026-09-24", "2026-09-23",
        )
    assert db.get_prices_v2("META").empty
    assert db.get_price_repairs() == []


def test_corporate_action_ratio_change_blocks_fallback(tmp_path, monkeypatch) -> None:
    """A dividend or unknown adjustment between neighbors needs manual review."""
    db = _setup(tmp_path, monkeypatch)
    FakeTicker.frame.loc[pd.Timestamp("2026-09-21"), "Adj Close"] = 90.0
    with pytest.raises(ValueError, match="corporate-action adjustment"):
        YahooLoader().get_daily_candles_strict(
            "META", "2026-09-21", "2026-09-24", "2026-09-23",
        )
    assert db.get_prices_v2("META").empty


def test_no_secondary_data_keeps_gap_blocked(tmp_path, monkeypatch) -> None:
    """If both providers lack a verified bar, do not synthesize one."""
    db = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(
        yahoo_loader, "fetch_historical_bars",
        lambda *_: (_ for _ in ()).throw(OSError("offline")),
    )
    with pytest.raises(ValueError, match="missing XNYS bar 2026-09-22"):
        YahooLoader().get_daily_candles_strict(
            "META", "2026-09-21", "2026-09-24", "2026-09-23",
        )
    assert db.get_prices_v2("META").empty


def test_later_yahoo_conflict_with_audited_nasdaq_bar_blocks(tmp_path, monkeypatch) -> None:
    """A provider correction is reviewed before replacing an accepted quote."""
    db = _setup(tmp_path, monkeypatch)
    YahooLoader().get_daily_candles_strict(
        "META", "2026-09-21", "2026-09-24", "2026-09-23",
    )
    FakeTicker.frame = _yahoo_frame(
        ["2026-09-21", "2026-09-22", "2026-09-23", "2026-09-24"],
    )
    FakeTicker.frame.loc[pd.Timestamp("2026-09-22"), "Close"] = 110.0
    with pytest.raises(ValueError, match="repaired close conflict"):
        YahooLoader().get_daily_candles_strict(
            "META", "2026-09-21", "2026-09-25", "2026-09-24",
        )
    assert db.get_raw_open("META", "2026-09-22") == 101.0


def test_fallback_recovers_pre_split_execution_price(tmp_path, monkeypatch) -> None:
    """A later split must not make Nasdaq's original opening price double."""
    db = _setup(tmp_path, monkeypatch)
    frame = _yahoo_frame(["2026-09-21", "2026-09-23"])
    frame.loc[pd.Timestamp("2026-09-21"), [
        "Open", "High", "Low", "Close", "Adj Close",
    ]] = [50.0, 52.0, 49.0, 50.0, 50.0]
    frame.loc[pd.Timestamp("2026-09-23"), [
        "Open", "High", "Low", "Close", "Adj Close", "Stock Splits",
    ]] = [102.0, 104.0, 101.0, 102.0, 102.0, 2.0]
    FakeTicker.frame = frame
    bars = _bars(previous_close=100.0)
    bars["2026-09-22"] = {
        "open": 101.0, "high": 103.0, "low": 99.0,
        "close": 101.0, "volume": 12000.0,
    }
    monkeypatch.setattr(
        yahoo_loader, "fetch_historical_bars", lambda *_: (URL, bars),
    )
    result = YahooLoader().get_daily_candles_strict(
        "META", "2026-09-21", "2026-09-24", "2026-09-23",
    )
    assert db.get_raw_open("META", "2026-09-21") == 100.0
    assert db.get_raw_open("META", "2026-09-22") == 101.0
    assert result.loc[pd.Timestamp("2026-09-22"), "Adj_Close"] == 50.5


def test_nasdaq_parser_rejects_impossible_ohlc(monkeypatch) -> None:
    """The official endpoint response still receives local validation."""
    payload = {
        "status": {"rCode": 200},
        "data": {"tradesTable": {"rows": [{
            "date": "09/22/2026", "open": "$100", "high": "$99",
            "low": "$98", "close": "$100", "volume": "1,000",
        }]}},
    }
    monkeypatch.setattr(
        nasdaq_fallback, "urlopen",
        lambda *_args, **_kwargs: io.BytesIO(json.dumps(payload).encode()),
    )
    with pytest.raises(ValueError, match="Impossible Nasdaq OHLC"):
        nasdaq_fallback.fetch_historical_bars(
            "META", "2026-09-21", "2026-09-23",
        )


def test_approved_bar_survives_nasdaq_outage(tmp_path, monkeypatch) -> None:
    """A previously verified September 22 quote remains usable offline."""
    db = SignalRadarDB(tmp_path / "radar.db")
    monkeypatch.setattr(yahoo_loader, "_db", db)
    monkeypatch.setattr("yfinance.Ticker", FakeTicker)
    frame = _yahoo_frame(["2026-09-21", "2026-09-23"])
    frame.loc[pd.Timestamp("2026-09-21"), [
        "Open", "High", "Low", "Close", "Adj Close",
    ]] = [891.07, 899.44, 885.50, 898.48, 898.48]
    frame.loc[pd.Timestamp("2026-09-23"), [
        "Open", "High", "Low", "Close", "Adj Close",
    ]] = [901.31, 905.59, 893.36, 904.70, 904.70]
    FakeTicker.frame = frame
    monkeypatch.setattr(
        yahoo_loader, "fetch_historical_bars",
        lambda *_: (_ for _ in ()).throw(OSError("offline")),
    )
    result = YahooLoader().get_daily_candles_strict(
        "COST", "2026-09-21", "2026-09-24", "2026-09-23",
    )
    assert result.loc[pd.Timestamp("2026-09-22"), "Open"] == 902.255
    assert db.get_price_repair("COST", "2026-09-22")["source_url"].startswith(
        "https://api.nasdaq.com/"
    )
