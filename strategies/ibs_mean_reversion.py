"""IBS (Internal Bar Strength) Mean Reversion Strategy.

Achete quand le close est pres du low du jour (IBS < seuil) en tendance haussiere.
Vend quand le close rebondit (IBS > seuil sortie ou close > high veille).

References :
- QuantifiedStrategies.com : SPY avg gain 0.8%/trade, WR 78%
- Alvarez Quant Trading : IBS < 25 filtre 63% des trades MR avec +21% avg PnL
"""

from __future__ import annotations

import math
from typing import Any

from engine.indicator_cache import IndicatorCache
from engine.types import Direction, ExitSignal, Position
from strategies.base import BaseStrategy


class IBSMeanReversion(BaseStrategy):
    """IBS Mean Reversion -- close pres du low = oversold = rebond."""

    name = "ibs_mean_reversion"

    def default_params(self) -> dict[str, Any]:
        return {
            "ibs_entry_threshold": 0.2,
            "ibs_exit_threshold": 0.8,
            "sma_trend_period": 200,
            "sl_percent": 0.0,
            "position_fraction": 0.2,
            "cooldown_candles": 0,
            "sides": ["long"],
        }

    def param_grid(self) -> dict[str, list]:
        return {
            "ibs_entry_threshold": [0.1, 0.15, 0.2, 0.25],
            "ibs_exit_threshold": [0.7, 0.8, 0.9],
            "sma_trend_period": [150, 200, 250],
        }
        # 4 x 3 x 3 = 36 combinaisons

    def check_entry(self, i: int, cache: IndicatorCache, params: dict) -> Direction:
        """Entry sur candle [i-1], action sur open[i]."""
        prev = i - 1

        ibs_entry: float = params.get("ibs_entry_threshold", 0.2)
        sma_trend_period: int = params.get("sma_trend_period", 200)
        sides: list[str] = params.get("sides", ["long"])

        # IBS value
        if cache.ibs is None:
            return Direction.FLAT
        ibs_prev = cache.ibs[prev]
        if math.isnan(ibs_prev):
            return Direction.FLAT

        # SMA trend value
        sma_trend = cache.sma_by_period[sma_trend_period]
        sma_trend_prev = sma_trend[prev]
        if math.isnan(sma_trend_prev):
            return Direction.FLAT

        close_prev = cache.closes[prev]

        # LONG : IBS bas + tendance haussiere
        if "long" in sides:
            if ibs_prev < ibs_entry and close_prev > sma_trend_prev:
                return Direction.LONG

        # SHORT : IBS haut + tendance baissiere (miroir)
        if "short" in sides:
            if ibs_prev > (1.0 - ibs_entry) and close_prev < sma_trend_prev:
                return Direction.SHORT

        return Direction.FLAT

    def check_exit(
        self, i: int, cache: IndicatorCache, params: dict, position: Position,
    ) -> ExitSignal | None:
        """Exits IBS -- toutes au close, sans slippage."""
        ibs_exit: float = params.get("ibs_exit_threshold", 0.8)
        sma_trend_period: int = params.get("sma_trend_period", 200)

        close_i = cache.closes[i]
        direction = position.direction

        # Phase 1 : IBS exit (reversion terminee)
        if cache.ibs is not None:
            ibs_val = cache.ibs[i]
            if not math.isnan(ibs_val):
                if direction == Direction.LONG and ibs_val > ibs_exit:
                    return ExitSignal(close_i, "ibs_exit")
                if direction == Direction.SHORT and ibs_val < (1.0 - ibs_exit):
                    return ExitSignal(close_i, "ibs_exit")

        # Phase 2 : Previous high/low exit (breakout du range precedent)
        if i >= 1:
            if direction == Direction.LONG and close_i > cache.highs[i - 1]:
                return ExitSignal(close_i, "prev_high_exit")
            if direction == Direction.SHORT and close_i < cache.lows[i - 1]:
                return ExitSignal(close_i, "prev_low_exit")

        # Phase 3 : Trend break
        sma_trend = cache.sma_by_period[sma_trend_period]
        sma_trend_val = sma_trend[i]
        if not math.isnan(sma_trend_val):
            if direction == Direction.LONG and close_i < sma_trend_val:
                return ExitSignal(close_i, "trend_break")
            if direction == Direction.SHORT and close_i > sma_trend_val:
                return ExitSignal(close_i, "trend_break")

        return None
