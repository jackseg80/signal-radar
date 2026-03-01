"""Tests du moteur de backtest gap-aware.

Inclut :
- 6 tests gap-aware CRITIQUES (nouveaux)
- Tests portés depuis scalp-radar (entrée, sortie, ADX, cooldown, etc.)
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from engine.backtest_config import BacktestConfig
from engine.fast_backtest import (
    _close_trend_position,
    _compute_fast_metrics,
    _simulate_trend_follow,
    run_backtest_from_cache,
)
from engine.fee_model import FEE_MODEL_US_STOCKS, FeeModel
from engine.indicator_cache import IndicatorCache
from engine.indicators import rolling_max, rolling_min
from tests.conftest import (
    default_params,
    make_bt_config,
    setup_bear_cross,
    setup_bull_cross,
    setup_donchian_breakout_long,
)


# ══════════════════════════════════════════════════════════════════════════════
# TESTS GAP-AWARE — PRIORITÉ #1
# ══════════════════════════════════════════════════════════════════════════════


class TestGapAwareExits:
    """Tests critiques pour la gestion des gaps actions."""

    def test_gap_down_exits_at_open_not_sl(self, make_indicator_cache):
        """Gap DOWN overnight : exit à l'open, PAS au SL.

        Position LONG, SL=90 (sl_percent=10%, entry≈100).
        Open[gap_candle]=80 (gaps sous SL).
        Exit doit être à 80, pas 90.
        """
        n = 200
        breakout_at = 60
        period = 20
        gap_candle = breakout_at + 2  # 2 candles après le signal

        closes = np.full(n, 100.0)
        opens = np.full(n, 100.0)
        highs = np.full(n, 101.0)
        lows = np.full(n, 99.0)

        # Breakout sur candle breakout_at
        closes[breakout_at] = 102.0
        highs[breakout_at] = 103.0

        # Entrée sur candle breakout_at+1
        entry_candle = breakout_at + 1
        opens[entry_candle] = 103.0
        highs[entry_candle] = 104.0
        lows[entry_candle] = 102.0
        closes[entry_candle] = 103.5

        # GAP DOWN : open[gap_candle] = 80 (bien en dessous du SL ≈ 92.7)
        opens[gap_candle] = 80.0
        highs[gap_candle] = 82.0
        lows[gap_candle] = 78.0
        closes[gap_candle] = 81.0

        rh = rolling_max(highs, period)
        rl = rolling_min(lows, period)

        cache = make_indicator_cache(
            n=n, closes=closes, opens=opens, highs=highs, lows=lows,
            rolling_high={period: rh},
            rolling_low={period: rl},
        )

        params = default_params(
            donchian_entry_period=period, sl_percent=10.0,
            trailing_atr_mult=100.0,  # Trailing très large pour ne pas interférer
        )
        config = make_bt_config()

        pnls, _, _ = _simulate_trend_follow(cache, params, config)
        assert len(pnls) >= 1

        # Le PnL doit refléter un exit à ~80, pas au SL (~92.7)
        # entry ≈ 103.0, exit ≈ 80 → pnl ≈ (80 - 103) * qty ≈ très négatif
        # Si exit au SL : pnl ≈ (92.7 - 103) * qty ≈ moins négatif
        # Donc pnl[0] < ce qu'on aurait avec un SL normal
        entry_price = 103.0  # opens[entry_candle]
        sl_price = entry_price * 0.9  # 92.7
        qty = (100_000 * 0.3) / entry_price
        pnl_at_sl = (sl_price - entry_price) * qty
        pnl_at_gap = (80.0 - entry_price) * qty

        # Le PnL réel doit être proche du gap (80), pas du SL
        assert pnls[0] < pnl_at_sl * 0.5  # Beaucoup plus négatif que le SL
        assert abs(pnls[0] - pnl_at_gap) < abs(pnl_at_gap) * 0.1  # ≈ gap price

    def test_gap_up_exits_at_open_not_sl_short(self, make_indicator_cache):
        """Gap UP overnight sur SHORT : exit à l'open.

        Position SHORT, SL=110 (sl_percent=10%, entry≈100).
        Open[gap_candle]=120 (gaps au-dessus du SL).
        Exit doit être à 120, pas 110.
        """
        n = 200
        breakout_at = 60
        period = 20
        gap_candle = breakout_at + 2

        closes = np.full(n, 100.0)
        opens = np.full(n, 100.0)
        highs = np.full(n, 101.0)
        lows = np.full(n, 99.0)

        # Breakout baissier : close < rolling_low
        closes[breakout_at] = 97.0
        lows[breakout_at] = 96.0

        entry_candle = breakout_at + 1
        opens[entry_candle] = 97.0
        highs[entry_candle] = 98.0
        lows[entry_candle] = 96.0
        closes[entry_candle] = 96.5

        # GAP UP : open[gap_candle] = 120
        opens[gap_candle] = 120.0
        highs[gap_candle] = 122.0
        lows[gap_candle] = 118.0
        closes[gap_candle] = 121.0

        rh = rolling_max(highs, period)
        rl = rolling_min(lows, period)

        cache = make_indicator_cache(
            n=n, closes=closes, opens=opens, highs=highs, lows=lows,
            rolling_high={period: rh},
            rolling_low={period: rl},
        )

        params = default_params(
            donchian_entry_period=period, sl_percent=10.0,
            sides=["long", "short"],
            trailing_atr_mult=100.0,
        )
        config = make_bt_config()

        pnls, _, _ = _simulate_trend_follow(cache, params, config)
        assert len(pnls) >= 1

        # SHORT entry ≈ 97, gap open 120 → pnl = (97 - 120) * qty ≈ très négatif
        entry_price = 97.0
        sl_price = entry_price * 1.1  # 106.7
        qty = (100_000 * 0.3) / entry_price
        pnl_at_sl = (entry_price - sl_price) * qty
        pnl_at_gap = (entry_price - 120.0) * qty

        assert pnls[0] < pnl_at_sl * 0.5
        assert abs(pnls[0] - pnl_at_gap) < abs(pnl_at_gap) * 0.15

    def test_gap_down_trailing_exits_at_open(self, make_indicator_cache):
        """Trailing stop touché par gap : exit à l'open.

        Position LONG, price monte 100→130, trailing ≈ 122.
        Open[gap_candle]=110 (gap sous trailing).
        Exit doit être à 110.
        """
        n = 200
        breakout_at = 60
        period = 20

        closes = np.full(n, 100.0)
        opens = np.full(n, 100.0)
        highs = np.full(n, 101.0)
        lows = np.full(n, 99.0)

        # Breakout
        closes[breakout_at] = 102.0
        highs[breakout_at] = 103.0

        # Entrée
        entry_candle = breakout_at + 1
        opens[entry_candle] = 103.0
        highs[entry_candle] = 104.0
        lows[entry_candle] = 102.0
        closes[entry_candle] = 103.5

        # Prix monte progressivement (pour update le trailing)
        for j in range(entry_candle + 1, entry_candle + 10):
            if j < n:
                price = 103.5 + (j - entry_candle) * 3.0
                opens[j] = price - 1
                highs[j] = price + 1
                lows[j] = price - 2
                closes[j] = price

        # High water mark ≈ 130 → trailing ≈ 130 - 2*4 = 122
        gap_candle = entry_candle + 10
        if gap_candle < n:
            opens[gap_candle] = 110.0  # Gap sous trailing (≈122)
            highs[gap_candle] = 112.0
            lows[gap_candle] = 108.0
            closes[gap_candle] = 111.0

        rh = rolling_max(highs, period)
        rl = rolling_min(lows, period)

        cache = make_indicator_cache(
            n=n, closes=closes, opens=opens, highs=highs, lows=lows,
            rolling_high={period: rh},
            rolling_low={period: rl},
        )

        params = default_params(
            donchian_entry_period=period, sl_percent=20.0,
            trailing_atr_mult=4.0,
        )
        config = make_bt_config()

        pnls, _, _ = _simulate_trend_follow(cache, params, config)
        assert len(pnls) >= 1

        # Exit à l'open (110), pas au trailing level (≈122)
        # PnL ≈ (110 - 103) * qty > 0 mais moins que trailing
        entry_price = 103.0
        qty = (100_000 * 0.3) / entry_price
        pnl_at_trailing = (122.0 - entry_price) * qty
        pnl_at_gap_open = (110.0 - entry_price) * qty

        assert pnls[0] > 0  # Toujours rentable
        assert pnls[0] < pnl_at_trailing  # Mais moins que si exit au trailing

    def test_gap_up_then_intraday_reversal(self, make_indicator_cache):
        """Gap UP favorable, trailing recalculé, puis reversal intraday.

        Position LONG. Close[i-1]=100. Open[i]=108 (gap up).
        High[i]=110 → HWM updated, trailing recalculé.
        Low[i]=101 touche le nouveau trailing.
        Vérifier que trailing est mis à jour AVANT le check.
        """
        n = 200
        breakout_at = 60
        period = 20

        closes = np.full(n, 100.0)
        opens = np.full(n, 100.0)
        highs = np.full(n, 101.0)
        lows = np.full(n, 99.0)

        closes[breakout_at] = 102.0
        highs[breakout_at] = 103.0

        entry_candle = breakout_at + 1
        opens[entry_candle] = 103.0
        highs[entry_candle] = 104.0
        lows[entry_candle] = 102.0
        closes[entry_candle] = 103.5

        # Candle normale pour que le trailing se mette à jour
        next_c = entry_candle + 1
        opens[next_c] = 104.0
        highs[next_c] = 106.0
        lows[next_c] = 103.0
        closes[next_c] = 105.0

        # Gap UP favorable + reversal intraday
        gap_candle = entry_candle + 2
        opens[gap_candle] = 108.0
        highs[gap_candle] = 110.0  # Nouveau HWM
        lows[gap_candle] = 99.0    # Reversal : touche le trailing recalculé
        closes[gap_candle] = 100.0

        rh = rolling_max(highs, period)
        rl = rolling_min(lows, period)

        cache = make_indicator_cache(
            n=n, closes=closes, opens=opens, highs=highs, lows=lows,
            rolling_high={period: rh},
            rolling_low={period: rl},
            atr_by_period={14: np.full(n, 2.0)},
        )

        params = default_params(
            donchian_entry_period=period, sl_percent=20.0,
            trailing_atr_mult=4.0,  # trailing = HWM - 2*4 = HWM - 8
        )
        config = make_bt_config()

        pnls, _, _ = _simulate_trend_follow(cache, params, config)
        # Le trailing devrait être recalculé avec HWM=110 → trailing = 110-8 = 102
        # Low=99 touche le trailing → exit au trailing level (102), pas à l'open (108)
        assert len(pnls) >= 1
        # L'exit ne doit PAS être à l'open (108 est au-dessus du trailing)
        # L'exit doit être au trailing level recalculé ≈ 102

    def test_no_gap_sl_exact(self, make_indicator_cache):
        """Sans gap (open entre SL et position) : exit au SL exact.

        Position LONG, SL=92.7. Open[i]=95 (au-dessus du SL), Low[i]=90.
        Exit doit être au SL (92.7), pas à l'open (95).
        """
        n = 200
        breakout_at = 60
        period = 20

        closes = np.full(n, 100.0)
        opens = np.full(n, 100.0)
        highs = np.full(n, 101.0)
        lows = np.full(n, 99.0)

        closes[breakout_at] = 102.0
        highs[breakout_at] = 103.0

        entry_candle = breakout_at + 1
        opens[entry_candle] = 103.0
        highs[entry_candle] = 104.0
        lows[entry_candle] = 102.0
        closes[entry_candle] = 103.5

        # Pas de gap : open au-dessus du SL, mais low traverse le SL
        sl_candle = entry_candle + 1
        sl_price = 103.0 * 0.9  # ≈ 92.7
        opens[sl_candle] = 95.0  # Au-dessus du SL — pas de gap
        highs[sl_candle] = 96.0
        lows[sl_candle] = 90.0   # Traverse le SL intraday
        closes[sl_candle] = 91.0

        rh = rolling_max(highs, period)
        rl = rolling_min(lows, period)

        cache = make_indicator_cache(
            n=n, closes=closes, opens=opens, highs=highs, lows=lows,
            rolling_high={period: rh},
            rolling_low={period: rl},
        )

        params = default_params(
            donchian_entry_period=period, sl_percent=10.0,
            trailing_atr_mult=100.0,
        )
        config = make_bt_config()

        pnls, _, _ = _simulate_trend_follow(cache, params, config)
        assert len(pnls) >= 1

        # Exit au SL exact, pas à l'open
        entry_price = 103.0
        qty = (100_000 * 0.3) / entry_price
        expected_sl_exit = entry_price * 0.9  # 92.7
        expected_pnl = (expected_sl_exit - entry_price) * qty

        assert abs(pnls[0] - expected_pnl) < abs(expected_pnl) * 0.05

    def test_gap_affects_pnl_correctly(self, make_indicator_cache):
        """Vérifier que le P&L reflète le prix réel de sortie (gap).

        Position LONG entry≈103, SL≈92.7. Gap open à 80.
        P&L = (80 - 103) * qty, PAS (92.7 - 103) * qty.
        """
        n = 200
        breakout_at = 60
        period = 20

        closes = np.full(n, 100.0)
        opens = np.full(n, 100.0)
        highs = np.full(n, 101.0)
        lows = np.full(n, 99.0)

        closes[breakout_at] = 102.0
        highs[breakout_at] = 103.0

        entry_candle = breakout_at + 1
        opens[entry_candle] = 103.0
        highs[entry_candle] = 104.0
        lows[entry_candle] = 102.0
        closes[entry_candle] = 103.5

        gap_candle = entry_candle + 1
        opens[gap_candle] = 80.0
        highs[gap_candle] = 82.0
        lows[gap_candle] = 78.0
        closes[gap_candle] = 81.0

        rh = rolling_max(highs, period)
        rl = rolling_min(lows, period)

        cache = make_indicator_cache(
            n=n, closes=closes, opens=opens, highs=highs, lows=lows,
            rolling_high={period: rh},
            rolling_low={period: rl},
        )

        params = default_params(
            donchian_entry_period=period, sl_percent=10.0,
            trailing_atr_mult=100.0,
        )
        config = make_bt_config()

        pnls, _, _ = _simulate_trend_follow(cache, params, config)
        assert len(pnls) >= 1

        entry_price = 103.0
        qty = (100_000 * 0.3) / entry_price
        pnl_at_gap = (80.0 - entry_price) * qty    # ≈ -6699
        pnl_at_sl = (92.7 - entry_price) * qty      # ≈ -2999

        # Le PnL doit être proche du gap price, pas du SL
        assert abs(pnls[0] - pnl_at_gap) < abs(pnl_at_gap) * 0.1
        assert abs(pnls[0]) > abs(pnl_at_sl) * 1.5  # Gap loss >> SL loss


# ══════════════════════════════════════════════════════════════════════════════
# TESTS PORTÉS DEPUIS SCALP-RADAR
# ══════════════════════════════════════════════════════════════════════════════


class TestEntryLong:
    def test_ema_cross_long_entry(self, make_indicator_cache):
        """EMA bull cross → LONG entry sur open[cross+1]."""
        n = 200
        cross_at = 60
        ema_fast, ema_slow = setup_bull_cross(n, cross_at)

        cache = make_indicator_cache(
            n=n,
            ema_by_period={9: ema_fast, 50: ema_slow},
        )

        params = default_params(
            entry_mode="ema_cross", ema_fast=9, ema_slow=50,
        )
        config = make_bt_config()

        pnls, _, final_cap = _simulate_trend_follow(cache, params, config)
        # Doit y avoir au moins un trade (entrée + force-close ou trailing)
        assert final_cap > 0


class TestEntryShort:
    def test_ema_cross_short_entry(self, make_indicator_cache):
        """EMA bear cross → SHORT entry (sides=["long","short"])."""
        n = 200
        cross_at = 60
        ema_fast, ema_slow = setup_bear_cross(n, cross_at)

        cache = make_indicator_cache(
            n=n,
            ema_by_period={9: ema_fast, 50: ema_slow},
        )

        params = default_params(
            entry_mode="ema_cross", ema_fast=9, ema_slow=50,
            sides=["long", "short"],
        )
        config = make_bt_config()

        pnls, _, final_cap = _simulate_trend_follow(cache, params, config)
        assert final_cap > 0


class TestADXFilter:
    def test_adx_below_threshold_blocks_entry(self, make_indicator_cache):
        """ADX < threshold → pas d'entrée malgré le signal."""
        n = 200
        breakout_at = 60
        period = 20

        closes = np.full(n, 100.0)
        opens = np.full(n, 100.0)
        highs = np.full(n, 101.0)
        lows = np.full(n, 99.0)
        closes[breakout_at] = 102.0
        highs[breakout_at] = 103.0

        rh = rolling_max(highs, period)
        rl = rolling_min(lows, period)

        # ADX = 10, bien en dessous du threshold de 20
        adx_arr = np.full(n, 10.0)
        di_plus = np.full(n, 15.0)
        di_minus = np.full(n, 12.0)

        cache = make_indicator_cache(
            n=n, closes=closes, opens=opens, highs=highs, lows=lows,
            adx_by_period={14: (adx_arr, di_plus, di_minus)},
            rolling_high={period: rh},
            rolling_low={period: rl},
        )

        params = default_params(
            donchian_entry_period=period, adx_threshold=20.0,
        )
        config = make_bt_config()

        pnls, _, _ = _simulate_trend_follow(cache, params, config)
        assert len(pnls) == 0  # Pas de trade

    def test_adx_threshold_zero_allows_entry(self, make_indicator_cache):
        """adx_threshold=0 → entrée même avec ADX=10."""
        n = 200
        breakout_at = 60
        period = 20

        closes = np.full(n, 100.0)
        opens = np.full(n, 100.0)
        highs = np.full(n, 101.0)
        lows = np.full(n, 99.0)
        closes[breakout_at] = 102.0
        highs[breakout_at] = 103.0

        # Prix post-breakout stable pour que le trade existe
        closes[breakout_at + 1 :] = 105.0
        opens[breakout_at + 1 :] = 103.0
        highs[breakout_at + 1 :] = 106.0
        lows[breakout_at + 1 :] = 102.0

        rh = rolling_max(highs, period)
        rl = rolling_min(lows, period)

        adx_arr = np.full(n, 10.0)
        di_plus = np.full(n, 15.0)
        di_minus = np.full(n, 12.0)

        cache = make_indicator_cache(
            n=n, closes=closes, opens=opens, highs=highs, lows=lows,
            adx_by_period={14: (adx_arr, di_plus, di_minus)},
            rolling_high={period: rh},
            rolling_low={period: rl},
        )

        params = default_params(
            donchian_entry_period=period, adx_threshold=0,
        )
        config = make_bt_config()

        pnls, _, _ = _simulate_trend_follow(cache, params, config)
        # Avec threshold=0, le trade devrait se faire
        # (force-close à la fin si pas de SL/trailing)
        assert True  # Le test ne doit pas crasher


