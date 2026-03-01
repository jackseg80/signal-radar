"""Tests pour strategies/rsi2_mean_reversion.py — plugin BaseStrategy RSI(2).

Vérifie entry/exit/params via l'API BaseStrategy, puis cycles complets
via engine/simulator.py.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from engine.types import Direction, ExitSignal, Position
from strategies.rsi2_mean_reversion import RSI2MeanReversion
from tests.conftest import make_bt_config

# ── Helpers ──


def _make_rsi2_cache(make_indicator_cache, *, n=50, rsi_val=5.0, close=110.0,
                     sma200=100.0, sma5=105.0, rsi_exit_val=None):
    """Construit un cache avec RSI et SMA pré-remplis pour tests RSI2."""
    closes = np.full(n, close)
    rsi_arr = np.full(n, rsi_val)
    sma200_arr = np.full(n, sma200)
    sma5_arr = np.full(n, sma5)

    if rsi_exit_val is not None:
        rsi_arr[-5:] = rsi_exit_val

    return make_indicator_cache(
        n=n,
        closes=closes,
        rsi_by_period={2: rsi_arr},
        sma_by_period={200: sma200_arr, 5: sma5_arr},
    )


# ══════════════════════════════════════════════════════════════════════
# TESTS DEFAULT PARAMS & PARAM GRID
# ══════════════════════════════════════════════════════════════════════


class TestRSI2Params:
    def test_default_params_keys(self):
        strat = RSI2MeanReversion()
        p = strat.default_params()
        required = {
            "rsi_period", "rsi_entry_threshold", "sma_trend_period",
            "sma_exit_period", "rsi_exit_threshold", "sma_trend_buffer",
            "sl_percent", "position_fraction", "cooldown_candles", "sides",
        }
        assert required <= set(p.keys())

    def test_default_params_values_connors(self):
        """Params par défaut = Connors canonical."""
        strat = RSI2MeanReversion()
        p = strat.default_params()
        assert p["rsi_period"] == 2
        assert p["rsi_entry_threshold"] == 10.0
        assert p["sma_trend_period"] == 200
        assert p["sma_exit_period"] == 5
        assert p["sma_trend_buffer"] == 1.01
        assert p["sl_percent"] == 0.0  # Pas de SL Connors
        assert p["sides"] == ["long"]

    def test_param_grid_combos(self):
        strat = RSI2MeanReversion()
        grid = strat.param_grid()
        n_combos = 1
        for vals in grid.values():
            n_combos *= len(vals)
        # Spec : 4 × 3 × 4 = 48 combos
        assert n_combos == 48

    def test_name(self):
        assert RSI2MeanReversion.name == "rsi2_mean_reversion"


# ══════════════════════════════════════════════════════════════════════
# TESTS ENTRY
# ══════════════════════════════════════════════════════════════════════


class TestRSI2Entry:
    def test_long_entry_rsi_low_above_trend(self, make_indicator_cache):
        """RSI < 10 + close > SMA200 * buffer → LONG."""
        strat = RSI2MeanReversion()
        params = strat.default_params()

        # close=110 > sma200=100 * 1.01 = 101, rsi=5 < 10 → LONG
        cache = _make_rsi2_cache(make_indicator_cache, rsi_val=5.0,
                                 close=110.0, sma200=100.0)
        result = strat.check_entry(10, cache, params)
        assert result == Direction.LONG

    def test_no_entry_rsi_too_high(self, make_indicator_cache):
        """RSI >= threshold → pas d'entrée."""
        strat = RSI2MeanReversion()
        params = strat.default_params()

        cache = _make_rsi2_cache(make_indicator_cache, rsi_val=15.0,
                                 close=110.0, sma200=100.0)
        result = strat.check_entry(10, cache, params)
        assert result == Direction.FLAT

    def test_no_entry_below_trend(self, make_indicator_cache):
        """Close < SMA200 * buffer → pas d'entrée (tendance baissière)."""
        strat = RSI2MeanReversion()
        params = strat.default_params()

        # close=99 < sma200=100 * 1.01 = 101
        cache = _make_rsi2_cache(make_indicator_cache, rsi_val=5.0,
                                 close=99.0, sma200=100.0)
        result = strat.check_entry(10, cache, params)
        assert result == Direction.FLAT

    def test_no_entry_nan_rsi(self, make_indicator_cache):
        """RSI NaN → FLAT."""
        strat = RSI2MeanReversion()
        params = strat.default_params()

        cache = _make_rsi2_cache(make_indicator_cache, rsi_val=float("nan"),
                                 close=110.0, sma200=100.0)
        result = strat.check_entry(10, cache, params)
        assert result == Direction.FLAT

    def test_no_entry_nan_sma(self, make_indicator_cache):
        """SMA NaN → FLAT."""
        strat = RSI2MeanReversion()
        params = strat.default_params()

        cache = _make_rsi2_cache(make_indicator_cache, rsi_val=5.0,
                                 close=110.0, sma200=float("nan"))
        result = strat.check_entry(10, cache, params)
        assert result == Direction.FLAT

    def test_buffer_effect(self, make_indicator_cache):
        """Close juste au-dessus de SMA200 mais en-dessous du buffer → FLAT."""
        strat = RSI2MeanReversion()
        params = strat.default_params()  # buffer=1.01

        # close=100.5 > sma200=100 mais < 100*1.01=101 → FLAT
        cache = _make_rsi2_cache(make_indicator_cache, rsi_val=5.0,
                                 close=100.5, sma200=100.0)
        result = strat.check_entry(10, cache, params)
        assert result == Direction.FLAT

    def test_short_entry_if_sides_include_short(self, make_indicator_cache):
        """Short : RSI > (100 - threshold) + close < SMA200 / buffer."""
        strat = RSI2MeanReversion()
        params = strat.default_params()
        params["sides"] = ["short"]

        n = 50
        closes = np.full(n, 90.0)  # close < sma200 / 1.01 ≈ 99.0
        rsi_arr = np.full(n, 95.0)  # > 100 - 10 = 90
        sma200_arr = np.full(n, 100.0)

        cache = make_indicator_cache(
            n=n, closes=closes,
            rsi_by_period={2: rsi_arr},
            sma_by_period={200: sma200_arr, 5: np.full(n, 95.0)},
        )
        result = strat.check_entry(10, cache, params)
        assert result == Direction.SHORT


