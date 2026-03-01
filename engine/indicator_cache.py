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

from engine.indicators import adx, atr, ema, rolling_max, rolling_min


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


def build_cache(
    arrays: dict[str, np.ndarray],
    param_grid_values: dict[str, list],
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

    # --- Rolling high/low pour Donchian channels ---
    lookbacks: set[int] = set()
    for key in ("donchian_entry_period", "donchian_exit_period"):
        if key in param_grid_values:
            lookbacks.update(param_grid_values[key])
    rolling_high_dict = {lb: rolling_max(highs, lb) for lb in lookbacks}
    rolling_low_dict = {lb: rolling_min(lows, lb) for lb in lookbacks}

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
    )