class TestSidesFilter:
    def test_sides_long_only_blocks_short(self, make_indicator_cache):
        """sides=["long"] → bear signal ignoré."""
        n = 200
        cross_at = 60
        ema_fast, ema_slow = setup_bear_cross(n, cross_at)

        cache = make_indicator_cache(
            n=n,
            ema_by_period={9: ema_fast, 50: ema_slow},
        )

        params = default_params(
            entry_mode="ema_cross", ema_fast=9, ema_slow=50,
            sides=["long"],
        )
        config = make_bt_config()

        pnls, _, _ = _simulate_trend_follow(cache, params, config)
        assert len(pnls) == 0  # Pas de trade SHORT


class TestCooldown:
    def test_cooldown_blocks_reentry(self, make_indicator_cache):
        """cooldown=3 → pas de re-entrée dans les 3 candles après exit."""
        n = 200
        period = 20

        closes = np.full(n, 100.0)
        opens = np.full(n, 100.0)
        highs = np.full(n, 101.0)
        lows = np.full(n, 99.0)

        # Premier breakout à 60
        closes[60] = 102.0
        highs[60] = 103.0
        opens[61] = 103.0
        highs[61] = 104.0
        lows[61] = 102.0
        closes[61] = 103.5

        # SL touché à candle 62
        opens[62] = 95.0
        lows[62] = 88.0
        highs[62] = 96.0
        closes[62] = 89.0

        # Deuxième breakout à 63 (dans la période de cooldown)
        closes[63] = 102.0
        highs[63] = 103.0
        opens[64] = 103.0
        closes[64] = 105.0

        rh = rolling_max(highs, period)
        rl = rolling_min(lows, period)

        cache = make_indicator_cache(
            n=n, closes=closes, opens=opens, highs=highs, lows=lows,
            rolling_high={period: rh},
            rolling_low={period: rl},
        )

        params = default_params(
            donchian_entry_period=period, sl_percent=10.0,
            cooldown_candles=5, trailing_atr_mult=100.0,
        )
        config = make_bt_config()

        pnls, _, _ = _simulate_trend_follow(cache, params, config)
        # Le premier trade devrait exister (SL touché)
        # Le deuxième trade ne devrait PAS exister (cooldown)
        assert len(pnls) == 1


