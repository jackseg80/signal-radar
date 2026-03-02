"""Gestionnaire du cache de donnees OHLCV local.

Wraper autour de YahooLoader avec gestion du cycle de vie :
telechargement, mise a jour incrementale, info, nettoyage.

Usage:
    from data.cache_manager import CacheManager

    cm = CacheManager()
    df = cm.get("AAPL", "2005-01-01", "2025-01-01")   # cache-through
    cm.update("AAPL")                                   # incremental
    cm.update_universe("us_stocks_large")               # tout un univers
    cm.info()                                            # liste du cache
    cm.clear("AAPL")                                    # supprimer un symbol
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from loguru import logger

from data.yahoo_loader import YahooLoader

CACHE_DIR = Path("data/cache")


class CacheManager:
    """Gestionnaire du cache de donnees OHLCV."""

    def __init__(self, cache_dir: str = "data/cache") -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._loader = YahooLoader(cache_dir=str(self.cache_dir))

    def _cache_path(self, symbol: str) -> Path:
        """Chemin du fichier cache (meme convention que YahooLoader)."""
        safe = symbol.replace("/", "_").replace("=", "_")
        return self.cache_dir / f"{safe}_1d.parquet"

    def has(self, symbol: str) -> bool:
        """Verifie si le symbol est en cache."""
        return self._cache_path(symbol).exists()

    def get(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """Recupere les donnees OHLCV (delegue a YahooLoader avec cache)."""
        return self._loader.get_daily_candles(symbol, start, end)

    def _download_raw(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """Telecharge depuis Yahoo Finance avec ajustement splits.

        Replique la logique de YahooLoader.get_daily_candles() sans cache.
        """
        import yfinance as yf

        logger.info("Downloading {} ({} -> {})...", symbol, start, end)
        try:
            ticker = yf.Ticker(symbol)
            raw = ticker.history(start=start, end=end, auto_adjust=False)
        except Exception as e:
            logger.error("Failed to download {}: {}", symbol, e)
            return pd.DataFrame()

        if raw.empty:
            logger.warning("No data for {}", symbol)
            return pd.DataFrame()

        df = raw[["Open", "High", "Low", "Close", "Adj Close", "Volume"]].copy()
        df.rename(columns={"Adj Close": "Adj_Close"}, inplace=True)

        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)

        # Ajuster O/H/L pour splits et dividendes
        adj_ratio = df["Adj_Close"].values / df["Close"].values
        if not np.allclose(adj_ratio, 1.0, rtol=1e-6):
            df["Open"] = df["Open"] * adj_ratio
            df["High"] = df["High"] * adj_ratio
            df["Low"] = df["Low"] * adj_ratio
            df["Close"] = df["Adj_Close"]

        return df

    def update(self, symbol: str) -> pd.DataFrame:
        """Met a jour le cache avec les dernieres donnees.

        Si le cache existe, telecharge depuis la derniere date (incremental).
        Sinon, telecharge tout depuis 2003.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        path = self._cache_path(symbol)

        if path.exists():
            existing = pd.read_parquet(path)
            last_date = existing.index.max()
            overlap_start = (last_date - timedelta(days=5)).strftime("%Y-%m-%d")

            new_data = self._download_raw(symbol, overlap_start, today)

            if not new_data.empty:
                combined = pd.concat([existing, new_data])
                combined = combined[~combined.index.duplicated(keep="last")]
                combined.sort_index(inplace=True)
                combined.to_parquet(path)
                logger.info("{}: {} rows in cache", symbol, len(combined))
                return combined
            return existing
        else:
            df = self._download_raw(symbol, "2003-01-01", today)
            if not df.empty:
                df.to_parquet(path)
                logger.info("{}: {} rows cached", symbol, len(df))
            return df

    def update_universe(self, universe_name: str) -> None:
        """Met a jour tous les assets d'un univers."""
        from config.universe_loader import load_universe

        universe = load_universe(universe_name)
        total = len(universe.assets)
        for i, symbol in enumerate(universe.assets, 1):
            print(f"  [{i}/{total}] {symbol}...", end=" ", flush=True)
            try:
                df = self.update(symbol)
                rows = len(df) if not df.empty else 0
                print(f"{rows} rows")
            except Exception as e:
                print(f"FAILED ({e})")

    def download_universe(self, universe_name: str, end: str = "2025-01-01") -> None:
        """Telecharge tous les assets d'un univers (via YahooLoader)."""
        from config.universe_loader import load_universe

        universe = load_universe(universe_name)
        total = len(universe.assets)
        for i, (symbol, start_date) in enumerate(universe.assets.items(), 1):
            print(f"  [{i}/{total}] {symbol}...", end=" ", flush=True)
            try:
                df = self.get(symbol, start_date, end)
                print(f"{len(df)} rows")
            except Exception as e:
                print(f"FAILED ({e})")

    def info(self) -> list[dict]:
        """Liste les assets en cache avec metadonnees."""
        result: list[dict] = []
        for path in sorted(self.cache_dir.glob("*_1d.parquet")):
            try:
                df = pd.read_parquet(path)
                # Reverse symbol name: remove _1d suffix, undo safe replace
                stem = path.stem[:-3]  # remove "_1d"
                sym = stem.replace("_X", "=X")
                result.append({
                    "symbol": sym,
                    "rows": len(df),
                    "start": df.index.min().strftime("%Y-%m-%d"),
                    "end": df.index.max().strftime("%Y-%m-%d"),
                    "size_kb": round(path.stat().st_size / 1024, 1),
                })
            except Exception as e:
                logger.warning("Cannot read {}: {}", path, e)
        return result

    def clear(self, symbol: str | None = None) -> None:
        """Supprime le cache. Sans argument, supprime tout."""
        if symbol:
            path = self._cache_path(symbol)
            if path.exists():
                path.unlink()
                logger.info("Cache cleared for {}", symbol)
        else:
            count = 0
            for path in self.cache_dir.glob("*_1d.parquet"):
                path.unlink()
                count += 1
            logger.info("Cleared {} cached files", count)
