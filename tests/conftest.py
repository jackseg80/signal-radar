"""Fixtures partagées pour les tests signal-radar."""

from __future__ import annotations

import numpy as np
import pytest

from engine.backtest_config import BacktestConfig
from engine.fee_model import FeeModel
from engine.indicator_cache import IndicatorCache


@pytest.fixture
def make_indicator_cache():
    """Factory fixture pour créer un IndicatorCache avec des valeurs par défaut.

    Tous les champs sont overridables par keyword.
    """

    def _make(
        n: int = 200,
        *,
        closes: np.ndarray | None = None,
        opens: np.ndarray | None = None,
        highs: np.ndarray | None = None,
        lows: np.ndarray | None = None,
        volumes: np.ndarray | None = None,
        total_days: float | None = None,
        ema_by_period: dict[int, np.ndarray] | None = None,
        adx_by_period: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray]] | None = None,
        atr_by_period: dict[int, np.ndarray] | None = None,
        rolling_high: dict[int, np.ndarray] | None = None,
        rolling_low: dict[int, np.ndarray] | None = None,
        sma_by_period: dict[int, np.ndarray] | None = None,
        rsi_by_period: dict[int, np.ndarray] | None = None,
    ) -> IndicatorCache:
        if closes is None:
            closes = np.full(n, 100.0)
        if opens is None:
            opens = closes.copy()
        if highs is None:
            highs = closes + 1.0
        if lows is None:
            lows = closes - 1.0
        if volumes is None:
            volumes = np.full(n, 1_000_000.0)
        if total_days is None:
            total_days = n * 365.0 / 252.0
        if ema_by_period is None:
            ema_by_period = {}
        if adx_by_period is None:
            # Default : ADX = 25 partout, DI+ = 30, DI- = 20
            adx_arr = np.full(n, 25.0)
            di_plus = np.full(n, 30.0)
            di_minus = np.full(n, 20.0)
            adx_by_period = {14: (adx_arr, di_plus, di_minus)}
        if atr_by_period is None:
            atr_by_period = {14: np.full(n, 2.0)}
        if rolling_high is None:
            rolling_high = {}
        if rolling_low is None:
            rolling_low = {}
        if sma_by_period is None:
            sma_by_period = {}
        if rsi_by_period is None:
            rsi_by_period = {}

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
            rolling_high=rolling_high,
            rolling_low=rolling_low,
            sma_by_period=sma_by_period,
            rsi_by_period=rsi_by_period,
        )

    return _make


# ── Helpers pour construire les tests ──


def make_bt_config(**overrides) -> BacktestConfig:
    """Crée un BacktestConfig avec des valeurs par défaut raisonnables."""
    defaults = {
        "symbol": "TEST",
        "initial_capital": 100_000.0,
        "slippage_pct": 0.0,  # Pas de slippage par défaut dans les tests
        "max_wfo_drawdown_pct": 80.0,
        "fee_model": FeeModel(),  # Zero fees par défaut pour simplifier
    }
    defaults.update(overrides)
    return BacktestConfig(**defaults)


def default_params(**overrides) -> dict:
    """Params Donchian par défaut pour les tests."""
    defaults = {
        "entry_mode": "donchian",
        "donchian_entry_period": 20,
        "donchian_exit_period": 10,
        "ema_fast": 9,
        "ema_slow": 50,
        "adx_period": 14,
        "adx_threshold": 20.0,
        "atr_period": 14,
        "trailing_atr_mult": 4.0,
        "exit_mode": "trailing",
        "sl_percent": 10.0,
        "cooldown_candles": 3,
        "sides": ["long"],
        "position_fraction": 0.3,
    }
    defaults.update(overrides)
    return defaults


def setup_bull_cross(n: int, cross_at: int) -> tuple[np.ndarray, np.ndarray]:
    """Crée des EMA fast/slow avec un cross haussier à l'index cross_at.

    Signal détecté sur [cross_at], entrée sur opens[cross_at+1].
    """
    ema_fast = np.full(n, 95.0)
    ema_slow = np.full(n, 100.0)
    # Avant cross : fast < slow
    # Au cross : fast[cross_at] > slow[cross_at] et fast[cross_at-1] <= slow[cross_at-1]
    ema_fast[cross_at:] = 105.0
    return ema_fast, ema_slow


def setup_bear_cross(n: int, cross_at: int) -> tuple[np.ndarray, np.ndarray]:
    """Crée des EMA fast/slow avec un cross baissier à l'index cross_at."""
    ema_fast = np.full(n, 105.0)
    ema_slow = np.full(n, 100.0)
    ema_fast[cross_at:] = 95.0
    return ema_fast, ema_slow


def setup_donchian_breakout_long(
    n: int, breakout_at: int, period: int = 20,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Crée des arrays OHLC avec un breakout Donchian haussier.

    Le close[breakout_at] dépasse rolling_high[breakout_at].
    Entrée sur opens[breakout_at+1].

    Returns: (opens, highs, lows, closes, rolling_high)
    """
    closes = np.full(n, 100.0)
    opens = np.full(n, 100.0)
    highs = np.full(n, 101.0)
    lows = np.full(n, 99.0)

    # Le breakout : close[breakout_at] > rolling_high[breakout_at]
    # rolling_high[breakout_at] = max(highs[breakout_at-period : breakout_at]) = 101
    closes[breakout_at] = 102.0
    highs[breakout_at] = 103.0
    opens[breakout_at] = 100.5

    # Post-breakout : prix reste élevé
    closes[breakout_at + 1 :] = 105.0
    opens[breakout_at + 1 :] = 103.0
    highs[breakout_at + 1 :] = 106.0
    lows[breakout_at + 1 :] = 102.0

    from engine.indicators import rolling_max

    rh = rolling_max(highs, period)

    return opens, highs, lows, closes, rh