# ══════════════════════════════════════════════════════════════════════
# TESTS EXIT
# ══════════════════════════════════════════════════════════════════════


class TestRSI2Exit:
    def _make_position(self, direction=Direction.LONG, entry_candle=5):
        return Position(
            entry_price=100.0, entry_candle=entry_candle, quantity=10.0,
            direction=direction, capital_allocated=1000.0, entry_fee=0.0,
        )

    def test_sma_exit_long(self, make_indicator_cache):
        """Close > SMA5 → sma_exit."""
        strat = RSI2MeanReversion()
        params = strat.default_params()

        n = 50
        closes = np.full(n, 110.0)  # close > sma5
        cache = make_indicator_cache(
            n=n, closes=closes,
            rsi_by_period={2: np.full(n, 50.0)},
            sma_by_period={200: np.full(n, 100.0), 5: np.full(n, 105.0)},
        )
        pos = self._make_position()
        result = strat.check_exit(10, cache, params, pos)

        assert result is not None
        assert result.reason == "sma_exit"
        assert result.price == 110.0
        assert result.apply_slippage is False

    def test_no_sma_exit_below(self, make_indicator_cache):
        """Close < SMA5 → pas de sma_exit."""
        strat = RSI2MeanReversion()
        params = strat.default_params()

        n = 50
        closes = np.full(n, 100.0)  # close < sma5=105
        cache = make_indicator_cache(
            n=n, closes=closes,
            rsi_by_period={2: np.full(n, 50.0)},
            sma_by_period={200: np.full(n, 110.0), 5: np.full(n, 105.0)},
        )
        pos = self._make_position()
        result = strat.check_exit(10, cache, params, pos)

        # SMA exit non déclenchée, RSI exit disabled (threshold=0),
        # trend break : close=100 < sma200=110 → trend_break
        assert result is not None
        assert result.reason == "trend_break"

    def test_rsi_exit_when_enabled(self, make_indicator_cache):
        """RSI > rsi_exit_threshold → rsi_exit (si activé)."""
        strat = RSI2MeanReversion()
        params = strat.default_params()
        params["rsi_exit_threshold"] = 70.0

        n = 50
        closes = np.full(n, 100.0)  # close < sma5=105 → pas de sma_exit
        rsi_arr = np.full(n, 80.0)  # > 70 → rsi_exit

        cache = make_indicator_cache(
            n=n, closes=closes,
            rsi_by_period={2: rsi_arr},
            sma_by_period={200: np.full(n, 90.0), 5: np.full(n, 105.0)},
        )
        pos = self._make_position()
        result = strat.check_exit(10, cache, params, pos)

        assert result is not None
        assert result.reason == "rsi_exit"
        assert result.price == 100.0

    def test_trend_break_exit(self, make_indicator_cache):
        """Close < SMA200 → trend_break."""
        strat = RSI2MeanReversion()
        params = strat.default_params()

        n = 50
        closes = np.full(n, 95.0)  # < sma200=100, < sma5=105
        cache = make_indicator_cache(
            n=n, closes=closes,
            rsi_by_period={2: np.full(n, 50.0)},
            sma_by_period={200: np.full(n, 100.0), 5: np.full(n, 105.0)},
        )
        pos = self._make_position()
        result = strat.check_exit(10, cache, params, pos)

        assert result is not None
        assert result.reason == "trend_break"
        assert result.price == 95.0

    def test_no_exit_holding(self, make_indicator_cache):
        """Close entre SMA5 et SMA200, RSI exit désactivé → None."""
        strat = RSI2MeanReversion()
        params = strat.default_params()

        n = 50
        closes = np.full(n, 102.0)  # < sma5=105, > sma200=100
        cache = make_indicator_cache(
            n=n, closes=closes,
            rsi_by_period={2: np.full(n, 50.0)},
            sma_by_period={200: np.full(n, 100.0), 5: np.full(n, 105.0)},
        )
        pos = self._make_position()
        result = strat.check_exit(10, cache, params, pos)

        assert result is None

    def test_exit_priority_sma_before_rsi(self, make_indicator_cache):
        """SMA exit a priorité sur RSI exit."""
        strat = RSI2MeanReversion()
        params = strat.default_params()
        params["rsi_exit_threshold"] = 70.0

        n = 50
        closes = np.full(n, 110.0)  # > sma5=105 ET > rsi_threshold
        rsi_arr = np.full(n, 80.0)

        cache = make_indicator_cache(
            n=n, closes=closes,
            rsi_by_period={2: rsi_arr},
            sma_by_period={200: np.full(n, 100.0), 5: np.full(n, 105.0)},
        )
        pos = self._make_position()
        result = strat.check_exit(10, cache, params, pos)

        assert result.reason == "sma_exit"  # SMA d'abord


