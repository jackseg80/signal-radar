"""Data loader Yahoo Finance pour signal-radar.

Telecharge les donnees OHLCV daily via yfinance, avec cache SQLite local.
"""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd
from loguru import logger

from data.base_loader import BaseDataLoader
from data.db import SignalRadarDB

_db = SignalRadarDB()


class YahooLoader(BaseDataLoader):
    """Telecharge les donnees daily depuis Yahoo Finance via yfinance.

    Cache dans data/signal_radar.db (SQLite) pour eviter les telechargements
    repetes.
    """

    def __init__(self, cache_dir: str = "data/cache") -> None:
        # cache_dir garde pour compatibilite, ignore (DB utilisee)
        pass

    def get_daily_candles(
        self, symbol: str, start: str, end: str,
    ) -> pd.DataFrame:
        """Telecharge ou lit depuis le cache les candles daily.

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

        # Essayer le cache DB d'abord
        if _db.has_ohlcv(symbol):
            cached = _db.get_ohlcv(symbol)
            if len(cached) > 0:
                cache_start = cached.index[0].date()
                cache_end = cached.index[-1].date()
                req_start = pd.Timestamp(start).date()
                req_end = pd.Timestamp(end).date()
                tolerance = timedelta(days=7)
                if cache_start <= req_start + tolerance and cache_end >= req_end - tolerance:
                    mask = (cached.index >= start) & (cached.index <= end)
                    df = cached[mask]
                    if len(df) > 0:
                        logger.debug(
                            "Cache hit pour {} ({} -> {}): {} candles",
                            symbol, start, end, len(df),
                        )
                        return df

        # Telechargement depuis Yahoo
        logger.info("Telechargement {} ({} -> {})...", symbol, start, end)
        ticker = yf.Ticker(symbol)
        raw = ticker.history(start=start, end=end, auto_adjust=False)

        if raw.empty:
            raise ValueError(f"Aucune donnee retournee pour {symbol} ({start} -> {end})")

        # Normaliser le DataFrame
        df = raw[["Open", "High", "Low", "Close", "Adj Close", "Volume"]].copy()
        df.rename(columns={"Adj Close": "Adj_Close"}, inplace=True)

        # Supprimer timezone si presente
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)

        # Ajuster O/H/L pour splits et dividendes (ratio Adj_Close / Close)
        # Sans cet ajustement, un split 4:1 fait que les prix pre-split sont
        # 4x trop hauts -> ATR, Donchian channels, SL completement faux.
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
            df["Close"] = df["Adj_Close"]  # Close = Adj_Close apres ajustement

        # Validation
        self._validate(df, symbol)

        # Sauvegarder dans la DB
        _db.save_ohlcv(symbol, df)
        logger.info("{}: {} candles sauvegardees dans la DB", symbol, len(df))

        mask = (df.index >= start) & (df.index <= end)
        return df[mask]

    def get_available_symbols(self) -> list[str]:
        """Retourne les symboles ayant des donnees en DB."""
        return [a["symbol"] for a in _db.list_assets()]

    @staticmethod
    def _validate(df: pd.DataFrame, symbol: str) -> None:
        """Valide la qualite des donnees."""
        # Pas de NaN dans les prix
        price_cols = ["Open", "High", "Low", "Close", "Adj_Close"]
        for col in price_cols:
            nan_count = df[col].isna().sum()
            if nan_count > 0:
                logger.warning("{}: {} NaN dans {} -- suppression des lignes", symbol, nan_count, col)
                df.dropna(subset=price_cols, inplace=True)
                break

        # Prix > 0
        for col in price_cols:
            if (df[col] <= 0).any():
                raise ValueError(f"{symbol}: prix <= 0 detecte dans {col}")

        # High >= Low
        violations = (df["High"] < df["Low"]).sum()
        if violations > 0:
            raise ValueError(f"{symbol}: {violations} candles avec High < Low")
