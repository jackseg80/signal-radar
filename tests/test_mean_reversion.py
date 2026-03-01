"""Tests unitaires pour le moteur mean reversion RSI(2) Connors.

Couvre : indicateur RSI, logique entry/exit, trend filter, anti-look-ahead,
gap-aware SL, force-close, cooldown, SMA buffer, no double entry.

Pattern de test : SMA et RSI sont injectés en tant qu'arrays synthétiques
contrôlés dans le cache (même approche que les tests trend following avec
EMA/ADX). Les tests RSI indicateur vérifient séparément que rsi() calcule
correctement.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from engine.indicators import rsi, sma
from engine.mean_reversion_backtest import _simulate_mean_reversion
from tests.conftest import make_bt_config


# ── Helper ──────────────────────────────────────────────────────────────────


def mr_params(**overrides: object) -> dict:
    """Params mean reversion par défaut pour les tests (périodes courtes)."""
    defaults: dict = {
        "strategy_type": "mean_reversion",
        "rsi_period": 2,
        "rsi_entry_threshold": 10.0,
        "sma_trend_period": 5,
        "sma_exit_period": 3,
        "rsi_exit_threshold": 0.0,
        "sl_percent": 0.0,
        "position_fraction": 0.2,
        "cooldown_candles": 0,
        "sma_trend_buffer": 1.0,
    }
    defaults.update(overrides)
    return defaults


# ── Tests RSI indicateur ────────────────────────────────────────────────────


class TestRSIIndicator:
    """Tests de la fonction rsi() dans engine/indicators.py."""

    def test_rsi_basic_values(self) -> None:
        """RSI(2) sur séquence connue, valeurs calculées à la main."""
        closes = np.array([100.0, 101.0, 99.0, 98.0, 100.0, 102.0, 101.0, 103.0])
        result = rsi(closes, period=2)

        # Les 2 premières valeurs sont NaN
        assert math.isnan(result[0])
        assert math.isnan(result[1])
        # Valeur au seed (index 2) est valide
        assert not math.isnan(result[2])

        # Calcul à la main pour period=2 :
        # deltas = [+1, -2, -1, +2, +2, -1, +2]
        # gains  = [ 1,  0,  0,  2,  2,  0,  2]
        # losses = [ 0,  2,  1,  0,  0,  1,  0]
        # Seed: avg_gain = mean(1, 0) = 0.5, avg_loss = mean(0, 2) = 1.0
        # result[2] = 100 - 100/(1 + 0.5/1.0) = 33.33
        assert result[2] == pytest.approx(33.33, abs=0.1)

        # index 3: gains[2]=0, losses[2]=1
        # avg_gain = (0.5*1 + 0)/2 = 0.25
        # avg_loss = (1.0*1 + 1)/2 = 1.0
        # RS = 0.25 -> RSI = 100 - 100/1.25 = 20.0
        assert result[3] == pytest.approx(20.0, abs=0.1)

        # Toutes les valeurs valides dans [0, 100]
        valid = result[~np.isnan(result)]
        assert np.all(valid >= 0.0)
        assert np.all(valid <= 100.0)

    def test_rsi2_extreme_values(self) -> None:
        """RSI ∈ [0, 100], NaN avant period, array court → tout NaN."""
        # Array trop court
        short = np.array([100.0, 101.0])
        result_short = rsi(short, period=2)
        assert all(math.isnan(v) for v in result_short)

        # Montée constante → RSI proche de 100
        rising = np.array([100.0, 101.0, 102.0, 103.0, 104.0, 105.0])
        result_rising = rsi(rising, period=2)
        valid = result_rising[~np.isnan(result_rising)]
        assert np.all(valid >= 0.0)
        assert np.all(valid <= 100.0)
        assert valid[-1] > 90.0

        # Baisse constante → RSI proche de 0
        falling = np.array([105.0, 104.0, 103.0, 102.0, 101.0, 100.0])
        result_falling = rsi(falling, period=2)
        valid_f = result_falling[~np.isnan(result_falling)]
        assert np.all(valid_f >= 0.0)
        assert np.all(valid_f <= 100.0)
        assert valid_f[-1] < 10.0


# ── Tests backtest mean reversion ───────────────────────────────────────────
#
# Les tests injectent des SMA/RSI synthétiques pour contrôler précisément
# les conditions d'entrée/sortie, comme les tests trend following injectent
# des EMA/ADX synthétiques.
# ────────────────────────────────────────────────────────────────────────────


class TestMeanReversionEntry:
    """Tests entry conditions."""

    def test_entry_on_rsi_below_threshold(self, make_indicator_cache) -> None:  # type: ignore[no-untyped-def]
        """RSI < seuil + uptrend → entry sur next open, au moins 1 trade."""
        n = 50
        signal_at = 20  # RSI signal on this candle, entry on signal_at + 1

        closes = np.full(n, 100.0)
        opens = np.full(n, 100.0)
        # Post-entry : close monte pour trigger SMA exit
        closes[signal_at + 1 :] = 105.0
        opens[signal_at + 1] = 100.0  # Entry open
        opens[signal_at + 2 :] = 105.0

        highs = np.maximum(opens, closes) + 1.0
        lows = np.minimum(opens, closes) - 1.0

        # SMA trend : toujours sous closes → trend OK
        sma_trend = np.full(n, 95.0)
        # SMA exit : sous closes, sauf post-entry où close > sma_exit
        sma_exit = np.full(n, 98.0)
        sma_exit[signal_at + 1 :] = 102.0  # close(105) > sma_exit(102) → exit

        # RSI : dip au signal_at
        rsi_arr = np.full(n, 50.0)
        rsi_arr[signal_at] = 3.0  # < threshold 10

        cache = make_indicator_cache(
            n=n, closes=closes, opens=opens, highs=highs, lows=lows,
            sma_by_period={5: sma_trend, 3: sma_exit},
            rsi_by_period={2: rsi_arr},
        )

        params = mr_params()
        config = make_bt_config()

        pnls, _, _ = _simulate_mean_reversion(cache, params, config)
        assert len(pnls) >= 1
        # Entry at 100, exit at close(105) → profit
        assert pnls[0] > 0

    def test_no_entry_above_threshold(self, make_indicator_cache) -> None:  # type: ignore[no-untyped-def]
        """RSI > seuil → pas d'entry."""
        n = 50
        closes = np.full(n, 100.0)
        opens = np.full(n, 100.0)
        highs = closes + 1.0
        lows = closes - 1.0

        sma_trend = np.full(n, 95.0)  # Trend OK
        sma_exit = np.full(n, 98.0)
        rsi_arr = np.full(n, 50.0)  # Toujours au-dessus du threshold (10)

        cache = make_indicator_cache(
            n=n, closes=closes, opens=opens, highs=highs, lows=lows,
            sma_by_period={5: sma_trend, 3: sma_exit},
            rsi_by_period={2: rsi_arr},
        )

        params = mr_params()
        config = make_bt_config()

        pnls, _, _ = _simulate_mean_reversion(cache, params, config)
        assert len(pnls) == 0

    def test_trend_filter_blocks_entry(self, make_indicator_cache) -> None:  # type: ignore[no-untyped-def]
        """Close < SMA trend → pas d'entry même si RSI bas."""
        n = 50
        closes = np.full(n, 100.0)
        opens = np.full(n, 100.0)
        highs = closes + 1.0
        lows = closes - 1.0

        # SMA trend AU-DESSUS des closes → trend filter bloque
        sma_trend = np.full(n, 110.0)
        sma_exit = np.full(n, 98.0)
        # RSI très bas → voudrait entrer
        rsi_arr = np.full(n, 3.0)

        cache = make_indicator_cache(
            n=n, closes=closes, opens=opens, highs=highs, lows=lows,
            sma_by_period={5: sma_trend, 3: sma_exit},
            rsi_by_period={2: rsi_arr},
        )

        params = mr_params()
        config = make_bt_config()

        pnls, _, _ = _simulate_mean_reversion(cache, params, config)
        assert len(pnls) == 0


