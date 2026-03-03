"""IBS + Turn of Month combined strategy.

Combine l'anomalie calendaire TOM (entree fin de mois) avec le filtre IBS
(oversold, close pres du low). Hypothese : les meilleurs trades TOM arrivent
quand le marche a aussi baisse en fin de mois (IBS bas).

Entry (signal sur [i-1], action sur open[i]) :
  1. Fenetre TOM : trading_days_left_in_month <= entry_days_before_eom
  2. IBS oversold : ibs < ibs_entry_threshold
  3. Trend filter : close > SMA(sma_trend_period)

Exit :
  1. Safety : max_holding_days depasse
  2. Dans le nouveau mois : TOM exit (jour >= exit_day) ou IBS early exit (ibs > seuil)
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from engine.indicator_cache import IndicatorCache
from engine.types import Direction, ExitSignal, Position
from strategies.base import BaseStrategy


class IBSTurnOfMonth(BaseStrategy):
    """IBS + Turn of Month -- entree calendaire filtree par oversold."""

    name = "ibs_turn_of_month"

    def default_params(self) -> dict[str, Any]:
        return {
            "entry_days_before_eom": 5,
            "exit_day_of_new_month": 3,
            "max_holding_days": 10,
            "ibs_entry_threshold": 0.2,
            "ibs_exit_threshold": 0.8,
            "sma_trend_period": 200,
            "position_fraction": 1.0,
            "sl_percent": 0.0,
            "cooldown_candles": 0,
            "sides": ["long"],
        }

    def param_grid(self) -> dict[str, list]:
        return {
            "entry_days_before_eom": [4, 5, 6],
            "ibs_entry_threshold": [0.15, 0.2, 0.25],
            "exit_day_of_new_month": [2, 3],
        }
        # 3 x 3 x 2 = 18 combinaisons

    def check_entry(self, i: int, cache: IndicatorCache, params: dict) -> Direction:
        """Entry sur [i-1] : fin de mois + IBS bas + trend haussiere."""
        prev = i - 1
        if prev < 0:
            return Direction.FLAT

        # Condition 1 : TOM -- derniers jours du mois
        if cache.trading_days_left_in_month is None:
            return Direction.FLAT
        entry_days: int = params.get("entry_days_before_eom", 5)
        days_left = cache.trading_days_left_in_month[prev]
        if days_left > entry_days:
            return Direction.FLAT

        # Condition 2 : IBS -- oversold
        if cache.ibs is None:
            return Direction.FLAT
        ibs_prev = cache.ibs[prev]
        if math.isnan(ibs_prev):
            return Direction.FLAT
        ibs_entry: float = params.get("ibs_entry_threshold", 0.2)
        if ibs_prev >= ibs_entry:
            return Direction.FLAT

        # Condition 3 : Trend filter -- close > SMA
        sma_trend_period: int = params.get("sma_trend_period", 200)
        sma_trend_prev = cache.sma_by_period[sma_trend_period][prev]
        if math.isnan(sma_trend_prev):
            return Direction.FLAT

        close_prev = cache.closes[prev]
        sides: list[str] = params.get("sides", ["long"])

        if "long" in sides and close_prev > sma_trend_prev:
            return Direction.LONG

        return Direction.FLAT

    def check_exit(
        self, i: int, cache: IndicatorCache, params: dict, position: Position,
    ) -> ExitSignal | None:
        """Exit calendaire (TOM) ou IBS early exit dans le nouveau mois."""
        entry_i = position.entry_candle
        close_i = cache.closes[i]

        # Phase 1 : Safety exit (max holding)
        max_holding: int = params.get("max_holding_days", 10)
        if (i - entry_i) >= max_holding:
            return ExitSignal(close_i, "max_holding_exit")

        # Phase 2 : Exits dans le nouveau mois uniquement
        if cache.trading_day_of_month is None or cache.dates is None:
            return None

        entry_ts = pd.Timestamp(cache.dates[entry_i])
        current_ts = pd.Timestamp(cache.dates[i])

        in_new_month = (
            current_ts.month != entry_ts.month
            or current_ts.year != entry_ts.year
        )

        if in_new_month:
            # TOM exit : N-eme jour du nouveau mois (priorite)
            exit_day: int = params.get("exit_day_of_new_month", 3)
            if cache.trading_day_of_month[i] >= exit_day:
                return ExitSignal(close_i, "tom_exit")

            # IBS early exit : reversion deja faite
            ibs_exit: float = params.get("ibs_exit_threshold", 0.8)
            if cache.ibs is not None:
                ibs_val = cache.ibs[i]
                if not math.isnan(ibs_val) and ibs_val > ibs_exit:
                    return ExitSignal(close_i, "ibs_early_exit")

        return None