# ══════════════════════════════════════════════════════════════════════
# TEST FULL CYCLE VIA SIMULATOR
# ══════════════════════════════════════════════════════════════════════


class TestRSI2FullCycle:
    def test_entry_then_sma_exit(self, make_indicator_cache):
        """Cycle complet : RSI bas → entry, puis close > SMA5 → exit."""
        from engine.simulator import simulate

        strat = RSI2MeanReversion()
        params = strat.default_params()
        params["cooldown_candles"] = 0
        # Réduire les périodes pour que warmup < n
        params["sma_trend_period"] = 10
        params["sma_exit_period"] = 3

        n = 50
        closes = np.full(n, 110.0)   # > sma_trend*buffer
        opens = np.full(n, 110.0)
        highs = np.full(n, 112.0)
        lows = np.full(n, 108.0)
        rsi_arr = np.full(n, 50.0)    # Pas d'entry
        sma_trend_arr = np.full(n, 100.0)
        sma_exit_arr = np.full(n, 105.0)

        # Candle 25 : RSI bas → signal entry (well past warmup=20)
        rsi_arr[25] = 5.0
        # Candle 26 : entry au open (110)
        # Close 26 = 110 > SMA_exit=105 → sma_exit sur candle 26

        cache = make_indicator_cache(
            n=n, closes=closes, opens=opens, highs=highs, lows=lows,
            rsi_by_period={2: rsi_arr},
            sma_by_period={10: sma_trend_arr, 3: sma_exit_arr},
        )
        config = make_bt_config()
        result = simulate(strat, cache, params, config)

        assert result.n_trades >= 1
        assert result.trades[0].exit_reason == "sma_exit"

    def test_init_state_empty(self):
        """RSI2 init_state retourne {} (pas de trailing)."""
        strat = RSI2MeanReversion()
        state = strat.init_state(100.0, 10, None, strat.default_params())
        assert state == {}
