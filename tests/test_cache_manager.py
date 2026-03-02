"""Tests pour data/cache_manager.py."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from data.cache_manager import CacheManager


@pytest.fixture
def tmp_cache(tmp_path: Path) -> CacheManager:
    """CacheManager avec un dossier temporaire."""
    return CacheManager(cache_dir=str(tmp_path))


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


class TestCachePath:
    """Tests pour _cache_path."""

    def test_cache_path_normal(self, tmp_cache: CacheManager) -> None:
        path = tmp_cache._cache_path("AAPL")
        assert path.name == "AAPL_1d.parquet"

    def test_cache_path_forex(self, tmp_cache: CacheManager) -> None:
        path = tmp_cache._cache_path("EURUSD=X")
        assert path.name == "EURUSD_X_1d.parquet"


class TestHas:
    """Tests pour has()."""

    def test_has_empty(self, tmp_cache: CacheManager) -> None:
        assert tmp_cache.has("AAPL") is False

    def test_has_after_save(self, tmp_cache: CacheManager) -> None:
        df = _make_ohlcv()
        path = tmp_cache._cache_path("AAPL")
        df.to_parquet(path)
        assert tmp_cache.has("AAPL") is True


class TestInfo:
    """Tests pour info()."""

    def test_info_empty(self, tmp_cache: CacheManager) -> None:
        assert tmp_cache.info() == []

    def test_info_with_data(self, tmp_cache: CacheManager) -> None:
        df = _make_ohlcv(50, "2022-01-03")
        path = tmp_cache._cache_path("MSFT")
        df.to_parquet(path)

        info = tmp_cache.info()
        assert len(info) == 1
        assert info[0]["symbol"] == "MSFT"
        assert info[0]["rows"] == 50
        assert info[0]["start"] == "2022-01-03"
        assert info[0]["size_kb"] > 0


class TestClear:
    """Tests pour clear()."""

    def test_clear_specific(self, tmp_cache: CacheManager) -> None:
        df = _make_ohlcv()
        for sym in ["AAPL", "MSFT"]:
            path = tmp_cache._cache_path(sym)
            df.to_parquet(path)

        tmp_cache.clear("AAPL")
        assert not tmp_cache.has("AAPL")
        assert tmp_cache.has("MSFT")

    def test_clear_all(self, tmp_cache: CacheManager) -> None:
        df = _make_ohlcv()
        for sym in ["AAPL", "MSFT", "GOOGL"]:
            path = tmp_cache._cache_path(sym)
            df.to_parquet(path)

        tmp_cache.clear()
        assert tmp_cache.info() == []