class TestMeanReversionExit:
    """Tests exit conditions."""

    def test_exit_on_close_above_sma5(self, make_indicator_cache) -> None:  # type: ignore[no-untyped-def]
        """Close > SMA(exit) → exit at close, y compris entry-day exit."""
        n = 50
        signal_at = 20
        entry_day = signal_at + 1

        closes = np.full(n, 100.0)
        opens = np.full(n, 100.0)
        # Entry day: close remonte → exit at close le même jour
        opens[entry_day] = 98.0  # Entry open (bas)
        closes[entry_day] = 105.0  # Close haut → > sma_exit → exit

        highs = np.maximum(opens, closes) + 1.0
        lows = np.minimum(opens, closes) - 1.0

        sma_trend = np.full(n, 90.0)  # Toujours sous closes → trend OK
        sma_exit = np.full(n, 103.0)  # close(105) > 103 → exit at close
        rsi_arr = np.full(n, 50.0)
        rsi_arr[signal_at] = 3.0  # Signal RSI

        cache = make_indicator_cache(
            n=n, closes=closes, opens=opens, highs=highs, lows=lows,
            sma_by_period={5: sma_trend, 3: sma_exit},
            rsi_by_period={2: rsi_arr},
        )

        params = mr_params()
        config = make_bt_config()

        pnls, _, _ = _simulate_mean_reversion(cache, params, config)
        assert len(pnls) == 1
        # Entry at 98, exit at close 105 → profit
        assert pnls[0] > 0

    def test_exit_on_trend_break(self, make_indicator_cache) -> None:  # type: ignore[no-untyped-def]
        """Close < SMA(trend) → safety exit at close."""
        n = 50
        signal_at = 20
        entry_day = signal_at + 1

        closes = np.full(n, 100.0)
        opens = np.full(n, 100.0)
        opens[entry_day] = 100.0

        # Entry day: close crash sous SMA trend → trend break exit
        closes[entry_day] = 85.0

        highs = np.maximum(opens, closes) + 1.0
        lows = np.minimum(opens, closes) - 1.0

        sma_trend = np.full(n, 95.0)  # close(85) < 95 → trend break
        sma_exit = np.full(n, 110.0)  # close(85) < 110 → SMA exit pas trigger
        rsi_arr = np.full(n, 50.0)
        rsi_arr[signal_at] = 3.0

        cache = make_indicator_cache(
            n=n, closes=closes, opens=opens, highs=highs, lows=lows,
            sma_by_period={5: sma_trend, 3: sma_exit},
            rsi_by_period={2: rsi_arr},
        )

        params = mr_params()
        config = make_bt_config()

        pnls, _, _ = _simulate_mean_reversion(cache, params, config)
        assert len(pnls) == 1
        # Entry at 100, exit at close 85 → perte
        assert pnls[0] < 0


