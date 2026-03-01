"""Tests pour strategies/ibs_mean_reversion.py -- plugin BaseStrategy IBS.

Verifie indicateur IBS, entry/exit/params via l'API BaseStrategy, puis
cycle complet via engine/simulator.py.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from engine.indicators import internal_bar_strength
from engine.types import Direction, ExitSignal, Position
from strategies.ibs_mean_reversion import IBSMeanReversion
from tests.conftest import make_bt_config


# ── Helpers ──


def _make_ibs_cache(
    make_indicator_cache,
    *,
    n=50,
    ibs_val=0.1,
    close=110.0,
    sma200=100.0,
    high=112.0,
    low=108.0,
):
    """Construit un cache avec IBS et SMA pre-remplis pour tests IBS."""
    closes = np.full(n, close)
    highs = np.full(n, high)
    lows = np.full(n, low)
    ibs_arr = np.full(n, ibs_val)
    sma200_arr = np.full(n, sma200)

    return make_indicator_cache(
        n=n,
        closes=closes,
        highs=highs,
        lows=lows,
        sma_by_period={200: sma200_arr},
        ibs=ibs_arr,
    )


# ======================================================================
# TESTS INDICATEUR IBS
# ======================================================================


class TestIBSIndicator:
    def test_ibs_close_at_low(self):
        """IBS(close=low) = 0.0."""
        highs = np.array([110.0, 120.0, 115.0])
        lows = np.array([100.0, 105.0, 108.0])
        closes = np.array([100.0, 105.0, 108.0])  # close == low
        result = internal_bar_strength(highs, lows, closes)
        np.testing.assert_array_almost_equal(result, [0.0, 0.0, 0.0])

    def test_ibs_close_at_high(self):
        """IBS(close=high) = 1.0."""
        highs = np.array([110.0, 120.0, 115.0])
        lows = np.array([100.0, 105.0, 108.0])
        closes = np.array([110.0, 120.0, 115.0])  # close == high
        result = internal_bar_strength(highs, lows, closes)
        np.testing.assert_array_almost_equal(result, [1.0, 1.0, 1.0])

    def test_ibs_midrange(self):
        """IBS(close=mid) = 0.5."""
        highs = np.array([110.0])
        lows = np.array([100.0])
        closes = np.array([105.0])  # mid
        result = internal_bar_strength(highs, lows, closes)
        np.testing.assert_array_almost_equal(result, [0.5])

    def test_ibs_doji(self):
        """High == Low (doji) -> NaN."""
        highs = np.array([100.0, 110.0])
        lows = np.array([100.0, 105.0])
        closes = np.array([100.0, 107.0])
        result = internal_bar_strength(highs, lows, closes)
        assert math.isnan(result[0])
        assert not math.isnan(result[1])


# ======================================================================
# TESTS DEFAULT PARAMS & PARAM GRID
# ======================================================================


class TestIBSParams:
    def test_default_params_keys(self):
        strat = IBSMeanReversion()
        p = strat.default_params()
        required = {
            "ibs_entry_threshold", "ibs_exit_threshold", "sma_trend_period",
            "sl_percent", "position_fraction", "cooldown_candles", "sides",
        }
        assert required <= set(p.keys())

    def test_default_params_values(self):
        strat = IBSMeanReversion()
        p = strat.default_params()
        assert p["ibs_entry_threshold"] == 0.2
        assert p["ibs_exit_threshold"] == 0.8
        assert p["sma_trend_period"] == 200
        assert p["sl_percent"] == 0.0
        assert p["sides"] == ["long"]

    def test_param_grid_combos(self):
        strat = IBSMeanReversion()
        grid = strat.param_grid()
        n_combos = 1
        for vals in grid.values():
            n_combos *= len(vals)
        # 4 x 3 x 3 = 36 combos
        assert n_combos == 36

    def test_param_grid_covers_defaults(self):
        """Valeurs par defaut incluses dans le grid."""
        strat = IBSMeanReversion()
        p = strat.default_params()
        grid = strat.param_grid()
        for key, values in grid.items():
            assert p[key] in values, f"default {key}={p[key]} not in grid {values}"

    def test_name(self):
        assert IBSMeanReversion.name == "ibs_mean_reversion"

    def test_warmup_auto(self):
        """Warmup = max(sma_trend_period=200) + 10 = 210."""
        strat = IBSMeanReversion()
        p = strat.default_params()
        assert strat.warmup(p) == 210


# ======================================================================
# TESTS ENTRY
# ======================================================================


class TestIBSEntry:
    def test_long_entry_ibs_below_threshold(self, make_indicator_cache):
        """IBS < 0.2 + close > SMA200 -> LONG."""
        strat = IBSMeanReversion()
        params = strat.default_params()

        cache = _make_ibs_cache(make_indicator_cache, ibs_val=0.1,
                                close=110.0, sma200=100.0)
        result = strat.check_entry(10, cache, params)
        assert result == Direction.LONG

    def test_no_entry_ibs_above_threshold(self, make_indicator_cache):
        """IBS >= 0.2 -> pas d'entree."""
        strat = IBSMeanReversion()
        params = strat.default_params()

        cache = _make_ibs_cache(make_indicator_cache, ibs_val=0.5,
                                close=110.0, sma200=100.0)
        result = strat.check_entry(10, cache, params)
        assert result == Direction.FLAT

    def test_no_entry_below_sma_trend(self, make_indicator_cache):
        """IBS < 0.2 mais close < SMA200 -> FLAT."""
        strat = IBSMeanReversion()
        params = strat.default_params()

        cache = _make_ibs_cache(make_indicator_cache, ibs_val=0.1,
                                close=95.0, sma200=100.0)
        result = strat.check_entry(10, cache, params)
        assert result == Direction.FLAT

    def test_no_entry_nan_ibs(self, make_indicator_cache):
        """IBS NaN -> FLAT."""
        strat = IBSMeanReversion()
        params = strat.default_params()

        cache = _make_ibs_cache(make_indicator_cache, ibs_val=float("nan"),
                                close=110.0, sma200=100.0)
        result = strat.check_entry(10, cache, params)
        assert result == Direction.FLAT

    def test_no_entry_ibs_none(self, make_indicator_cache):
        """Cache sans IBS -> FLAT."""
        strat = IBSMeanReversion()
        params = strat.default_params()

        cache = make_indicator_cache(
            n=50,
            closes=np.full(50, 110.0),
            sma_by_period={200: np.full(50, 100.0)},
            ibs=None,
        )
        result = strat.check_entry(10, cache, params)
        assert result == Direction.FLAT

    def test_short_entry_if_sides_include_short(self, make_indicator_cache):
        """Short : IBS > 0.8 + close < SMA200."""
        strat = IBSMeanReversion()
        params = strat.default_params()
        params["sides"] = ["short"]

        cache = _make_ibs_cache(make_indicator_cache, ibs_val=0.9,
                                close=90.0, sma200=100.0)
        result = strat.check_entry(10, cache, params)
        assert result == Direction.SHORT