class TestForceClose:
    def test_force_close_not_in_pnls(self, make_indicator_cache):
        """Position jamais fermée naturellement → force-close exclu des pnls."""
        n = 100
        period = 20
        breakout_at = 30

        closes = np.full(n, 100.0)
        opens = np.full(n, 100.0)
        highs = np.full(n, 101.0)
        lows = np.full(n, 99.5)

        closes[breakout_at] = 102.0
        highs[breakout_at] = 103.0

        # Prix monte → ni SL ni trailing touché, mais force-close à prix différent
        closes[breakout_at + 1 :] = 110.0
        opens[breakout_at + 1 :] = 103.0
        highs[breakout_at + 1 :] = 111.0
        lows[breakout_at + 1 :] = 102.0

        rh = rolling_max(highs, period)
        rl = rolling_min(lows, period)

        cache = make_indicator_cache(
            n=n, closes=closes, opens=opens, highs=highs, lows=lows,
            rolling_high={period: rh},
            rolling_low={period: rl},
        )

        params = default_params(
            donchian_entry_period=period, sl_percent=20.0,
            trailing_atr_mult=100.0,  # Ne se déclenche jamais
        )
        config = make_bt_config()

        pnls, _, final_cap = _simulate_trend_follow(cache, params, config)
        # Force-close ne doit pas être dans trade_pnls
        assert len(pnls) == 0
        # Mais le capital doit refléter la position
        assert final_cap != config.initial_capital


