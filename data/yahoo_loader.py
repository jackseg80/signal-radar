"""Data loader Yahoo Finance pour signal-radar.

Télécharge les données OHLCV daily via yfinance, avec cache parquet local.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from loguru import logger

from data.base_loader import BaseDataLoader


class YahooLoader(BaseDataLoader):
    """Télécharge les données daily depuis Yahoo Finance via yfinance.

    Cache local en parquet dans data/cache/ pour éviter les téléchargements
    répétés.
    """

    def __init__(self, cache_dir: str = "data/cache") -> None:
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, symbol: str) -> Path:
        safe = symbol.replace("/", "_").replace("=", "_")
        return self._cache_dir / f"{safe}_1d.parquet"

    def get_daily_candles(
        self, symbol: str, start: str, end: str,
    ) -> pd.DataFrame:
        """Télécharge ou lit depuis le cache les candles daily.

        Parameters
        ----------
        symbol : str
            Ticker Yahoo Finance (ex: "AAPL", "EURUSD=X").
        start, end : str
            Dates au format "YYYY-MM-DD".

        Returns
        -------
        pd.DataFrame
            Colonnes: Open, High, Low, Close, Adj_Close, Volume.
            Index: DatetimeIndex timezone-naive.
        """
        import yfinance as yf

        cache_path = self._cache_path(symbol)

        # Essayer le cache d'abord
        if cache_path.exists():
            cached = pd.read_parquet(cache_path)
            if len(cached) > 0:
                cache_start = str(cached.index[0].date())
                cache_end = str(cached.index[-1].date())
                if cache_start <= start and cache_end >= end:
                    mask = (cached.index >= start) & (cached.index <= end)
                    df = cached[mask]
                    if len(df) > 0:
                        logger.debug(
                            "Cache hit pour {} ({} → {}): {} candles",
                            symbol, start, end, len(df),
                        )
                        return df

        # Téléchargement depuis Yahoo
        logger.info("Téléchargement {} ({} → {})...", symbol, start, end)
        ticker = yf.Ticker(symbol)
        raw = ticker.history(start=start, end=end, auto_adjust=False)

        if raw.empty:
            raise ValueError(f"Aucune donnée retournée pour {symbol} ({start} → {end})")

        # Normaliser le DataFrame
        df = raw[["Open", "High", "Low", "Close", "Adj Close", "Volume"]].copy()
        df.rename(columns={"Adj Close": "Adj_Close"}, inplace=True)

        # Supprimer timezone si présente
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)

        # Ajuster O/H/L pour splits et dividendes (ratio Adj_Close / Close)
        # Sans cet ajustement, un split 4:1 fait que les prix pré-split sont
        # 4x trop hauts → ATR, Donchian channels, SL complètement faux.
        adj_ratio = df["Adj_Close"].values / df["Close"].values
        has_adjustments = not np.allclose(adj_ratio, 1.0, rtol=1e-6)
        if has_adjustments:
            logger.info(
                "{}: ajustement O/H/L pour splits/dividendes (ratio min={:.4f}, max={:.4f})",
                symbol, adj_ratio.min(), adj_ratio.max(),
            )
            df["Open"] = df["Open"] * adj_ratio
            df["High"] = df["High"] * adj_ratio
            df["Low"] = df["Low"] * adj_ratio
            df["Close"] = df["Adj_Close"]  # Close = Adj_Close après ajustement

        # Validation
        self._validate(df, symbol)

        # Sauvegarder dans le cache
        df.to_parquet(cache_path)
        logger.info("{}: {} candles sauvegardées dans le cache", symbol, len(df))

        mask = (df.index >= start) & (df.index <= end)
        return df[mask]

    def get_available_symbols(self) -> list[str]:
        """Retourne les symboles ayant un cache local."""
        symbols = []
        for path in self._cache_dir.glob("*_1d.parquet"):
            name = path.stem.replace("_1d", "").replace("_X", "=X").replace("_", "/")
            symbols.append(name)
        return sorted(symbols)

    @staticmethod
    def _validate(df: pd.DataFrame, symbol: str) -> None:
        """Valide la qualité des données."""
        # Pas de NaN dans les prix
        price_cols = ["Open", "High", "Low", "Close", "Adj_Close"]
        for col in price_cols:
            nan_count = df[col].isna().sum()
            if nan_count > 0:
                logger.warning("{}: {} NaN dans {} — suppression des lignes", symbol, nan_count, col)
                df.dropna(subset=price_cols, inplace=True)
                break

        # Prix > 0
        for col in price_cols:
            if (df[col] <= 0).any():
                raise ValueError(f"{symbol}: prix <= 0 détecté dans {col}")

        # High >= Low
        violations = (df["High"] < df["Low"]).sum()
        if violations > 0:
            raise ValueError(f"{symbol}: {violations} candles avec High < Low")
