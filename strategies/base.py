"""Classe abstraite pour toutes les stratégies de trading."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from engine.indicator_cache import IndicatorCache
from engine.types import Direction, ExitSignal, Position  # noqa: F401 (re-export)


class BaseStrategy(ABC):
    """Interface pour toutes les stratégies.

    Contrat :
    - check_entry(i) évalue les conditions sur candle [i-1], entrée sur open[i]
    - check_exit(i) évalue les conditions sur candle [i] (intraday)
    - Le moteur gère : sizing, fees, gap SL, intraday SL, force-close, capital
    - La stratégie gère : logique de signal, état strategy-specific (via Position.state)

    Slippage :
    - Entry : le moteur applique slippage directionnel sur open[i]
    - Exit SL (engine) : le moteur applique slippage sur sl_price
    - Exit stratégie : retourner ExitSignal(price, reason, apply_slippage=True)
      pour que le moteur applique le slippage. Laisser False pour les exits
      "at close" (prix observé, pas de slippage).
    """

    name: str = "unnamed"

    @abstractmethod
    def default_params(self) -> dict[str, Any]:
        """Params canoniques de la stratégie.

        Exemple RSI(2) Connors :
        {"rsi_period": 2, "rsi_entry_threshold": 10, "sma_trend_period": 200, ...}
        """

    @abstractmethod
    def param_grid(self) -> dict[str, list]:
        """Grille de paramètres pour le test de robustesse ET le cache indicateurs.

        Les clés contenant 'period' sont utilisées par build_cache() pour
        pré-calculer les indicateurs (SMA, RSI, ATR, etc.).

        Doit inclure les valeurs de default_params().

        Exemple RSI(2) :
        {"rsi_period": [2], "rsi_entry_threshold": [5,10,15,20],
         "sma_trend_period": [150,200,250], "sma_exit_period": [3,5,7,10]}
        """

    @abstractmethod
    def check_entry(self, i: int, cache: IndicatorCache, params: dict) -> Direction:
        """Évalue si on entre en position.

        Évalue les conditions sur la candle [i-1] (anti-look-ahead).
        Si Direction.LONG ou Direction.SHORT, le moteur entre sur open[i].

        Args:
            i: Index de la candle courante (entrée potentielle sur open[i])
            cache: Cache indicateurs pré-calculés
            params: Paramètres de la stratégie

        Returns:
            Direction.LONG, Direction.SHORT, ou Direction.FLAT (pas de signal)
        """

    @abstractmethod
    def check_exit(
        self, i: int, cache: IndicatorCache, params: dict, position: Position
    ) -> ExitSignal | None:
        """Évalue si on sort de la position.

        Appelé APRÈS le gap SL check et intraday SL check du moteur.
        Appelé aussi le jour de l'entrée (i == position.entry_candle).
        Peut lire/modifier position.state pour maintenir un état
        inter-candles (ex: trailing stop HWM).

        Args:
            i: Index de la candle courante
            cache: Cache indicateurs pré-calculés
            params: Paramètres de la stratégie
            position: Position ouverte

        Returns:
            ExitSignal(price, reason, apply_slippage) ou None (rester en position)
        """

    def init_state(
        self,
        entry_price: float,
        i: int,
        cache: IndicatorCache,
        params: dict,
        direction: Direction = Direction.FLAT,
    ) -> dict[str, Any]:
        """Initialise l'état strategy-specific de la position.

        Override pour les stratégies avec état (ex: trailing stop TF).
        Le MR n'a pas besoin de l'overrider → state = {}.

        Args:
            entry_price: Prix d'entrée (open[i])
            i: Index de la candle d'entrée
            cache: Cache indicateurs
            params: Paramètres de la stratégie
            direction: Direction du trade (LONG/SHORT)

        Returns:
            Dict d'état initial (vide par défaut)
        """
        return {}

    def warmup(self, params: dict) -> int:
        """Nombre de candles de warmup nécessaires.

        Default : max de toutes les valeurs dont la clé contient 'period', +10.
        Override si la stratégie a un warmup spécifique.
        """
        periods = [
            v
            for k, v in params.items()
            if "period" in k and isinstance(v, (int, float))
        ]
        return int(max(periods) + 10) if periods else 50
