"""Tests pour strategies/donchian_trend.py — plugin BaseStrategy Donchian TF.

Vérifie entry/exit/trailing/channel/signal via l'API BaseStrategy,
puis cycles complets via engine/simulator.py.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from engine.types import Direction, ExitSignal, Position
from strategies.donchian_trend import DonchianTrend
from tests.conftest import make_bt_config

# ── Helpers ──


def _make_donchian_cache(make_indicator_cache, *, n=100, close=100.0,
                         rolling_high_val=99.0, rolling_low_val=80.0,
                         adx_val=25.0, atr_val=2.0,
                         donchian_entry_period=50, donchian_exit_period=20):
    """Construit un cache pour tests Donchian entry/exit."""
    closes = np.full(n, close)
    opens = np.full(n, close)
    highs = np.full(n, close + 1.0)
    lows = np.full(n, close - 1.0)

    rh = np.full(n, rolling_high_val)
    rl = np.full(n, rolling_low_val)
    rh_exit = np.full(n, close + 5.0)
    rl_exit = np.full(n, close - 5.0)

    adx_arr = np.full(n, adx_val)
    di_plus = np.full(n, 30.0)
    di_minus = np.full(n, 20.0)

    atr_arr = np.full(n, atr_val)

    return make_indicator_cache(
        n=n,
        closes=closes,
        opens=opens,
        highs=highs,
        lows=lows,
        adx_by_period={14: (adx_arr, di_plus, di_minus)},
        atr_by_period={14: atr_arr},
        rolling_high={donchian_entry_period: rh, donchian_exit_period: rh_exit},
        rolling_low={donchian_entry_period: rl, donchian_exit_period: rl_exit},
    )


def _make_position(direction=Direction.LONG, entry_candle=5, entry_price=100.0,
                   state=None):
    return Position(
        entry_price=entry_price, entry_candle=entry_candle, quantity=10.0,
        direction=direction, capital_allocated=1000.0, entry_fee=0.0,
        state=state or {},
    )


# ══════════════════════════════════════════════════════════════════════
# TESTS DEFAULT PARAMS & PARAM GRID
# ══════════════════════════════════════════════════════════════════════


class TestDonchianParams:
    def test_default_params_keys(self):
        strat = DonchianTrend()
        p = strat.default_params()
        required = {
            "entry_mode", "donchian_entry_period", "donchian_exit_period",
            "ema_fast", "ema_slow", "adx_period", "adx_threshold",
            "atr_period", "trailing_atr_mult", "exit_mode",
            "sl_percent", "cooldown_candles", "position_fraction", "sides",
        }
        assert required <= set(p.keys())

    def test_param_grid_combos(self):
        strat = DonchianTrend()
        grid = strat.param_grid()
        n_combos = 1
        for vals in grid.values():
            n_combos *= len(vals)
        # 3 × 2 × 1 × 3 × 1 × 3 = 54
        assert n_combos == 54

    def test_name(self):
        assert DonchianTrend.name == "donchian_trend"


# ══════════════════════════════════════════════════════════════════════
# TESTS ENTRY — DONCHIAN BREAKOUT
# ══════════════════════════════════════════════════════════════════════


class TestDonchianEntry:
    def test_breakout_long(self, make_indicator_cache):
        """Close > rolling_high → LONG."""
        strat = DonchianTrend()
        params = strat.default_params()

        # close=100 > rolling_high=99 → breakout long
        cache = _make_donchian_cache(make_indicator_cache,
                                     close=100.0, rolling_high_val=99.0)
        result = strat.check_entry(60, cache, params)
        assert result == Direction.LONG

    def test_breakout_short(self, make_indicator_cache):
        """Close < rolling_low → SHORT (si sides=[short])."""
        strat = DonchianTrend()
        params = strat.default_params()
        params["sides"] = ["short"]

        # close=75 < rolling_low=80 → breakout short
        cache = _make_donchian_cache(make_indicator_cache,
                                     close=75.0, rolling_low_val=80.0)
        result = strat.check_entry(60, cache, params)
        assert result == Direction.SHORT

    def test_no_breakout_flat(self, make_indicator_cache):
        """Close entre rolling_high et rolling_low → FLAT."""
        strat = DonchianTrend()
        params = strat.default_params()

        # close=90, rolling_high=99, rolling_low=80 → entre les deux
        cache = _make_donchian_cache(make_indicator_cache,
                                     close=90.0, rolling_high_val=99.0,
                                     rolling_low_val=80.0)
        result = strat.check_entry(60, cache, params)
        assert result == Direction.FLAT

    def test_adx_filter_blocks_entry(self, make_indicator_cache):
        """ADX < threshold → FLAT même si breakout."""
        strat = DonchianTrend()
        params = strat.default_params()
        params["adx_threshold"] = 25.0

        # close=100 > rh=99, mais ADX=15 < 25 → bloqué
        cache = _make_donchian_cache(make_indicator_cache,
                                     close=100.0, rolling_high_val=99.0,
                                     adx_val=15.0)
        result = strat.check_entry(60, cache, params)
        assert result == Direction.FLAT

    def test_adx_disabled(self, make_indicator_cache):
        """ADX threshold = 0 → pas de filtrage."""
        strat = DonchianTrend()
        params = strat.default_params()
        params["adx_threshold"] = 0.0

        # ADX faible mais threshold=0 → pas de filtrage
        cache = _make_donchian_cache(make_indicator_cache,
                                     close=100.0, rolling_high_val=99.0,
                                     adx_val=5.0)
        result = strat.check_entry(60, cache, params)
        assert result == Direction.LONG


# ══════════════════════════════════════════════════════════════════════
# TESTS ENTRY — EMA CROSS
# ══════════════════════════════════════════════════════════════════════


class TestEMACrossEntry:
    def test_bull_cross_long(self, make_indicator_cache):
        """EMA fast cross au-dessus slow → LONG."""
        strat = DonchianTrend()
        params = strat.default_params()
        params["entry_mode"] = "ema_cross"

        n = 100
        ema_fast = np.full(n, 95.0)
        ema_slow = np.full(n, 100.0)
        # Bull cross at index 60: fast[60] > slow[60], fast[59] <= slow[59]
        ema_fast[60:] = 105.0

        adx_arr = np.full(n, 25.0)
        cache = make_indicator_cache(
            n=n,
            ema_by_period={9: ema_fast, 50: ema_slow},
            adx_by_period={14: (adx_arr, np.full(n, 30.0), np.full(n, 20.0))},
        )
        # check_entry at i=61, signal on [60]
        result = strat.check_entry(61, cache, params)
        assert result == Direction.LONG

    def test_bear_cross_short(self, make_indicator_cache):
        """EMA fast cross en-dessous slow → SHORT (si sides=[short])."""
        strat = DonchianTrend()
        params = strat.default_params()
        params["entry_mode"] = "ema_cross"
        params["sides"] = ["short"]

        n = 100
        ema_fast = np.full(n, 105.0)
        ema_slow = np.full(n, 100.0)
        # Bear cross at index 60
        ema_fast[60:] = 95.0

        adx_arr = np.full(n, 25.0)
        cache = make_indicator_cache(
            n=n,
            ema_by_period={9: ema_fast, 50: ema_slow},
            adx_by_period={14: (adx_arr, np.full(n, 30.0), np.full(n, 20.0))},
        )
        result = strat.check_entry(61, cache, params)
        assert result == Direction.SHORT


# ══════════════════════════════════════════════════════════════════════
# TESTS EXIT — TRAILING STOP
# ══════════════════════════════════════════════════════════════════════


class TestTrailingExit:
    def test_trailing_gap_exit(self, make_indicator_cache):
        """Open <= trailing_level → gap_trailing exit."""
        strat = DonchianTrend()
        params = strat.default_params()

        n = 100
        opens = np.full(n, 90.0)  # Open gaps below trailing
        cache = make_indicator_cache(n=n, opens=opens)

        state = {"hwm": 105.0, "trailing_level": 95.0}
        pos = _make_position(state=state, entry_candle=5)

        result = strat.check_exit(10, cache, params, pos)
        assert result is not None
        assert result.reason == "gap_trailing"
        assert result.price == 90.0  # exit at open, pas au trailing

    def test_trailing_intraday_exit(self, make_indicator_cache):
        """Low <= trailing_level → trailing exit avec slippage flag."""
        strat = DonchianTrend()
        params = strat.default_params()

        n = 100
        opens = np.full(n, 100.0)  # Open above trailing
        lows = np.full(n, 90.0)    # Low touches trailing
        highs = np.full(n, 105.0)
        cache = make_indicator_cache(n=n, opens=opens, lows=lows, highs=highs)

        state = {"hwm": 105.0, "trailing_level": 95.0}
        pos = _make_position(state=state, entry_candle=5)

        result = strat.check_exit(10, cache, params, pos)
        assert result is not None
        assert result.reason == "trailing"
        assert result.price == 95.0
        assert result.apply_slippage is True

    def test_trailing_no_exit_above(self, make_indicator_cache):
        """Low > trailing_level → pas de trailing exit."""
        strat = DonchianTrend()
        params = strat.default_params()

        n = 100
        opens = np.full(n, 100.0)
        lows = np.full(n, 96.0)  # Low above trailing=95
        highs = np.full(n, 105.0)
        cache = make_indicator_cache(n=n, opens=opens, lows=lows, highs=highs)

        state = {"hwm": 105.0, "trailing_level": 95.0}
        pos = _make_position(state=state, entry_candle=5)

        result = strat.check_exit(10, cache, params, pos)
        assert result is None

    def test_trailing_hwm_update(self, make_indicator_cache):
        """New high → HWM et trailing_level mis à jour."""
        strat = DonchianTrend()
        params = strat.default_params()
        params["trailing_atr_mult"] = 4.0

        n = 100
        opens = np.full(n, 110.0)
        highs = np.full(n, 115.0)  # New high > hwm=105
        lows = np.full(n, 108.0)   # Above new trailing
        atr_arr = np.full(n, 2.0)

        cache = make_indicator_cache(
            n=n, opens=opens, highs=highs, lows=lows,
            atr_by_period={14: atr_arr},
        )

        state = {"hwm": 105.0, "trailing_level": 97.0}
        pos = _make_position(state=state, entry_candle=5)

        result = strat.check_exit(10, cache, params, pos)
        assert result is None  # Low=108 > new trailing
        # HWM updated to 115, trailing = 115 - 2*4 = 107
        assert state["hwm"] == 115.0
        assert state["trailing_level"] == pytest.approx(107.0)

    def test_no_trailing_on_entry_candle(self, make_indicator_cache):
        """Trailing update et intraday check skip quand i == entry_candle."""
        strat = DonchianTrend()
        params = strat.default_params()

        n = 100
        opens = np.full(n, 100.0)
        lows = np.full(n, 80.0)   # Low bien en-dessous du trailing
        highs = np.full(n, 120.0)
        cache = make_indicator_cache(n=n, opens=opens, lows=lows, highs=highs)

        state = {"hwm": 100.0, "trailing_level": 95.0}
        pos = _make_position(state=state, entry_candle=10)

        # i == entry_candle → pas de trailing intraday check
        result = strat.check_exit(10, cache, params, pos)
        assert result is None

    def test_no_trailing_without_state(self, make_indicator_cache):
        """Pas de trailing_level dans state → None."""
        strat = DonchianTrend()
        params = strat.default_params()

        cache = make_indicator_cache(n=100)
        pos = _make_position(state={}, entry_candle=5)

        result = strat.check_exit(10, cache, params, pos)
        assert result is None


# ══════════════════════════════════════════════════════════════════════
# TESTS EXIT — CHANNEL
# ══════════════════════════════════════════════════════════════════════


class TestChannelExit:
    def test_channel_exit_long(self, make_indicator_cache):
        """Close < rolling_low_exit[prev] → channel exit."""
        strat = DonchianTrend()
        params = strat.default_params()
        params["exit_mode"] = "channel"

        n = 100
        closes = np.full(n, 85.0)      # < rolling_low_exit=90
        opens = np.full(n, 100.0)      # Above trailing → no gap
        lows = np.full(n, 96.0)        # Above trailing → no intraday
        rl_exit = np.full(n, 90.0)

        cache = make_indicator_cache(
            n=n, closes=closes, opens=opens, lows=lows,
            rolling_low={20: rl_exit},
            atr_by_period={14: np.full(n, 2.0)},
        )

        state = {"hwm": 105.0, "trailing_level": 95.0}
        pos = _make_position(state=state, entry_candle=5)

        result = strat.check_exit(10, cache, params, pos)
        assert result is not None
        assert result.reason == "channel"
        assert result.price == 85.0
        assert result.apply_slippage is False

    def test_channel_forced_to_trailing_with_ema_entry(self, make_indicator_cache):
        """Channel exit + ema_cross entry → force trailing mode."""
        strat = DonchianTrend()
        params = strat.default_params()
        params["exit_mode"] = "channel"
        params["entry_mode"] = "ema_cross"

        n = 100
        opens = np.full(n, 90.0)  # Gap below trailing
        cache = make_indicator_cache(n=n, opens=opens)

        state = {"hwm": 105.0, "trailing_level": 95.0}
        pos = _make_position(state=state, entry_candle=5)

        # Should fallback to trailing mode → gap_trailing exit
        result = strat.check_exit(10, cache, params, pos)
        assert result is not None
        assert result.reason == "gap_trailing"


# ══════════════════════════════════════════════════════════════════════
# TESTS EXIT — SIGNAL REVERSE (EMA CROSS)
# ══════════════════════════════════════════════════════════════════════


class TestSignalExit:
    def test_signal_exit_long_bear_cross(self, make_indicator_cache):
        """LONG + bear cross → signal_reverse exit."""
        strat = DonchianTrend()
        params = strat.default_params()
        params["exit_mode"] = "signal"
        params["entry_mode"] = "ema_cross"

        n = 100
        ema_fast = np.full(n, 105.0)
        ema_slow = np.full(n, 100.0)
        # Bear cross at 59: fast[59] < slow[59], fast[58] >= slow[58]
        ema_fast[59:] = 95.0
        opens = np.full(n, 100.0)

        cache = make_indicator_cache(
            n=n, opens=opens,
            ema_by_period={9: ema_fast, 50: ema_slow},
        )

        pos = _make_position(state={}, entry_candle=5)

        # check_exit at i=60, prev=59 → bear cross detected
        result = strat.check_exit(60, cache, params, pos)
        assert result is not None
        assert result.reason == "signal_reverse"
        assert result.price == 100.0  # opens[60]
        assert result.apply_slippage is True


# ══════════════════════════════════════════════════════════════════════
# TESTS INIT_STATE
# ══════════════════════════════════════════════════════════════════════


class TestInitState:
    def test_init_state_trailing_long(self, make_indicator_cache):
        """init_state trailing LONG : hwm=entry, trailing=entry - ATR*mult."""
        strat = DonchianTrend()
        params = strat.default_params()
        params["trailing_atr_mult"] = 4.0

        n = 100
        atr_arr = np.full(n, 2.0)
        cache = make_indicator_cache(n=n, atr_by_period={14: atr_arr})

        state = strat.init_state(100.0, 50, cache, params,
                                 direction=Direction.LONG)
        assert state["hwm"] == 100.0
        assert state["trailing_level"] == pytest.approx(92.0)  # 100 - 2*4

    def test_init_state_trailing_short(self, make_indicator_cache):
        """init_state trailing SHORT : hwm=entry, trailing=entry + ATR*mult."""
        strat = DonchianTrend()
        params = strat.default_params()

        n = 100
        atr_arr = np.full(n, 2.0)
        cache = make_indicator_cache(n=n, atr_by_period={14: atr_arr})

        state = strat.init_state(100.0, 50, cache, params,
                                 direction=Direction.SHORT)
        assert state["hwm"] == 100.0
        assert state["trailing_level"] == pytest.approx(108.0)  # 100 + 2*4

    def test_init_state_signal_mode_empty(self, make_indicator_cache):
        """init_state en mode signal → {} (pas de trailing)."""
        strat = DonchianTrend()
        params = strat.default_params()
        params["exit_mode"] = "signal"

        cache = make_indicator_cache(n=100)
        state = strat.init_state(100.0, 50, cache, params,
                                 direction=Direction.LONG)
        assert state == {}

    def test_init_state_zero_atr(self, make_indicator_cache):
        """ATR=0 → trailing_level=0 (LONG) ou inf (SHORT)."""
        strat = DonchianTrend()
        params = strat.default_params()

        n = 100
        atr_arr = np.full(n, 0.0)
        cache = make_indicator_cache(n=n, atr_by_period={14: atr_arr})

        state_long = strat.init_state(100.0, 50, cache, params,
                                      direction=Direction.LONG)
        assert state_long["trailing_level"] == 0.0

        state_short = strat.init_state(100.0, 50, cache, params,
                                       direction=Direction.SHORT)
        assert state_short["trailing_level"] == float("inf")


# ══════════════════════════════════════════════════════════════════════
# TESTS WARMUP
# ══════════════════════════════════════════════════════════════════════


class TestWarmup:
    def test_warmup_donchian(self):
        strat = DonchianTrend()
        params = strat.default_params()
        w = strat.warmup(params)
        # max(50, 0 if trailing, 14*2) + 2 = 52
        assert w == 52

    def test_warmup_ema_cross(self):
        strat = DonchianTrend()
        params = strat.default_params()
        params["entry_mode"] = "ema_cross"
        w = strat.warmup(params)
        # max(50, 14*2) + 2 = 52
        assert w == 52

    def test_warmup_channel(self):
        strat = DonchianTrend()
        params = strat.default_params()
        params["exit_mode"] = "channel"
        w = strat.warmup(params)
        # max(50, 20, 28) + 2 = 52
        assert w == 52


# ══════════════════════════════════════════════════════════════════════
# TEST FULL CYCLE VIA SIMULATOR
# ══════════════════════════════════════════════════════════════════════


class TestDonchianFullCycle:
    def test_donchian_breakout_entry_trailing_exit(self, make_indicator_cache):
        """Cycle : breakout long → trailing exit qqs candles plus tard."""
        from engine.simulator import simulate

        strat = DonchianTrend()
        params = strat.default_params()
        params["donchian_entry_period"] = 20
        params["adx_threshold"] = 0.0     # Pas de filtre ADX
        params["trailing_atr_mult"] = 2.0
        params["sl_percent"] = 0.0
        params["cooldown_candles"] = 0

        n = 100
        closes = np.full(n, 100.0)
        opens = np.full(n, 100.0)
        highs = np.full(n, 101.0)
        lows = np.full(n, 99.0)
        atr_arr = np.full(n, 2.0)

        # Breakout at candle 55: close > rolling_high
        rh = np.full(n, 101.0)  # rolling_high[20] = 101
        rl = np.full(n, 80.0)

        # Signal on candle 55: close > rh → breakout
        closes[55] = 102.0
        highs[55] = 103.0

        # Entry at candle 56: open=103
        opens[56] = 103.0
        highs[56] = 105.0
        lows[56] = 102.0
        closes[56] = 104.0

        # Candle 57+: price drops → trailing hit
        for j in range(57, n):
            opens[j] = 104.0
            highs[j] = 104.0
            lows[j] = 90.0   # Way below trailing
            closes[j] = 91.0

        cache = make_indicator_cache(
            n=n, closes=closes, opens=opens, highs=highs, lows=lows,
            atr_by_period={14: atr_arr},
            rolling_high={20: rh},
            rolling_low={20: rl},
            adx_by_period={14: (np.full(n, 30.0), np.full(n, 30.0), np.full(n, 20.0))},
        )
        config = make_bt_config()
        result = simulate(strat, cache, params, config)

        assert result.n_trades >= 1
        t = result.trades[0]
        assert t.exit_reason in ("trailing", "gap_trailing")