class TestMeanReversionAntiLookAhead:
    """Tests anti-look-ahead."""

    def test_no_look_ahead(self, make_indicator_cache) -> None:  # type: ignore[no-untyped-def]
        """Signal sur [i-1], pas [i]. L'engine utilise RSI[i-1] pour l'entry."""
        n = 50
        closes = np.full(n, 100.0)
        opens = np.full(n, 100.0)
        closes[26:] = 105.0  # Post-signal: prix monte
        opens[26] = 100.0
        opens[27] = 101.0

        highs = np.maximum(opens, closes) + 1.0
        lows = np.minimum(opens, closes) - 1.0

        sma_trend = np.full(n, 90.0)
        sma_exit = np.full(n, 103.0)  # close(105) > 103 → exit
        rsi_arr = np.full(n, 50.0)  # RSI normal partout

        # RSI[25] = 50 (au-dessus du threshold) → PAS de signal
        # RSI[26] = 3 (en dessous) → signal, entry sur opens[27]
        rsi_arr[26] = 3.0

        cache = make_indicator_cache(
            n=n, closes=closes, opens=opens, highs=highs, lows=lows,
            sma_by_period={5: sma_trend, 3: sma_exit},
            rsi_by_period={2: rsi_arr},
        )

        params = mr_params()
        config = make_bt_config()

        pnls, _, _ = _simulate_mean_reversion(cache, params, config)
        # Trade doit exister (signal RSI[26], entry opens[27])
        assert len(pnls) >= 1
        # Si look-ahead existait (RSI[i] au lieu de RSI[i-1]),
        # l'engine entrerait sur opens[26] = 100, pas opens[27] = 101.
        # Le PnL avec entry=101 est plus petit qu'avec entry=100.
        # On vérifie que le PnL est cohérent avec entry ~101, exit ~105.
        qty = (100_000 * 0.2) / 101.0
        expected_pnl = (105.0 - 101.0) * qty
        assert abs(pnls[0] - expected_pnl) < expected_pnl * 0.1


