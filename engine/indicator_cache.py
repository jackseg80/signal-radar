"""Cache d'indicateurs pré-calculés pour le fast backtest engine.

Construit TOUS les indicateurs une seule fois par fenêtre WFO, pour toutes
les variantes de paramètres du grid.

Adapté depuis scalp-radar/backend/optimization/indicator_cache.py — stripped
de tous les champs crypto (RSI, VWAP, Bollinger, SuperTrend, régime, funding,
filtre multi-TF).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from engine.indicators import (
    adx,
    atr,
    ema,
    internal_bar_strength,
    rolling_max,
    rolling_min,
    rsi,
    sma,
)


@dataclass
class IndicatorCache:
    """Cache numpy de tous les indicateurs pour une fenêtre de données.

    Tous les arrays ont shape (n_candles,) sauf les dicts {param_variant: array}.
    """

    n_candles: int
    opens: np.ndarray
    highs: np.ndarray
    lows: np.ndarray
    closes: np.ndarray
    volumes: np.ndarray
    total_days: float  # durée totale en jours (pour annualisation Sharpe)

    # Multi-period EMA (pour entry_mode="ema_cross")
    ema_by_period: dict[int, np.ndarray] = field(default_factory=dict)

    # Multi-period ADX — stocke le tuple complet (adx, di_plus, di_minus)
    # pour permettre un futur filtre DI+ > DI-
    adx_by_period: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray]] = field(
        default_factory=dict
    )

    # Multi-period ATR (pour trailing stop)
    atr_by_period: dict[int, np.ndarray] = field(default_factory=dict)

    # Donchian channels — rolling high/low excluant la candle courante
    rolling_high: dict[int, np.ndarray] = field(default_factory=dict)
    rolling_low: dict[int, np.ndarray] = field(default_factory=dict)

    # Multi-period SMA (pour mean reversion trend filter / exit)
    sma_by_period: dict[int, np.ndarray] = field(default_factory=dict)

    # Multi-period RSI (pour mean reversion entry signal)
    rsi_by_period: dict[int, np.ndarray] = field(default_factory=dict)

    # Internal Bar Strength (IBS) — calcul par candle, pas de période
    ibs: np.ndarray | None = None

    # Arrays calendaires (optionnels — requis pour TurnOfMonth et stratégies calendaires)
    dates: np.ndarray | None = None                        # datetime64 array des dates de trading
    trading_day_of_month: np.ndarray | None = None        # rang du jour dans le mois (1er, 2ème, ...)
    trading_days_left_in_month: np.ndarray | None = None  # jours de trading restants dans le mois (inclus)

    def get_idx_from_date(self, target_date_str: str) -> int:
        """Retourne l'index de la première date >= target_date_str."""
        if self.dates is None:
            raise ValueError("dates array is not initialized in cache")
        import pandas as pd
        # Find first date >= target
        valid_indices = np.where(pd.DatetimeIndex(self.dates) >= target_date_str)[0]
        if len(valid_indices) == 0:
            raise ValueError(f"No dates found >= {target_date_str}")
        return int(valid_indices[0])

    def get_idx_before_date(self, target_date_str: str) -> int:
        """Retourne l'index de la première date < target_date_str."""
        if self.dates is None:
            raise ValueError("dates array is not initialized in cache")
        import pandas as pd
        valid_indices = np.where(pd.DatetimeIndex(self.dates) < target_date_str)[0]
        if len(valid_indices) == 0:
            return 0
        return int(valid_indices[-1] + 1)


