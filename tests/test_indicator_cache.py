"""Tests pour engine/indicator_cache.py."""

from __future__ import annotations

import math

import numpy as np
import pytest

from engine.indicator_cache import IndicatorCache, build_cache
from engine.indicators import rolling_max, rolling_min


# ─── build_cache ───────────────────────────────────────────────────────────


class TestBuildCache:
    """Tests pour build_cache()."""

    @pytest.fixture
    def sample_arrays(self) -> dict[str, np.ndarray]:
        n = 200
        rng = np.random.default_rng(42)
        closes = 100 + np.cumsum(rng.standard_normal(n) * 0.5)
        opens = closes + rng.standard_normal(n) * 0.2
        highs = np.maximum(opens, closes) + rng.uniform(0.1, 1.0, n)
        lows = np.minimum(opens, closes) - rng.uniform(0.1, 1.0, n)
        volumes = rng.uniform(1e6, 5e6, n)
        return {
            "opens": opens,
            "highs": highs,
            "lows": lows,
            "closes": closes,
            "volumes": volumes,
        }

    @pytest.fixture
    def param_grid(self) -> dict[str, list]:
        return {
            "ema_fast": [9, 21],
            "ema_slow": [50],
            "adx_period": [14],
            "atr_period": [14],
            "donchian_entry_period": [20, 50],
            "donchian_exit_period": [10],
        }

    def test_cache_has_correct_shape(self, sample_arrays, param_grid):
        cache = build_cache(sample_arrays, param_grid)
        assert cache.n_candles == 200
        assert len(cache.closes) == 200
        assert len(cache.opens) == 200

    def test_ema_periods_computed(self, sample_arrays, param_grid):
        cache = build_cache(sample_arrays, param_grid)
        assert 9 in cache.ema_by_period
        assert 21 in cache.ema_by_period
        assert 50 in cache.ema_by_period
        for p, arr in cache.ema_by_period.items():
            assert len(arr) == 200

    def test_adx_stores_tuple(self, sample_arrays, param_grid):
        cache = build_cache(sample_arrays, param_grid)
        assert 14 in cache.adx_by_period
        adx_tuple = cache.adx_by_period[14]
        assert isinstance(adx_tuple, tuple)
        assert len(adx_tuple) == 3  # (adx, di_plus, di_minus)
        for arr in adx_tuple:
            assert len(arr) == 200

    def test_atr_computed(self, sample_arrays, param_grid):
        cache = build_cache(sample_arrays, param_grid)
        assert 14 in cache.atr_by_period
        assert len(cache.atr_by_period[14]) == 200

    def test_rolling_high_low_computed(self, sample_arrays, param_grid):
        cache = build_cache(sample_arrays, param_grid)
        assert 20 in cache.rolling_high
        assert 50 in cache.rolling_high
        assert 10 in cache.rolling_low
        for p, arr in cache.rolling_high.items():
            assert len(arr) == 200

    def test_total_days_calculated(self, sample_arrays, param_grid):
        cache = build_cache(sample_arrays, param_grid)
        expected = 200 * 365.0 / 252.0
        assert abs(cache.total_days - expected) < 0.01


# ─── rolling_max / rolling_min anti look-ahead ────────────────────────────


class TestRollingAntiLookAhead:
    """Vérifie que rolling_max/min excluent l'élément courant."""

    def test_rolling_max_excludes_current(self):
        """rolling_max[i] = max(arr[i-window:i]), pas arr[i-window:i+1]."""
        arr = np.array([1.0, 2.0, 3.0, 10.0, 4.0, 5.0, 6.0, 7.0])
        rm = rolling_max(arr, 3)
        # rm[3] = max(arr[0:3]) = max(1, 2, 3) = 3, PAS 10
        assert rm[3] == 3.0
        # rm[4] = max(arr[1:4]) = max(2, 3, 10) = 10
        assert rm[4] == 10.0

    def test_rolling_min_excludes_current(self):
        arr = np.array([5.0, 4.0, 3.0, 1.0, 6.0, 7.0, 8.0, 9.0])
        rm = rolling_min(arr, 3)
        # rm[3] = min(arr[0:3]) = min(5, 4, 3) = 3, PAS 1
        assert rm[3] == 3.0
        # rm[4] = min(arr[1:4]) = min(4, 3, 1) = 1
        assert rm[4] == 1.0

    def test_rolling_max_nan_before_window(self):
        arr = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        rm = rolling_max(arr, 3)
        assert math.isnan(rm[0])
        assert math.isnan(rm[1])
        assert math.isnan(rm[2])
        assert not math.isnan(rm[3])