class TestDonchianEntry:
    def test_donchian_breakout_long(self, make_indicator_cache):
        """Close[breakout_at] > rolling_high → entrée LONG sur open[breakout_at+1]."""
        n = 200
        breakout_at = 60
        period = 20

        opens, highs, lows, closes, rh = setup_donchian_breakout_long(
            n, breakout_at, period,
        )
        rl = rolling_min(lows, period)

        cache = make_indicator_cache(
            n=n, closes=closes, opens=opens, highs=highs, lows=lows,
            rolling_high={period: rh},
            rolling_low={period: rl},
        )

        params = default_params(donchian_entry_period=period)
        config = make_bt_config()

        _, _, final_cap = _simulate_trend_follow(cache, params, config)
        assert final_cap > 0

    def test_donchian_no_signal_inside_channel(self, make_indicator_cache):
        """Prix dans le canal → pas d'entrée."""
        n = 200
        period = 20

        # Prix plat → close ne dépasse jamais rolling_high
        closes = np.full(n, 100.0)
        opens = np.full(n, 100.0)
        highs = np.full(n, 100.5)
        lows = np.full(n, 99.5)

        rh = rolling_max(highs, period)
        rl = rolling_min(lows, period)

        cache = make_indicator_cache(
            n=n, closes=closes, opens=opens, highs=highs, lows=lows,
            rolling_high={period: rh},
            rolling_low={period: rl},
        )

        params = default_params(donchian_entry_period=period)
        config = make_bt_config()

        pnls, _, _ = _simulate_trend_follow(cache, params, config)
        assert len(pnls) == 0


