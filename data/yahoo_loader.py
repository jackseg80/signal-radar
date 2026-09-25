"""Data loader Yahoo Finance pour signal-radar.

Telecharge les donnees OHLCV daily via yfinance, avec cache SQLite local.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from loguru import logger

from data.base_loader import BaseDataLoader
from data.db import SignalRadarDB
from data.nasdaq_fallback import fetch_historical_bars
from engine.trading_calendar import XNYS

_db = SignalRadarDB()
VERIFIED_REPAIRS_PATH = Path('config/verified_price_repairs.yaml')


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
    def _verified_manifest(symbol: str, session: str) -> dict | None:
        """Read a previously checked Nasdaq bar for an exceptional Yahoo gap."""
        if not VERIFIED_REPAIRS_PATH.exists():
            return None
        with VERIFIED_REPAIRS_PATH.open(encoding="utf-8") as stream:
            values = yaml.safe_load(stream) or {}
        if values.get("version") != 1 or not isinstance(values.get("repairs"), list):
            raise ValueError("Invalid verified price repair manifest")
        matches = [
            item for item in values["repairs"]
            if item.get("symbol") == symbol and item.get("session") == session
        ]
        if len(matches) > 1:
            raise ValueError(f"Duplicate approved repair for {symbol} {session}")
        return matches[0] if matches else None

    @staticmethod
    def _future_split_factor(raw: pd.DataFrame, session: pd.Timestamp) -> float:
        """Recover the quoted basis from split-adjusted Yahoo history."""
        later = raw.loc[raw.index > session, "Stock Splits"]
        return float(later.where(later > 0, 1.0).prod())

    @classmethod
    def _complete_nasdaq_gaps(
        cls, symbol: str, raw: pd.DataFrame,
    ) -> tuple[pd.DataFrame, list[dict]]:
        """Fill only isolated daily Yahoo gaps corroborated by Nasdaq neighbors.

        When no authoritative comparison is possible, leave the gap for strict
        validation to reject. Previously audited bars survive provider outages.
        """
        for field in ("Dividends", "Stock Splits"):
            if field not in raw:
                raw[field] = 0.0
        dates = pd.DatetimeIndex(raw.index).normalize()
        expected = XNYS.sessions_in_range(dates[0], dates[-1])
        missing = expected.difference(dates)
        if len(missing) > 3:
            raise ValueError(f"{symbol}: too many missing daily bars for fallback")
        applied: list[dict] = []
        for day in missing:
            previous = XNYS.previous_session(day)
            following = XNYS.next_session(day)
            if previous not in raw.index or following not in raw.index:
                continue
            session = str(day.date())
            prev_name, next_name = str(previous.date()), str(following.date())
            manifest = cls._verified_manifest(symbol, session)
            audited = _db.get_price_repair(symbol, session)
            source_url = ""
            bars: dict[str, dict] = {}
            try:
                source_url, bars = fetch_historical_bars(
                    symbol, prev_name, next_name,
                )
            except (OSError, ValueError) as exc:
                logger.warning("{}: Nasdaq fallback unavailable for {}: {}",
                               symbol, session, exc)
            live = all(name in bars for name in (prev_name, session, next_name))
            if live:
                candidate = bars[session]
                if manifest and any(
                    abs(float(candidate[field]) - float(manifest[field])) > 0.03
                    for field in ("open", "high", "low", "close")
                ):
                    raise ValueError(f"{symbol}: Nasdaq revised approved bar {session}")
                prev_close, next_close = (
                    bars[prev_name]["close"], bars[next_name]["close"]
                )
                verified_at = datetime.now(timezone.utc).date().isoformat()
            elif manifest or audited:
                candidate = manifest or {
                    "open": audited["raw_open"], "high": audited["raw_high"],
                    "low": audited["raw_low"], "close": audited["raw_close"],
                    "volume": audited["volume"],
                }
                source_url = (manifest or audited)["source_url"]
                prev_close = float((manifest or audited)["previous_close"])
                next_close = float((manifest or audited)["next_close"])
                verified_at = (manifest or audited)["verified_at"]
            else:
                continue
            if not source_url.startswith(
                f"https://api.nasdaq.com/api/quote/{symbol}/historical?"
            ):
                raise ValueError(f"{symbol}: untrusted fallback source")
            if manifest and (
                prev_name != manifest["previous_session"]
                or next_name != manifest["next_session"]
            ):
                raise ValueError(f"{symbol}: repair neighbors changed")
            left_ratio = float(raw.loc[previous, "Adj Close"] /
                               raw.loc[previous, "Close"])
            right_ratio = float(raw.loc[following, "Adj Close"] /
                                raw.loc[following, "Close"])
            if (not np.isfinite([left_ratio, right_ratio]).all()
                    or abs(left_ratio - right_ratio) > 1e-6):
                raise ValueError(
                    f"{symbol}: corporate-action adjustment crosses missing {session}"
                )
            for neighbor, quoted_close in (
                (previous, prev_close), (following, next_close),
            ):
                yahoo_quoted = (
                    float(raw.loc[neighbor, "Close"])
                    * cls._future_split_factor(raw, neighbor)
                )
                if abs(yahoo_quoted - quoted_close) > 0.03:
                    raise ValueError(
                        f"{symbol}: Yahoo/Nasdaq neighbor disagreement near {session}"
                    )
            values = {field: float(candidate[field])
                      for field in ("open", "high", "low", "close", "volume")}
            if (not np.isfinite(list(values.values())).all()
                    or min(values[field] for field in ("open", "high", "low", "close")) <= 0
                    or values["volume"] < 0
                    or values["low"] > min(values["open"], values["close"])
                    or values["high"] < max(values["open"], values["close"])):
                raise ValueError(f"{symbol}: impossible fallback OHLC on {session}")
            future = cls._future_split_factor(raw, day)
            raw.loc[day, "Open"] = values["open"] / future
            raw.loc[day, "High"] = values["high"] / future
            raw.loc[day, "Low"] = values["low"] / future
            raw.loc[day, "Close"] = values["close"] / future
            raw.loc[day, "Adj Close"] = values["close"] / future * left_ratio
            raw.loc[day, "Volume"] = values["volume"]
            raw.loc[day, "Dividends"] = 0.0
            raw.loc[day, "Stock Splits"] = 0.0
            applied.append({
                "symbol": symbol, "session": session, "source_url": source_url,
                "verified_at": verified_at,
                "previous_close": prev_close, "next_close": next_close,
                **values,
            })
            logger.warning("{}: repaired missing {} daily bar from verified Nasdaq OHLC",
                           symbol, session)
        return raw.sort_index(), applied

    @classmethod
    def _check_audited_yahoo_bars(
        cls, symbol: str, raw: pd.DataFrame,
    ) -> None:
        """Block a later Yahoo correction that materially conflicts with Nasdaq."""
        for repair in _db.get_price_repairs():
            if repair["symbol"] != symbol:
                continue
            day = pd.Timestamp(repair["date"])
            if day not in raw.index:
                continue
            close = (
                float(raw.loc[day, "Close"])
                * cls._future_split_factor(raw, day)
            )
            if abs(close - repair["raw_close"]) > 0.03:
                raise ValueError(
                    f"{symbol}: Yahoo/Nasdaq repaired close conflict on {repair['date']}"
                )

    def get_daily_candles_strict(
        self, symbol: str, start: str, end: str, expected_session: str,
    ) -> pd.DataFrame:
        """Return verified bars through the exact closed session or raise.

        The v2 cache stores raw trade prices and separate adjusted indicators.
        A legacy adjusted-only cache is never accepted here.
        """
        import yfinance as yf

        cached = _db.get_prices_v2(symbol, start, end)
        first_requested = XNYS.date_to_session(pd.Timestamp(start), direction="next")
        if (not cached.empty
                and not _db.has_legacy_prices_v2(symbol, start, end)
                and cached.index[0] <= first_requested
                and str(cached.index[-1].date()) == expected_session):
            try:
                self._validate_strict(cached, symbol, expected_session)
                return cached
            except ValueError:
                logger.warning("{}: cached bars invalid; refreshing Yahoo", symbol)

        raw = yf.Ticker(symbol).history(start=start, end=end, auto_adjust=False, actions=True)
        if raw.empty:
            raise ValueError(f"{symbol}: Yahoo returned no bars through {expected_session}")
        if raw.index.tz is not None:
            raw.index = raw.index.tz_localize(None)
        if "Adj Close" not in raw:
            raise ValueError(f"{symbol}: Yahoo omitted Adj Close")
        if raw.index.has_duplicates:
            raise ValueError(f"{symbol}: duplicate Yahoo session dates")
        if not raw.index.is_monotonic_increasing:
            raise ValueError(f"{symbol}: Yahoo session dates are not ordered")
        raw, repairs = self._complete_nasdaq_gaps(symbol, raw.copy())
        self._check_audited_yahoo_bars(symbol, raw)
        df = raw[["Open", "High", "Low", "Close", "Adj Close", "Volume"]].copy()
        df = df.rename(columns={"Adj Close": "Adj_Close"})
        for action in ("Dividends", "Stock Splits"):
            df[action] = raw[action] if action in raw else 0.0
        ratio = df["Adj_Close"] / df["Close"]
        for field in ("Open", "High", "Low"):
            df[f"Adj_{field}"] = df[field] * ratio
        # Yahoo auto_adjust=False still returns prices and cash dividends
        # adjusted for later splits. Recover the actually quoted price and
        # dividend per share before storing execution data. A split occurring
        # on a session affects only earlier rows, never that session's open.
        split_factors = df["Stock Splits"].where(df["Stock Splits"] > 0, 1.0)
        future_splits = split_factors.iloc[::-1].cumprod().iloc[::-1] / split_factors
        for field in ("Open", "High", "Low", "Close", "Dividends"):
            df[field] = df[field] * future_splits
        self._validate_strict(df, symbol, expected_session)
        _db.save_prices_v2(symbol, df, repairs=repairs)
        return _db.get_prices_v2(symbol, start, end)

    @staticmethod
    def _validate_strict(
        df: pd.DataFrame, symbol: str, expected_session: str,
    ) -> None:
        """Fail closed on missing, duplicate, non-session or impossible OHLC bars."""
        if df.empty or str(df.index[-1].date()) != expected_session:
            latest = str(df.index[-1].date()) if not df.empty else "none"
            raise ValueError(
                f"{symbol}: expected closed session {expected_session}, latest {latest}"
            )
        if df.index.has_duplicates or not df.index.is_monotonic_increasing:
            raise ValueError(f"{symbol}: duplicate or unsorted session dates")
        dates = pd.DatetimeIndex(df.index).normalize()
        if any(not XNYS.is_session(day) for day in dates):
            raise ValueError(f"{symbol}: non-XNYS date in Yahoo bars")
        expected = XNYS.sessions_in_range(dates[0], dates[-1])
        missing = expected.difference(dates)
        if len(missing):
            raise ValueError(f"{symbol}: missing XNYS bar {missing[0].date()}")
        price_cols = [
            "Open", "High", "Low", "Close", "Adj_Open", "Adj_High",
            "Adj_Low", "Adj_Close",
        ]
        if not np.isfinite(df[price_cols].to_numpy(dtype=float)).all():
            raise ValueError(f"{symbol}: missing or non-finite OHLC")
        if (df[price_cols] <= 0).any().any():
            raise ValueError(f"{symbol}: non-positive OHLC")
        if not np.isfinite(df["Volume"].to_numpy(dtype=float)).all() or (df["Volume"] < 0).any():
            raise ValueError(f"{symbol}: invalid volume")
        for prefix in ("", "Adj_"):
            high, low = df[f"{prefix}High"], df[f"{prefix}Low"]
            op, close = df[f"{prefix}Open"], df[f"{prefix}Close"]
            # Multiplying a raw OHLC by Adj_Close / Close can differ from
            # Adj_Close by a few floating-point ulps at equal high/close.
            tolerance = 1e-10 * high.clip(lower=1.0) if prefix else 0.0
            if ((high + tolerance < low) | (high + tolerance < op) |
                    (high + tolerance < close) | (low - tolerance > op) |
                    (low - tolerance > close)).any():
                raise ValueError(f"{symbol}: impossible {prefix}OHLC")

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