def build_cache(
    arrays: dict[str, np.ndarray],
    param_grid_values: dict[str, list],
    dates: np.ndarray | None = None,
) -> IndicatorCache:
    """Construit le cache d'indicateurs pour une fenêtre de données.

    Parameters
    ----------
    arrays : dict
        Doit contenir les clés 'opens', 'highs', 'lows', 'closes', 'volumes'
        (numpy arrays de même longueur).
    param_grid_values : dict
        Union de toutes les valeurs de paramètres du grid WFO.
        Ex: {"ema_fast": [9, 21], "atr_period": [14], ...}
    dates : np.ndarray | None
        Array datetime64 des dates de trading (optionnel). Requis pour les
        stratégies calendaires (TurnOfMonth). Si fourni, calcule automatiquement
        trading_day_of_month et trading_days_left_in_month.

    Returns
    -------
    IndicatorCache
        Cache prêt pour _simulate_trend_follow().
    """
    opens = np.ascontiguousarray(arrays["opens"], dtype=np.float64)
    highs = np.ascontiguousarray(arrays["highs"], dtype=np.float64)
    lows = np.ascontiguousarray(arrays["lows"], dtype=np.float64)
    closes = np.ascontiguousarray(arrays["closes"], dtype=np.float64)
    volumes = np.ascontiguousarray(arrays["volumes"], dtype=np.float64)
    n = len(closes)

    # Durée totale approximative en jours calendrier
    # Pour daily bars : n_candles ≈ trading days, total_days ≈ n * 365/252
    total_days = n * 365.0 / 252.0 if n > 1 else 1.0

    # --- EMA multi-period (pour ema_cross entry mode) ---
    ema_by_period: dict[int, np.ndarray] = {}
    all_ema_periods: set[int] = set()
    for key in ("ema_fast", "ema_slow"):
        if key in param_grid_values:
            all_ema_periods.update(param_grid_values[key])
    for p in all_ema_periods:
        ema_by_period[p] = ema(closes, p)

    # --- ADX multi-period — stocke le tuple complet (adx, di+, di-) ---
    adx_by_period: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    adx_periods: set[int] = set()
    if "adx_period" in param_grid_values:
        adx_periods.update(param_grid_values["adx_period"])
    if not adx_periods:
        adx_periods.add(14)
    for p in adx_periods:
        adx_arr, di_plus_arr, di_minus_arr = adx(highs, lows, closes, p)
        adx_by_period[p] = (adx_arr, di_plus_arr, di_minus_arr)

    # --- ATR multi-period ---
    atr_by_period: dict[int, np.ndarray] = {}
    atr_periods: set[int] = set()
    if "atr_period" in param_grid_values:
        atr_periods.update(param_grid_values["atr_period"])
    if not atr_periods:
        atr_periods.add(14)
    for p in atr_periods:
        atr_by_period[p] = atr(highs, lows, closes, p)

    # --- SMA multi-period (pour mean reversion trend filter / exit) ---
    sma_by_period: dict[int, np.ndarray] = {}
    all_sma_periods: set[int] = set()
    for key in ("sma_trend_period", "sma_exit_period"):
        if key in param_grid_values:
            all_sma_periods.update(param_grid_values[key])
    for p in all_sma_periods:
        sma_by_period[p] = sma(closes, p)

    # --- RSI multi-period (pour mean reversion entry signal) ---
    rsi_by_period: dict[int, np.ndarray] = {}
    rsi_periods: set[int] = set()
    if "rsi_period" in param_grid_values:
        rsi_periods.update(param_grid_values["rsi_period"])
    for p in rsi_periods:
        rsi_by_period[p] = rsi(closes, p)

    # --- Rolling high/low pour Donchian channels ---
    lookbacks: set[int] = set()
    for key in ("donchian_entry_period", "donchian_exit_period"):
        if key in param_grid_values:
            lookbacks.update(param_grid_values[key])
    rolling_high_dict = {lb: rolling_max(highs, lb) for lb in lookbacks}
    rolling_low_dict = {lb: rolling_min(lows, lb) for lb in lookbacks}

    # --- IBS (Internal Bar Strength) — calcul par candle ---
    ibs_arr = internal_bar_strength(highs, lows, closes)

    # --- Arrays calendaires (optionnels) ---
    dates_arr: np.ndarray | None = None
    trading_day_of_month_arr: np.ndarray | None = None
    trading_days_left_arr: np.ndarray | None = None

    if dates is not None:
        import pandas as pd

        dates_arr = np.asarray(dates)
        ts = pd.DatetimeIndex(dates_arr)
        # Période mensuelle pour chaque date
        periods = ts.to_period("M")

        tdom = np.zeros(n, dtype=np.int32)
        tdlm = np.zeros(n, dtype=np.int32)

        for month_period in periods.unique():
            mask = periods == month_period
            idx_in_month = np.where(mask)[0]
            n_in_month = len(idx_in_month)
            for rank, idx in enumerate(idx_in_month):
                tdom[idx] = rank + 1         # 1er, 2ème... jour de trading du mois
                tdlm[idx] = n_in_month - rank  # jours restants (inclus)

        trading_day_of_month_arr = tdom
        trading_days_left_arr = tdlm

    return IndicatorCache(
        n_candles=n,
        opens=opens,
        highs=highs,
        lows=lows,
        closes=closes,
        volumes=volumes,
        total_days=total_days,
        ema_by_period=ema_by_period,
        adx_by_period=adx_by_period,
        atr_by_period=atr_by_period,
        rolling_high=rolling_high_dict,
        rolling_low=rolling_low_dict,
        sma_by_period=sma_by_period,
        rsi_by_period=rsi_by_period,
        ibs=ibs_arr,
        dates=dates_arr,
        trading_day_of_month=trading_day_of_month_arr,
        trading_days_left_in_month=trading_days_left_arr,
    )