# ======================================================================
# TESTS EXIT
# ======================================================================


class TestIBSExit:
    def _make_position(self, direction=Direction.LONG, entry_candle=5):
        return Position(
            entry_price=100.0, entry_candle=entry_candle, quantity=10.0,
            direction=direction, capital_allocated=1000.0, entry_fee=0.0,
        )

    def test_ibs_exit(self, make_indicator_cache):
        """IBS > 0.8 -> ibs_exit."""
        strat = IBSMeanReversion()
        params = strat.default_params()

        n = 50
        closes = np.full(n, 105.0)
        highs = np.full(n, 112.0)
        lows = np.full(n, 98.0)
        ibs_arr = np.full(n, 0.85)  # > 0.8 -> exit

        cache = make_indicator_cache(
            n=n, closes=closes, highs=highs, lows=lows,
            sma_by_period={200: np.full(n, 100.0)},
            ibs=ibs_arr,
        )
        pos = self._make_position()
        result = strat.check_exit(10, cache, params, pos)

        assert result is not None
        assert result.reason == "ibs_exit"
        assert result.price == 105.0
        assert result.apply_slippage is False

    def test_prev_high_exit(self, make_indicator_cache):
        """Close > yesterday's high -> prev_high_exit."""
        strat = IBSMeanReversion()
        params = strat.default_params()

        n = 50
        closes = np.full(n, 115.0)  # > highs[i-1] = 112
        highs = np.full(n, 112.0)
        lows = np.full(n, 98.0)
        ibs_arr = np.full(n, 0.5)  # Not triggering ibs_exit

        cache = make_indicator_cache(
            n=n, closes=closes, highs=highs, lows=lows,
            sma_by_period={200: np.full(n, 100.0)},
            ibs=ibs_arr,
        )
        pos = self._make_position()
        result = strat.check_exit(10, cache, params, pos)

        assert result is not None
        assert result.reason == "prev_high_exit"
        assert result.price == 115.0

    def test_trend_break_exit(self, make_indicator_cache):
        """Close < SMA200 -> trend_break."""
        strat = IBSMeanReversion()
        params = strat.default_params()

        n = 50
        closes = np.full(n, 95.0)  # < sma200=100
        highs = np.full(n, 112.0)  # highs[i-1]=112 > close=95 -> no prev_high
        lows = np.full(n, 90.0)
        ibs_arr = np.full(n, 0.5)  # Not triggering ibs_exit

        cache = make_indicator_cache(
            n=n, closes=closes, highs=highs, lows=lows,
            sma_by_period={200: np.full(n, 100.0)},
            ibs=ibs_arr,
        )
        pos = self._make_position()
        result = strat.check_exit(10, cache, params, pos)

        assert result is not None
        assert result.reason == "trend_break"
        assert result.price == 95.0

    def test_no_exit_holding(self, make_indicator_cache):
        """IBS milieu, close < highs[-1], close > SMA200 -> None."""
        strat = IBSMeanReversion()
        params = strat.default_params()

        n = 50
        closes = np.full(n, 105.0)   # > sma200=100, < highs[i-1]=112
        highs = np.full(n, 112.0)
        lows = np.full(n, 98.0)
        ibs_arr = np.full(n, 0.5)  # Between 0.2 and 0.8

        cache = make_indicator_cache(
            n=n, closes=closes, highs=highs, lows=lows,
            sma_by_period={200: np.full(n, 100.0)},
            ibs=ibs_arr,
        )
        pos = self._make_position()
        result = strat.check_exit(10, cache, params, pos)

        assert result is None

    def test_exit_priority_ibs_before_prev_high(self, make_indicator_cache):
        """IBS exit a priorite sur prev_high_exit."""
        strat = IBSMeanReversion()
        params = strat.default_params()

        n = 50
        closes = np.full(n, 115.0)  # > highs[i-1]=112 ET ibs=0.9 > 0.8
        highs = np.full(n, 112.0)
        lows = np.full(n, 98.0)
        ibs_arr = np.full(n, 0.9)

        cache = make_indicator_cache(
            n=n, closes=closes, highs=highs, lows=lows,
            sma_by_period={200: np.full(n, 100.0)},
            ibs=ibs_arr,
        )
        pos = self._make_position()
        result = strat.check_exit(10, cache, params, pos)

        assert result.reason == "ibs_exit"  # IBS d'abord


