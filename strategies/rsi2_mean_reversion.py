"""Stratégie RSI(2) Mean Reversion Connors pour signal-radar.

Long-only (production). Achète les pullbacks RSI(2) dans une tendance
haussière (close > SMA trend × buffer), sort quand le prix remonte
au-dessus de SMA exit (Connors classique).

Logique portée depuis engine/mean_reversion_backtest.py._simulate_mean_reversion()
"""

from __future__ import annotations

import math
from typing import Any

from engine.indicator_cache import IndicatorCache
from engine.types import Direction, ExitSignal, Position
from strategies.base import BaseStrategy


class RSI2MeanReversion(BaseStrategy):
    """RSI(2) Mean Reversion — Connors canonical params."""

    name = "rsi2_mean_reversion"

    def default_params(self) -> dict[str, Any]:
        return {
            "rsi_period": 2,
            "rsi_entry_threshold": 10.0,
            "sma_trend_period": 200,
            "sma_exit_period": 5,
            "rsi_exit_threshold": 0.0,  # 0 = désactivé
            "sma_trend_buffer": 1.01,  # Anti-whipsaw (production)
            "sl_percent": 0.0,  # Pas de SL (Connors)
            "position_fraction": 0.2,
            "cooldown_candles": 0,
            "sides": ["long"],
        }

    def param_grid(self) -> dict[str, list]:
        return {
            "rsi_period": [2],
            "rsi_entry_threshold": [5, 10, 15, 20],
            "sma_trend_period": [150, 200, 250],
            "sma_exit_period": [3, 5, 7, 10],
        }

    def check_entry(self, i: int, cache: IndicatorCache, params: dict) -> Direction:
        """Entry sur candle [i-1], action sur open[i]."""
        prev = i - 1

        rsi_period: int = params.get("rsi_period", 2)
        rsi_entry_threshold: float = params.get("rsi_entry_threshold", 10.0)
        sma_trend_period: int = params.get("sma_trend_period", 200)
        sma_trend_buffer: float = params.get("sma_trend_buffer", 1.0)
        sides: list[str] = params.get("sides", ["long"])

        # RSI value
        rsi_arr = cache.rsi_by_period[rsi_period]
        rsi_prev = rsi_arr[prev]
        if math.isnan(rsi_prev):
            return Direction.FLAT

        # SMA trend value
        sma_trend = cache.sma_by_period[sma_trend_period]
        sma_trend_prev = sma_trend[prev]
        if math.isnan(sma_trend_prev):
            return Direction.FLAT

        close_prev = cache.closes[prev]

        # LONG : RSI bas + tendance haussière
        if "long" in sides:
            if rsi_prev < rsi_entry_threshold and close_prev > sma_trend_prev * sma_trend_buffer:
                return Direction.LONG

        # SHORT : RSI haut + tendance baissière (miroir, pour complétude)
        if "short" in sides:
            if rsi_prev > (100.0 - rsi_entry_threshold) and close_prev < sma_trend_prev / sma_trend_buffer:
                return Direction.SHORT

        return Direction.FLAT

    def check_exit(
        self, i: int, cache: IndicatorCache, params: dict, position: Position,
    ) -> ExitSignal | None:
        """Exits MR — toutes au close, sans slippage."""
        sma_exit_period: int = params.get("sma_exit_period", 5)
        sma_trend_period: int = params.get("sma_trend_period", 200)
        rsi_exit_threshold: float = params.get("rsi_exit_threshold", 0.0)
        rsi_period: int = params.get("rsi_period", 2)

        close_i = cache.closes[i]
        direction = position.direction

        # Phase 1 : SMA exit
        sma_exit = cache.sma_by_period[sma_exit_period]
        sma_exit_val = sma_exit[i]
        if not math.isnan(sma_exit_val):
            if direction == Direction.LONG and close_i > sma_exit_val:
                return ExitSignal(close_i, "sma_exit")
            if direction == Direction.SHORT and close_i < sma_exit_val:
                return ExitSignal(close_i, "sma_exit")

        # Phase 2 : RSI exit (si activé)
        if rsi_exit_threshold > 0:
            rsi_arr = cache.rsi_by_period[rsi_period]
            rsi_val = rsi_arr[i]
            if not math.isnan(rsi_val):
                if direction == Direction.LONG and rsi_val > rsi_exit_threshold:
                    return ExitSignal(close_i, "rsi_exit")
                if direction == Direction.SHORT and rsi_val < (100.0 - rsi_exit_threshold):
                    return ExitSignal(close_i, "rsi_exit")

        # Phase 3 : Trend break
        sma_trend = cache.sma_by_period[sma_trend_period]
        sma_trend_val = sma_trend[i]
        if not math.isnan(sma_trend_val):
            if direction == Direction.LONG and close_i < sma_trend_val:
                return ExitSignal(close_i, "trend_break")
            if direction == Direction.SHORT and close_i > sma_trend_val:
                return ExitSignal(close_i, "trend_break")

        return None
