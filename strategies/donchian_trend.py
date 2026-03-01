"""Stratégie Donchian Trend Following pour signal-radar.

Supporte deux modes d'entrée (donchian breakout, ema cross) et trois
modes de sortie (trailing ATR, channel, signal reverse).

Logique portée depuis engine/fast_backtest.py._simulate_trend_follow()
"""

from __future__ import annotations

import math
from typing import Any

from engine.indicator_cache import IndicatorCache
from engine.types import Direction, ExitSignal, Position
from strategies.base import BaseStrategy


class DonchianTrend(BaseStrategy):
    """Trend Following — Donchian breakout ou EMA cross."""

    name = "donchian_trend"

    def default_params(self) -> dict[str, Any]:
        return {
            "entry_mode": "donchian",
            "donchian_entry_period": 50,
            "donchian_exit_period": 20,
            "ema_fast": 9,
            "ema_slow": 50,
            "adx_period": 14,
            "adx_threshold": 20.0,
            "atr_period": 14,
            "trailing_atr_mult": 4.0,
            "exit_mode": "trailing",
            "sl_percent": 10.0,
            "cooldown_candles": 3,
            "position_fraction": 0.3,
            "sides": ["long"],
        }

    def param_grid(self) -> dict[str, list]:
        return {
            "donchian_entry_period": [20, 50, 80],
            "donchian_exit_period": [10, 20],
            "adx_period": [14],
            "adx_threshold": [15, 20, 25],
            "atr_period": [14],
            "trailing_atr_mult": [3.0, 4.0, 5.0],
        }

    def warmup(self, params: dict) -> int:
        """Warmup adapté au mode d'entrée."""
        entry_mode = params.get("entry_mode", "donchian")
        adx_period: int = params.get("adx_period", 14)

        if entry_mode == "ema_cross":
            ema_slow: int = params.get("ema_slow", 50)
            return max(ema_slow, adx_period * 2) + 2
        else:
            donchian_entry_period: int = params.get("donchian_entry_period", 50)
            donchian_exit_period: int = params.get("donchian_exit_period", 20)
            exit_mode = params.get("exit_mode", "trailing")
            return max(
                donchian_entry_period,
                donchian_exit_period if exit_mode == "channel" else 0,
                adx_period * 2,
            ) + 2

    def check_entry(self, i: int, cache: IndicatorCache, params: dict) -> Direction:
        """Entry sur candle [i-1], action sur open[i]."""
        prev = i - 1
        entry_mode = params.get("entry_mode", "donchian")
        adx_threshold: float = params.get("adx_threshold", 20.0)
        adx_period: int = params.get("adx_period", 14)
        sides: list[str] = params.get("sides", ["long"])

        # ADX filter
        if adx_threshold > 0:
            adx_tuple = cache.adx_by_period.get(adx_period)
            if adx_tuple is not None:
                adx_val = adx_tuple[0][prev]
                if math.isnan(adx_val) or adx_val < adx_threshold:
                    return Direction.FLAT

        bull_signal = False
        bear_signal = False

        if entry_mode == "ema_cross":
            ema_fast_period: int = params.get("ema_fast", 9)
            ema_slow_period: int = params.get("ema_slow", 50)
            ema_fast = cache.ema_by_period[ema_fast_period]
            ema_slow = cache.ema_by_period[ema_slow_period]

            ef_prev = ema_fast[prev]
            es_prev = ema_slow[prev]
            ef_prev2 = ema_fast[prev - 1]
            es_prev2 = ema_slow[prev - 1]
            if math.isnan(ef_prev) or math.isnan(es_prev) or math.isnan(ef_prev2) or math.isnan(es_prev2):
                return Direction.FLAT

            bull_signal = ef_prev > es_prev and ef_prev2 <= es_prev2
            bear_signal = ef_prev < es_prev and ef_prev2 >= es_prev2

        else:  # donchian
            donchian_entry_period: int = params.get("donchian_entry_period", 50)
            rh = cache.rolling_high[donchian_entry_period][prev]
            rl = cache.rolling_low[donchian_entry_period][prev]
            if math.isnan(rh) or math.isnan(rl):
                return Direction.FLAT

            close_prev = cache.closes[prev]
            bull_signal = close_prev > rh
            bear_signal = close_prev < rl

        if bull_signal and "long" in sides:
            return Direction.LONG
        if bear_signal and "short" in sides:
            return Direction.SHORT
        return Direction.FLAT

    def check_exit(
        self, i: int, cache: IndicatorCache, params: dict, position: Position,
    ) -> ExitSignal | None:
        """Exits TF — trailing, channel, ou signal reverse."""
        exit_mode = params.get("exit_mode", "trailing")
        entry_mode = params.get("entry_mode", "donchian")
        direction = position.direction

        # Enforce: channel exit only with donchian entry
        if exit_mode == "channel" and entry_mode != "donchian":
            exit_mode = "trailing"

        # ── Trailing stop ──
        if exit_mode == "trailing":
            return self._check_trailing_exit(i, cache, params, position)

        # ── Channel exit ──
        if exit_mode == "channel":
            # Trailing check first (if active in state)
            trailing_result = self._check_trailing_exit(i, cache, params, position)
            if trailing_result is not None:
                return trailing_result

            # Channel exit (only after entry day)
            if i > position.entry_candle:
                donchian_exit_period: int = params.get("donchian_exit_period", 20)
                prev = i - 1
                close_i = cache.closes[i]
                if direction == Direction.LONG:
                    ch = cache.rolling_low[donchian_exit_period][prev]
                    if not math.isnan(ch) and close_i < ch:
                        return ExitSignal(close_i, "channel")
                else:
                    ch = cache.rolling_high[donchian_exit_period][prev]
                    if not math.isnan(ch) and close_i > ch:
                        return ExitSignal(close_i, "channel")

        # ── Signal reverse exit (EMA cross) ──
        if exit_mode == "signal" and entry_mode == "ema_cross":
            return self._check_signal_exit(i, cache, params, position)

        return None

    def _check_trailing_exit(
        self, i: int, cache: IndicatorCache, params: dict, position: Position,
    ) -> ExitSignal | None:
        """Check trailing stop — gap at open, update HWM, intraday check."""
        direction = position.direction
        atr_period: int = params.get("atr_period", 14)
        trailing_atr_mult: float = params.get("trailing_atr_mult", 4.0)
        state = position.state

        # Si pas de trailing dans le state → pas de trailing actif
        if "trailing_level" not in state:
            return None

        trailing_level = state["trailing_level"]

        # ── Gap trailing check (AVANT update) ──
        open_i = cache.opens[i]
        if direction == Direction.LONG:
            if trailing_level > 0 and open_i <= trailing_level:
                return ExitSignal(open_i, "gap_trailing")
        else:  # SHORT
            if trailing_level < float("inf") and open_i >= trailing_level:
                return ExitSignal(open_i, "gap_trailing")

        # ── Update trailing (seulement après le jour d'entrée) ──
        atr_arr = cache.atr_by_period[atr_period]
        atr_val = atr_arr[i - 1] if not math.isnan(atr_arr[i - 1]) else 0.0

        if atr_val > 0 and i > position.entry_candle:
            if direction == Direction.LONG:
                if cache.highs[i] > state["hwm"]:
                    state["hwm"] = cache.highs[i]
                    state["trailing_level"] = state["hwm"] - atr_val * trailing_atr_mult
                    trailing_level = state["trailing_level"]
            else:
                if cache.lows[i] < state["hwm"]:
                    state["hwm"] = cache.lows[i]
                    state["trailing_level"] = state["hwm"] + atr_val * trailing_atr_mult
                    trailing_level = state["trailing_level"]

        # ── Trailing intraday check (seulement après le jour d'entrée) ──
        if i > position.entry_candle:
            if direction == Direction.LONG:
                if trailing_level > 0 and cache.lows[i] <= trailing_level:
                    return ExitSignal(trailing_level, "trailing", apply_slippage=True)
            else:
                if trailing_level < float("inf") and cache.highs[i] >= trailing_level:
                    return ExitSignal(trailing_level, "trailing", apply_slippage=True)

        return None

    def _check_signal_exit(
        self, i: int, cache: IndicatorCache, params: dict, position: Position,
    ) -> ExitSignal | None:
        """Signal exit — EMA cross inverse → exit at open with slippage."""
        direction = position.direction
        ema_fast_period: int = params.get("ema_fast", 9)
        ema_slow_period: int = params.get("ema_slow", 50)
        prev = i - 1

        ema_fast = cache.ema_by_period[ema_fast_period]
        ema_slow = cache.ema_by_period[ema_slow_period]

        ef_prev = ema_fast[prev]
        es_prev = ema_slow[prev]
        ef_prev2 = ema_fast[prev - 1]
        es_prev2 = ema_slow[prev - 1]

        if math.isnan(ef_prev) or math.isnan(es_prev) or math.isnan(ef_prev2) or math.isnan(es_prev2):
            return None

        open_i = cache.opens[i]

        # LONG : bear cross → exit
        if direction == Direction.LONG and ef_prev < es_prev and ef_prev2 >= es_prev2:
            return ExitSignal(open_i, "signal_reverse", apply_slippage=True)
        # SHORT : bull cross → exit
        if direction == Direction.SHORT and ef_prev > es_prev and ef_prev2 <= es_prev2:
            return ExitSignal(open_i, "signal_reverse", apply_slippage=True)

        return None

    def init_state(
        self,
        entry_price: float,
        i: int,
        cache: IndicatorCache,
        params: dict,
        direction: Direction = Direction.FLAT,
    ) -> dict[str, Any]:
        """Initialise hwm et trailing_level pour le trailing stop."""
        exit_mode = params.get("exit_mode", "trailing")
        atr_period: int = params.get("atr_period", 14)
        trailing_atr_mult: float = params.get("trailing_atr_mult", 4.0)

        # Le trailing est actif en mode "trailing" et "channel"
        # (channel utilise aussi le trailing comme backup)
        if exit_mode in ("trailing", "channel"):
            atr_arr = cache.atr_by_period[atr_period]
            atr_val = atr_arr[i - 1] if not math.isnan(atr_arr[i - 1]) else 0.0

            if direction == Direction.LONG:
                if atr_val > 0:
                    trailing_level = entry_price - atr_val * trailing_atr_mult
                else:
                    trailing_level = 0.0
                return {"hwm": entry_price, "trailing_level": trailing_level}
            else:  # SHORT
                if atr_val > 0:
                    trailing_level = entry_price + atr_val * trailing_atr_mult
                else:
                    trailing_level = float("inf")
                return {"hwm": entry_price, "trailing_level": trailing_level}

        return {}