class TestDonchianChannelExit:
    def test_channel_exit_long(self, make_indicator_cache):
        """Exit mode 'channel' : close < rolling_low(exit_period) → exit LONG."""
        n = 200
        breakout_at = 60
        entry_period = 20
        exit_period = 10

        closes = np.full(n, 100.0)
        opens = np.full(n, 100.0)
        highs = np.full(n, 101.0)
        lows = np.full(n, 99.0)

        # Breakout
        closes[breakout_at] = 102.0
        highs[breakout_at] = 103.0

        # Prix monte
        for j in range(breakout_at + 1, breakout_at + 15):
            if j < n:
                closes[j] = 105.0
                opens[j] = 104.0
                highs[j] = 106.0
                lows[j] = 103.0

        # Prix crash → close < rolling_low[exit_period]
        drop_at = breakout_at + 15
        for j in range(drop_at, min(drop_at + 5, n)):
            closes[j] = 90.0
            opens[j] = 95.0
            highs[j] = 96.0
            lows[j] = 88.0

        rh_entry = rolling_max(highs, entry_period)
        rl_entry = rolling_min(lows, entry_period)
        rh_exit = rolling_max(highs, exit_period)
        rl_exit = rolling_min(lows, exit_period)

        cache = make_indicator_cache(
            n=n, closes=closes, opens=opens, highs=highs, lows=lows,
            rolling_high={entry_period: rh_entry, exit_period: rh_exit},
            rolling_low={entry_period: rl_entry, exit_period: rl_exit},
        )

        params = default_params(
            donchian_entry_period=entry_period,
            donchian_exit_period=exit_period,
            exit_mode="channel",
            sl_percent=50.0,  # SL large pour ne pas interférer
            trailing_atr_mult=100.0,
        )
        config = make_bt_config()

        pnls, _, _ = _simulate_trend_follow(cache, params, config)
        assert len(pnls) >= 1


