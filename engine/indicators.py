"""Indicateurs techniques en pur numpy pour signal-radar.

Toutes les fonctions sont pures (pas d'état interne), prennent et retournent
des np.ndarray. Les premières valeurs sont NaN (période d'échauffement).

Copié depuis scalp-radar/backend/core/indicators.py — stripped des fonctions
inutiles (RSI, VWAP, Bollinger, SuperTrend, régime).
"""

from __future__ import annotations

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view


# ─── MOYENNES ────────────────────────────────────────────────────────────────


def sma(values: np.ndarray, period: int) -> np.ndarray:
    """Simple Moving Average. Les period-1 premières valeurs sont NaN."""
    if len(values) < period:
        return np.full_like(values, np.nan, dtype=float)
    result = np.full_like(values, np.nan, dtype=float)
    cumsum = np.cumsum(values)
    result[period - 1 :] = (cumsum[period - 1 :] - np.concatenate(([0], cumsum[:-period]))) / period
    return result


def _ema_loop(
    values: np.ndarray,
    result: np.ndarray,
    period: int,
    multiplier: float,
) -> np.ndarray:
    """Boucle EMA (pure Python, pas de JIT)."""
    for i in range(period, len(values)):
        result[i] = values[i] * multiplier + result[i - 1] * (1 - multiplier)
    return result


def ema(values: np.ndarray, period: int) -> np.ndarray:
    """Exponential Moving Average. Les period-1 premières valeurs sont NaN."""
    if len(values) < period:
        return np.full_like(values, np.nan, dtype=float)
    values = np.ascontiguousarray(values, dtype=np.float64)
    result = np.full_like(values, np.nan, dtype=np.float64)
    multiplier = 2.0 / (period + 1)
    # Seed : SMA des period premières valeurs
    result[period - 1] = np.mean(values[:period])
    _ema_loop(values, result, period, multiplier)
    return result


# ─── ATR (Wilder smoothing) ─────────────────────────────────────────────────


def _wilder_smooth(
    data: np.ndarray,
    result: np.ndarray,
    period: int,
    seed_val: float,
    start_idx: int,
) -> np.ndarray:
    """Wilder smoothing loop."""
    val = seed_val
    for i in range(start_idx, len(data)):
        val = (val * (period - 1) + data[i]) / period
        result[i] = val
    return result


def atr(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    period: int = 14,
) -> np.ndarray:
    """Average True Range avec lissage de Wilder.

    TR = max(high-low, |high-prev_close|, |low-prev_close|)
    Les period premières valeurs sont NaN.
    """
    if len(closes) < period + 1:
        return np.full_like(closes, np.nan, dtype=float)

    highs = np.ascontiguousarray(highs, dtype=np.float64)
    lows = np.ascontiguousarray(lows, dtype=np.float64)
    closes = np.ascontiguousarray(closes, dtype=np.float64)

    result = np.full(len(closes), np.nan, dtype=np.float64)

    # True Range (vectorisé)
    tr = np.empty(len(closes), dtype=np.float64)
    tr[0] = highs[0] - lows[0]
    tr[1:] = np.maximum(
        highs[1:] - lows[1:],
        np.maximum(np.abs(highs[1:] - closes[:-1]), np.abs(lows[1:] - closes[:-1])),
    )

    # Seed : moyenne simple
    atr_val = float(np.mean(tr[1 : period + 1]))
    result[period] = atr_val

    # Wilder smoothing
    _wilder_smooth(tr, result, period, atr_val, period + 1)
    return result


# ─── ADX + DI+/DI- ──────────────────────────────────────────────────────────


