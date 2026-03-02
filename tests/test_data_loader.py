"""Tests pour data/yahoo_loader.py.

NOTE: Ces tests nécessitent un accès réseau pour yfinance.
Utilisez pytest -m "not network" pour les skipper.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from data.yahoo_loader import YahooLoader


def _make_fake_df(
    n: int = 100,
    start: str = "2020-01-02",
    symbol: str = "TEST",
) -> pd.DataFrame:
    """Crée un DataFrame OHLCV synthétique valide."""
    dates = pd.bdate_range(start=start, periods=n, freq="B")
    rng = np.random.default_rng(42)
    closes = 100 + np.cumsum(rng.standard_normal(n) * 0.5)
    opens = closes + rng.standard_normal(n) * 0.2
    highs = np.maximum(opens, closes) + rng.uniform(0.1, 1.0, n)
    lows = np.minimum(opens, closes) - rng.uniform(0.1, 1.0, n)
    volumes = rng.uniform(1e6, 5e6, n)
    df = pd.DataFrame(
        {
            "Open": opens,
            "High": highs,
            "Low": lows,
            "Close": closes,
            "Adj Close": closes,  # No adjustments
            "Volume": volumes,
        },
        index=dates,
    )
    return df


class TestYahooLoaderValidation:
    """Tests pour la validation des données."""

    def test_valid_df_passes(self):
        df = _make_fake_df()
        df.rename(columns={"Adj Close": "Adj_Close"}, inplace=True)
        YahooLoader._validate(df, "TEST")

    def test_high_lt_low_raises(self):
        df = _make_fake_df()
        df.rename(columns={"Adj Close": "Adj_Close"}, inplace=True)
        df.iloc[5, df.columns.get_loc("High")] = df.iloc[5]["Low"] - 1
        with pytest.raises(ValueError, match="High < Low"):
            YahooLoader._validate(df, "TEST")

    def test_negative_price_raises(self):
        df = _make_fake_df()
        df.rename(columns={"Adj Close": "Adj_Close"}, inplace=True)
        df.iloc[10, df.columns.get_loc("Close")] = -5.0
        with pytest.raises(ValueError, match="prix <= 0"):
            YahooLoader._validate(df, "TEST")

    def test_correct_columns(self):
        """Le DataFrame retourné a les colonnes attendues."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = YahooLoader(cache_dir=tmpdir)
            fake_df = _make_fake_df(n=50, start="2023-01-02")

            with patch("yfinance.Ticker") as mock_ticker:
                instance = MagicMock()
                instance.history.return_value = fake_df
                mock_ticker.return_value = instance

                df = loader.get_daily_candles("FAKE", "2023-01-02", "2023-03-30")

            assert "Open" in df.columns
            assert "High" in df.columns
            assert "Low" in df.columns
            assert "Close" in df.columns
            assert "Adj_Close" in df.columns
            assert "Volume" in df.columns

    def test_cache_db_written(self, tmp_path: Path):
        """Les donnees sont sauvegardees dans la DB apres un telechargement."""
        from data.db import SignalRadarDB

        test_db = SignalRadarDB(db_path=tmp_path / "test.db")
        loader = YahooLoader()
        fake_df = _make_fake_df(n=50, start="2023-01-02")

        with patch("data.yahoo_loader._db", test_db), \
             patch("yfinance.Ticker") as mock_ticker:
            instance = MagicMock()
            instance.history.return_value = fake_df
            mock_ticker.return_value = instance

            loader.get_daily_candles("FAKE", "2023-01-02", "2023-03-30")

        assert test_db.has_ohlcv("FAKE")
        stored = test_db.get_ohlcv("FAKE")
        assert len(stored) == 50

    def test_weekends_excluded(self):
        """Le DataFrame synthétique n'a pas de weekends (bdate_range)."""
        df = _make_fake_df(n=100)
        # bdate_range exclut les weekends (samedi=5, dimanche=6)
        for ts in df.index:
            assert ts.weekday() < 5, f"Weekend détecté : {ts}"