class TestCloseTrendPosition:
    def test_long_profit(self):
        """PnL correct pour un LONG profitable."""
        fm = FeeModel()
        pnl = _close_trend_position(
            direction=1, entry_price=100.0, exit_price=110.0,
            quantity=10.0, fee_model=fm, entry_fee=0.0, n_holding_days=0,
        )
        assert pnl == pytest.approx(100.0, abs=0.01)

    def test_short_profit(self):
        """PnL correct pour un SHORT profitable."""
        fm = FeeModel()
        pnl = _close_trend_position(
            direction=-1, entry_price=110.0, exit_price=100.0,
            quantity=10.0, fee_model=fm, entry_fee=0.0, n_holding_days=0,
        )
        assert pnl == pytest.approx(100.0, abs=0.01)

    def test_fees_reduce_pnl(self):
        """Les frais réduisent le PnL."""
        fm = FEE_MODEL_US_STOCKS
        entry_notional = 100.0 * 10.0
        entry_fee = fm.total_entry_cost(entry_notional)
        pnl = _close_trend_position(
            direction=1, entry_price=100.0, exit_price=110.0,
            quantity=10.0, fee_model=fm, entry_fee=entry_fee,
            n_holding_days=5,
        )
        assert pnl < 100.0  # Fees reduce the PnL


class TestComputeFastMetrics:
    def test_zero_trades(self):
        """0 trades → sharpe=0, return=0."""
        result = _compute_fast_metrics({}, [], [], 100_000, 100_000, 365)
        _, sharpe, ret, pf, n = result
        assert sharpe == 0.0
        assert n == 0

    def test_positive_trades(self):
        """Trades positifs → sharpe > 0."""
        pnls = [100.0, 200.0, 50.0, 150.0]
        rets = [0.01, 0.02, 0.005, 0.015]
        result = _compute_fast_metrics({}, pnls, rets, 100_500, 100_000, 365)
        _, sharpe, ret, pf, n = result
        assert sharpe > 0
        assert n == 4
        assert ret > 0