class TestMeanReversionGapSL:
    """Tests gap-aware SL."""

    def test_gap_aware_sl_exits_at_open(self, make_indicator_cache) -> None:  # type: ignore[no-untyped-def]
        """sl_percent > 0 + gap → exit at open, pas au SL."""
        n = 50
        signal_at = 20
        entry_day = signal_at + 1
        gap_day = entry_day + 1

        closes = np.full(n, 100.0)
        opens = np.full(n, 100.0)
        opens[entry_day] = 100.0  # Entry at 100
        closes[entry_day] = 101.0  # Survive entry day

        # Gap DOWN through SL on gap_day
        # SL = 100 * (1 - 0.05) = 95
        opens[gap_day] = 80.0  # Gap bien en dessous du SL
        closes[gap_day] = 82.0
        closes[gap_day + 1 :] = 82.0

        highs = np.maximum(opens, closes) + 1.0
        lows = np.minimum(opens, closes) - 1.0
        lows[gap_day] = 78.0

        sma_trend = np.full(n, 90.0)
        # SMA exit haute pour ne pas trigger avant le gap
        sma_exit = np.full(n, 110.0)
        rsi_arr = np.full(n, 50.0)
        rsi_arr[signal_at] = 3.0

        cache = make_indicator_cache(
            n=n, closes=closes, opens=opens, highs=highs, lows=lows,
            sma_by_period={5: sma_trend, 3: sma_exit},
            rsi_by_period={2: rsi_arr},
        )

        params = mr_params(sl_percent=5.0)
        config = make_bt_config()

        pnls, _, _ = _simulate_mean_reversion(cache, params, config)
        assert len(pnls) == 1
        # Exit at open (80), not at SL (95)
        entry_p = 100.0
        qty = (100_000.0 * 0.2) / entry_p
        pnl_at_sl = (95.0 - entry_p) * qty  # -1000
        pnl_at_gap = (80.0 - entry_p) * qty  # -4000
        # PnL doit être proche du gap exit, pas du SL
        assert pnls[0] < pnl_at_sl * 1.5  # Bien pire que le SL