# ======================================================================
# TEST FULL CYCLE VIA SIMULATOR
# ======================================================================


class TestIBSFullCycle:
    def test_entry_then_ibs_exit(self, make_indicator_cache):
        """Cycle complet : IBS bas -> entry, puis IBS haut -> exit."""
        from engine.simulator import simulate

        strat = IBSMeanReversion()
        params = strat.default_params()
        params["cooldown_candles"] = 0
        params["sma_trend_period"] = 10  # Reduce for warmup < n

        n = 50
        closes = np.full(n, 110.0)
        opens = np.full(n, 110.0)
        highs = np.full(n, 115.0)
        lows = np.full(n, 105.0)
        ibs_arr = np.full(n, 0.5)  # Neutral IBS
        sma_trend_arr = np.full(n, 100.0)

        # Candle 25 : IBS bas -> signal entry (well past warmup=20)
        ibs_arr[25] = 0.1
        # Candle 26 : entry au open (110)
        # IBS[26] = 0.5 < 0.8 -> no ibs_exit
        # close[26] = 110 < highs[25] = 115 -> no prev_high_exit
        # close[26] = 110 > sma_trend = 100 -> no trend_break
        # -> holding

        # Candle 27 : IBS haut -> exit
        ibs_arr[27] = 0.9

        cache = make_indicator_cache(
            n=n, closes=closes, opens=opens, highs=highs, lows=lows,
            sma_by_period={10: sma_trend_arr},
            ibs=ibs_arr,
        )
        config = make_bt_config()
        result = simulate(strat, cache, params, config)

        assert result.n_trades >= 1
        assert result.trades[0].exit_reason == "ibs_exit"

    def test_init_state_empty(self):
        """IBS init_state retourne {} (pas de trailing)."""
        strat = IBSMeanReversion()
        state = strat.init_state(100.0, 10, None, strat.default_params())
        assert state == {}
