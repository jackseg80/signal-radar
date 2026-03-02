"""Turn of the Month (TOM) Strategy.

Anomalie calendaire bien documentee : les actions montent de maniere anormale
dans les derniers jours du mois et les premiers jours du mois suivant.

References :
- McConnell & Xu (2008) : effet persistant 1987-2005, US + international
- Kunkel, Compton & Beyer (2003) : effet sur 19 pays
- QuantifiedStrategies : S&P 500 CAGR 7.1%, investi 33% du temps, WR 62%, PF 2.0

Signal :
- Entry : long au close du N-eme dernier jour de trading du mois
  (via check_entry sur [i-1], moteur entre sur open[i])
- Exit : au close du M-eme jour de trading du nouveau mois
  (verifie que le mois courant != mois d'entree)
- Safety exit : max_holding_days depasse

Params :
- entry_days_before_eom : 5  (entrer quand il reste <= 5 jours)
- exit_day_of_new_month : 3  (sortir au 3eme jour du nouveau mois)
- max_holding_days : 10      (safety exit)
- position_fraction : 1.0   (100% standalone)
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from engine.indicator_cache import IndicatorCache
from engine.types import Direction, ExitSignal, Position
from strategies.base import BaseStrategy


class TurnOfMonth(BaseStrategy):
    """Turn of the Month -- anomalie calendaire fin/debut de mois."""

    name = "turn_of_month"

    def default_params(self) -> dict[str, Any]:
        return {
            "entry_days_before_eom": 5,
            "exit_day_of_new_month": 3,
            "max_holding_days": 10,
            "position_fraction": 1.0,
            "sl_percent": 0.0,
            "cooldown_candles": 0,
            "sides": ["long"],
        }

    def param_grid(self) -> dict[str, list]:
        return {
            "entry_days_before_eom": [3, 4, 5, 6],
            "exit_day_of_new_month": [2, 3, 4],
        }
        # 4 x 3 = 12 combinaisons

    def warmup(self, params: dict) -> int:
        """Pas d'indicateur technique -- warmup minimal (1 mois de trading)."""
        return 30

    def check_entry(self, i: int, cache: IndicatorCache, params: dict) -> Direction:
        """Entry sur [i-1] : dans les derniers jours de trading du mois."""
        if cache.trading_days_left_in_month is None:
            return Direction.FLAT

        prev = i - 1
        if prev < 0:
            return Direction.FLAT

        entry_days: int = params.get("entry_days_before_eom", 5)
        sides: list[str] = params.get("sides", ["long"])

        days_left = cache.trading_days_left_in_month[prev]

        if "long" in sides and days_left <= entry_days:
            return Direction.LONG

        return Direction.FLAT

    def check_exit(
        self, i: int, cache: IndicatorCache, params: dict, position: Position
    ) -> ExitSignal | None:
        """Exit au M-eme jour du nouveau mois, ou safety exit."""
        if cache.trading_day_of_month is None or cache.dates is None:
            return None

        entry_i = position.entry_candle
        close_i = cache.closes[i]

        # Safety exit : max holding depasse
        max_holding: int = params.get("max_holding_days", 10)
        if (i - entry_i) >= max_holding:
            return ExitSignal(close_i, "max_holding_exit")

        # TOM exit : dans le nouveau mois, assez loin dans le mois
        exit_day: int = params.get("exit_day_of_new_month", 3)

        entry_ts = pd.Timestamp(cache.dates[entry_i])
        current_ts = pd.Timestamp(cache.dates[i])

        in_new_month = (
            current_ts.month != entry_ts.month
            or current_ts.year != entry_ts.year
        )

        if in_new_month and cache.trading_day_of_month[i] >= exit_day:
            return ExitSignal(close_i, "tom_exit")

        return None