def _adx_wilder_loop(
    tr: np.ndarray,
    plus_dm: np.ndarray,
    minus_dm: np.ndarray,
    period: int,
    n: int,
    adx_arr: np.ndarray,
    di_plus_arr: np.ndarray,
    di_minus_arr: np.ndarray,
) -> None:
    """Wilder smoothing pour DI+/DI-/DX puis ADX."""
    # Seeds : somme des period premières valeurs
    sm_tr = 0.0
    sm_plus = 0.0
    sm_minus = 0.0
    for j in range(1, period + 1):
        sm_tr += tr[j]
        sm_plus += plus_dm[j]
        sm_minus += minus_dm[j]

    # DI+/DI- au premier index (period)
    if sm_tr > 0.0:
        di_plus_arr[period] = 100.0 * sm_plus / sm_tr
        di_minus_arr[period] = 100.0 * sm_minus / sm_tr
    else:
        di_plus_arr[period] = 0.0
        di_minus_arr[period] = 0.0

    # DX pré-alloué
    dx_arr = np.empty(n - period, dtype=np.float64)
    di_sum = di_plus_arr[period] + di_minus_arr[period]
    if di_sum > 0.0:
        dx_arr[0] = abs(di_plus_arr[period] - di_minus_arr[period]) / di_sum * 100.0
    else:
        dx_arr[0] = 0.0
    dx_count = 1

    for i in range(period + 1, n):
        sm_tr = sm_tr - sm_tr / period + tr[i]
        sm_plus = sm_plus - sm_plus / period + plus_dm[i]
        sm_minus = sm_minus - sm_minus / period + minus_dm[i]

        if sm_tr > 0.0:
            di_plus_arr[i] = 100.0 * sm_plus / sm_tr
            di_minus_arr[i] = 100.0 * sm_minus / sm_tr
        else:
            di_plus_arr[i] = 0.0
            di_minus_arr[i] = 0.0

        di_sum = di_plus_arr[i] + di_minus_arr[i]
        if di_sum > 0.0:
            dx_arr[dx_count] = abs(di_plus_arr[i] - di_minus_arr[i]) / di_sum * 100.0
        else:
            dx_arr[dx_count] = 0.0
        dx_count += 1

    # ADX = Wilder smoothed DX
    if dx_count >= period:
        adx_val = 0.0
        for k in range(period):
            adx_val += dx_arr[k]
        adx_val /= period
        adx_arr[2 * period - 1] = adx_val
        for k in range(period, dx_count):
            adx_val = (adx_val * (period - 1) + dx_arr[k]) / period
            target_idx = period + k
            if target_idx < n:
                adx_arr[target_idx] = adx_val


def adx(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    period: int = 14,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Average Directional Index.

    Retourne (adx, di_plus, di_minus).
    Les 2×period premières valeurs environ sont NaN.
    """
    n = len(closes)
    if n < 2 * period + 1:
        nan_arr = np.full(n, np.nan, dtype=np.float64)
        return nan_arr.copy(), nan_arr.copy(), nan_arr.copy()

    highs = np.ascontiguousarray(highs, dtype=np.float64)
    lows = np.ascontiguousarray(lows, dtype=np.float64)
    closes = np.ascontiguousarray(closes, dtype=np.float64)

    adx_arr = np.full(n, np.nan, dtype=np.float64)
    di_plus_arr = np.full(n, np.nan, dtype=np.float64)
    di_minus_arr = np.full(n, np.nan, dtype=np.float64)

    # +DM, -DM et TR (vectorisé)
    plus_dm = np.zeros(n, dtype=np.float64)
    minus_dm = np.zeros(n, dtype=np.float64)
    tr = np.zeros(n, dtype=np.float64)

    tr[0] = highs[0] - lows[0]
    tr[1:] = np.maximum(
        highs[1:] - lows[1:],
        np.maximum(np.abs(highs[1:] - closes[:-1]), np.abs(lows[1:] - closes[:-1])),
    )

    up = highs[1:] - highs[:-1]
    down = lows[:-1] - lows[1:]
    plus_dm[1:] = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm[1:] = np.where((down > up) & (down > 0), down, 0.0)

    _adx_wilder_loop(tr, plus_dm, minus_dm, period, n, adx_arr, di_plus_arr, di_minus_arr)
    return adx_arr, di_plus_arr, di_minus_arr


# ─── Rolling High/Low (Donchian channels) ───────────────────────────────────


def rolling_max(arr: np.ndarray, window: int) -> np.ndarray:
    """Rolling max sur fenêtre glissante (exclut l'élément courant).

    rolling_max[i] = max(arr[i-window:i]). NaN avant window.
    Vectorisé via sliding_window_view.
    """
    result = np.full_like(arr, np.nan, dtype=float)
    n = len(arr)
    if n > window:
        views = sliding_window_view(arr, window)
        result[window:] = np.max(views[: n - window], axis=1)
    return result


def rolling_min(arr: np.ndarray, window: int) -> np.ndarray:
    """Rolling min sur fenêtre glissante (exclut l'élément courant).

    rolling_min[i] = min(arr[i-window:i]). NaN avant window.
    Vectorisé via sliding_window_view.
    """
    result = np.full_like(arr, np.nan, dtype=float)
    n = len(arr)
    if n > window:
        views = sliding_window_view(arr, window)
        result[window:] = np.min(views[: n - window], axis=1)
    return result
