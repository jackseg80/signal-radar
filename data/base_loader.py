"""Interface abstraite pour les sources de données daily."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class BaseDataLoader(ABC):
    """Interface standardisée pour les sources de données daily."""

    @abstractmethod
    def get_daily_candles(
        self, symbol: str, start: str, end: str,
    ) -> pd.DataFrame:
        """Retourne un DataFrame avec colonnes strictes.

        Index: DatetimeIndex (timezone-naive, dates UTC)
        Colonnes: Open, High, Low, Close, Adj_Close, Volume

        - Utiliser Adj_Close pour tous les calculs de signaux/rendements
        - Les jours non-trading (weekends, fériés) sont ABSENTS
        - Aucun NaN autorisé dans Open/High/Low/Close/Volume
        """
        ...

    @abstractmethod
    def get_available_symbols(self) -> list[str]:
        """Retourne la liste des symboles disponibles."""
        ...

    def to_cache_arrays(self, df: pd.DataFrame) -> dict[str, "np.ndarray"]:
        """Convertit un DataFrame en dict de numpy arrays pour IndicatorCache.

        Utilise Adj_Close comme 'closes' pour prendre en compte les splits/dividendes.
        """
        import numpy as np

        return {
            "opens": np.asarray(df["Open"].values, dtype=np.float64),
            "highs": np.asarray(df["High"].values, dtype=np.float64),
            "lows": np.asarray(df["Low"].values, dtype=np.float64),
            "closes": np.asarray(df["Adj_Close"].values, dtype=np.float64),
            "volumes": np.asarray(df["Volume"].values, dtype=np.float64),
        }