class TestMeanReversionMisc:
    """Tests divers : force-close, cooldown, buffer, no double entry."""

    def test_force_close_excluded(self, make_indicator_cache) -> None:  # type: ignore[no-untyped-def]
        """Position ouverte à la fin → pas dans trade_pnls."""
        n = 30
        signal_at = 10
        entry_day = signal_at + 1

        closes = np.full(n, 100.0)
        opens = np.full(n, 100.0)
        opens[entry_day] = 100.0
        # Close reste sous SMA exit et au-dessus SMA trend → pas d'exit
        closes[entry_day:] = 100.0

        highs = closes + 1.0
        lows = closes - 1.0

        sma_trend = np.full(n, 90.0)  # close(100) > 90 → pas de trend break
        sma_exit = np.full(n, 110.0)  # close(100) < 110 → SMA exit pas trigger
        rsi_arr = np.full(n, 50.0)
        rsi_arr[signal_at] = 3.0

        cache = make_indicator_cache(
            n=n, closes=closes, opens=opens, highs=highs, lows=lows,
            sma_by_period={5: sma_trend, 3: sma_exit},
            rsi_by_period={2: rsi_arr},
        )

        params = mr_params()
        config = make_bt_config()

        pnls, _, final_cap = _simulate_mean_reversion(cache, params, config)
        # Position ouverte à la fin → force-close exclue de trade_pnls
        assert len(pnls) == 0
        # Mais le capital reflète la force-close (entry à 100, exit à 100)
        # Avec zero fees, capital devrait être quasiment inchangé
        assert final_cap == pytest.approx(config.initial_capital, rel=0.01)

    def test_sma_buffer(self, make_indicator_cache) -> None:  # type: ignore[no-untyped-def]
        """sma_trend_buffer=1.05 → bloque entry quand close est juste au-dessus de SMA."""
        n = 50
        signal_at = 20

        closes = np.full(n, 100.0)
        opens = np.full(n, 100.0)
        closes[signal_at + 1 :] = 105.0
        opens[signal_at + 1 :] = 105.0

        highs = np.maximum(opens, closes) + 1.0
        lows = np.minimum(opens, closes) - 1.0

        # SMA trend à 98 → close(100) > 98 OK sans buffer
        # Mais avec buffer 1.05 : close(100) > 98 * 1.05 = 102.9 ? Non !
        sma_trend = np.full(n, 98.0)
        sma_exit = np.full(n, 103.0)
        rsi_arr = np.full(n, 50.0)
        rsi_arr[signal_at] = 3.0

        cache = make_indicator_cache(
            n=n, closes=closes, opens=opens, highs=highs, lows=lows,
            sma_by_period={5: sma_trend, 3: sma_exit},
            rsi_by_period={2: rsi_arr},
        )
        config = make_bt_config()

        # Sans buffer : close(100) > sma(98) * 1.0 = 98 → entry OK
        params_no = mr_params(sma_trend_buffer=1.0)
        pnls_no, _, _ = _simulate_mean_reversion(cache, params_no, config)
        assert len(pnls_no) >= 1

        # Avec buffer 1.05 : close(100) > sma(98) * 1.05 = 102.9 → BLOQUÉ
        params_buf = mr_params(sma_trend_buffer=1.05)
        pnls_buf, _, _ = _simulate_mean_reversion(cache, params_buf, config)
        assert len(pnls_buf) == 0

    def test_no_double_entry(self, make_indicator_cache) -> None:  # type: ignore[no-untyped-def]
        """RSI < seuil 2 jours de suite, déjà en position → pas de 2ème entry."""
        n = 50
        signal_at = 20

        closes = np.full(n, 100.0)
        opens = np.full(n, 100.0)
        opens[signal_at + 1] = 100.0  # Entry day
        # Close reste flat → pas d'exit (close < sma_exit, close > sma_trend)
        closes[signal_at + 3 :] = 105.0  # Exit éventuel plus tard

        highs = closes + 1.0
        lows = closes - 1.0

        sma_trend = np.full(n, 90.0)
        sma_exit = np.full(n, 103.0)
        rsi_arr = np.full(n, 50.0)
        # RSI < threshold sur 2 candles consécutives
        rsi_arr[signal_at] = 3.0      # Signal 1 → entry on signal_at+1
        rsi_arr[signal_at + 1] = 2.0  # Signal 2 → mais déjà en position !

        cache = make_indicator_cache(
            n=n, closes=closes, opens=opens, highs=highs, lows=lows,
            sma_by_period={5: sma_trend, 3: sma_exit},
            rsi_by_period={2: rsi_arr},
        )

        params = mr_params()
        config = make_bt_config()

        pnls, _, _ = _simulate_mean_reversion(cache, params, config)
        # Un seul trade, pas deux (le 2ème signal est ignoré)
        assert len(pnls) <= 1
