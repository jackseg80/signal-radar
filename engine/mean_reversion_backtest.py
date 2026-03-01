"""DEPRECATED — Ancien moteur mean reversion.

Remplace par :
  - engine/simulator.py (moteur generique)
  - strategies/rsi2_mean_reversion.py (strategie plugin)

Conserve pour reference historique et pour verify_migration.py.
Utiliser ``simulate(RSI2MeanReversion(), ...)`` pour tout nouveau backtest.

---

Moteur de backtest mean reversion RSI(2) Connors pour signal-radar.

Strategie long-only sur Daily. Achete les pullbacks RSI(2) dans une
tendance haussiere (close > SMA trend), sort quand le prix remonte
au-dessus de SMA(5) (exit Connors classique).

Structure boucle gap-aware par candle :
  Phase 1 : Gap-aware SL at open (si sl_percent > 0)
  Phase 2 : Intraday SL (si sl_percent > 0)
  Phase 3 : SMA exit -- closes[i] > sma_exit[i] -> exit closes[i]
  Phase 4 : RSI exit -- rsi_arr[i] > rsi_exit_threshold -> exit closes[i]
  Phase 5 : Trend break -- closes[i] < sma_trend[i] -> exit closes[i]

Signal sur candle [i-1], entree sur open[i] (pas de look-ahead).
Exits Connors = "on close" (decision et prix sur candle i).
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from engine.backtest_config import BacktestConfig
from engine.fast_backtest import ISResult, _close_trend_position, _compute_fast_metrics
from engine.indicator_cache import IndicatorCache


def _simulate_mean_reversion(
    cache: IndicatorCache,
    params: dict[str, Any],
    config: BacktestConfig,
    holding_days_out: list[int] | None = None,
) -> tuple[list[float], list[float], float]:
    """Simulation Mean Reversion RSI(2) Connors sur Daily.

    Long only. Achète les pullbacks RSI dans une tendance SMA haussière.

    Parameters
    ----------
    cache : IndicatorCache
        Cache pré-calculé avec SMA et RSI.
    params : dict
        Paramètres de la stratégie (voir run_mr_backtest_from_cache).
    config : BacktestConfig
        Configuration du backtest.
    holding_days_out : list[int] | None
        Si fourni, reçoit le nombre de candles de holding par trade clos.

    Returns
    -------
    tuple[list[float], list[float], float]
        (trade_pnls, trade_returns, final_capital)
    """
    # -- Params --
    rsi_period: int = params.get("rsi_period", 2)
    rsi_entry_threshold: float = params.get("rsi_entry_threshold", 5.0)
    sma_trend_period: int = params.get("sma_trend_period", 200)
    sma_exit_period: int = params.get("sma_exit_period", 5)
    rsi_exit_threshold: float = params.get("rsi_exit_threshold", 0.0)
    sl_pct: float = params.get("sl_percent", 0.0) / 100.0
    position_fraction: float = params.get("position_fraction", 0.2)
    cooldown: int = params.get("cooldown_candles", 0)
    sma_trend_buffer: float = params.get("sma_trend_buffer", 1.0)

    # -- Arrays from cache --
    n = cache.n_candles
    opens = cache.opens
    closes = cache.closes
    lows = cache.lows

    sma_trend = cache.sma_by_period[sma_trend_period]
    sma_exit = cache.sma_by_period[sma_exit_period]
    rsi_arr = cache.rsi_by_period[rsi_period]

    # -- Config --
    capital = config.initial_capital
    fee_model = config.fee_model
    slippage_pct = config.slippage_pct
    max_dd_pct = config.max_wfo_drawdown_pct / 100.0

    trade_pnls: list[float] = []
    trade_returns: list[float] = []

    # -- State --
    in_position = False
    entry_price = 0.0
    quantity = 0.0
    entry_fee = 0.0
    capital_allocated = 0.0
    sl_price = 0.0
    entry_candle = -1
    cooldown_remaining = 0
    peak_capital = capital

    # -- Warmup --
    warmup = max(sma_trend_period, sma_exit_period, rsi_period + 1) + 2

    # -- Exit helper --
    def _exit(exit_price: float, candle_idx: int) -> None:
        nonlocal capital, in_position, cooldown_remaining, peak_capital
        n_holding_days = candle_idx - entry_candle
        pnl = _close_trend_position(
            1,  # toujours LONG
            entry_price, exit_price, quantity,
            fee_model, entry_fee, n_holding_days,
        )
        capital += capital_allocated + pnl
        if capital > 0:
            trade_pnls.append(pnl)
            trade_returns.append(pnl / capital)
            if holding_days_out is not None:
                holding_days_out.append(n_holding_days)
        peak_capital = max(peak_capital, capital)
        in_position = False
        cooldown_remaining = cooldown

    # -- Main loop --
    for i in range(warmup, n):
        # DD guard
        equity = capital + (capital_allocated if in_position else 0.0)
        if equity < peak_capital * (1 - max_dd_pct):
            break

        # =======================================================
        # IF IN POSITION : EXIT CHECKS
        # =======================================================
        if in_position:
            # Phase 1 : Gap-aware SL at open
            if sl_pct > 0 and opens[i] <= sl_price:
                _exit(opens[i], i)
                continue

            # Phase 2 : Intraday SL
            if sl_pct > 0 and lows[i] <= sl_price:
                _exit(sl_price * (1 - slippage_pct), i)
                continue

            close_i = closes[i]

            # Phase 3 : SMA exit — close > sma_exit → exit at close
            sma_exit_val = sma_exit[i]
            if not math.isnan(sma_exit_val) and close_i > sma_exit_val:
                _exit(close_i, i)
                continue

            # Phase 4 : RSI exit — rsi[i] > threshold → exit at close
            if rsi_exit_threshold > 0:
                rsi_val = rsi_arr[i]
                if not math.isnan(rsi_val) and rsi_val > rsi_exit_threshold:
                    _exit(close_i, i)
                    continue

            # Phase 5 : Trend break — close < sma_trend → exit at close
            sma_trend_val = sma_trend[i]
            if not math.isnan(sma_trend_val) and close_i < sma_trend_val:
                _exit(close_i, i)
                continue

            # Toujours en position
            continue

        # =======================================================
        # NOT IN POSITION : ENTRY CHECKS
        # =======================================================
        if cooldown_remaining > 0:
            cooldown_remaining -= 1
            continue

        prev = i - 1

        # Trend filter : close[i-1] > sma_trend[i-1] * buffer
        sma_trend_prev = sma_trend[prev]
        if math.isnan(sma_trend_prev):
            continue
        if closes[prev] <= sma_trend_prev * sma_trend_buffer:
            continue

        # RSI entry : rsi[i-1] < threshold
        rsi_prev = rsi_arr[prev]
        if math.isnan(rsi_prev):
            continue
        if rsi_prev >= rsi_entry_threshold:
            continue

        # === ENTRY ===
        entry_price = opens[i] * (1 + slippage_pct)
        available = capital * position_fraction
        quantity = available / entry_price
        entry_notional = quantity * entry_price
        entry_fee = fee_model.total_entry_cost(entry_notional)
        capital_allocated = available
        capital -= capital_allocated

        if sl_pct > 0:
            sl_price = entry_price * (1 - sl_pct)
        else:
            sl_price = 0.0

        in_position = True
        entry_candle = i

        # -- Exit checks sur le jour d'entrée (phases 2-5) --

        # Intraday SL on entry day
        if sl_pct > 0 and lows[i] <= sl_price:
            _exit(sl_price * (1 - slippage_pct), i)
            continue

        close_i = closes[i]

        # SMA exit on entry day
        sma_exit_val = sma_exit[i]
        if not math.isnan(sma_exit_val) and close_i > sma_exit_val:
            _exit(close_i, i)
            continue

        # RSI exit on entry day
        if rsi_exit_threshold > 0:
            rsi_val = rsi_arr[i]
            if not math.isnan(rsi_val) and rsi_val > rsi_exit_threshold:
                _exit(close_i, i)
                continue

        # Trend break on entry day
        sma_trend_val = sma_trend[i]
        if not math.isnan(sma_trend_val) and close_i < sma_trend_val:
            _exit(close_i, i)
            continue

    # Force-close fin de données — PAS dans trade_pnls (convention)
    if in_position:
        n_holding_days = (n - 1) - entry_candle
        exit_price = closes[n - 1]
        pnl = _close_trend_position(
            1, entry_price, exit_price, quantity,
            fee_model, entry_fee, n_holding_days,
        )
        capital += capital_allocated + pnl

    return trade_pnls, trade_returns, capital


def run_mr_backtest_from_cache(
    params: dict[str, Any],
    cache: IndicatorCache,
    config: BacktestConfig,
) -> ISResult:
    """Point d'entrée : backtest mean reversion depuis un IndicatorCache.

    Parameters
    ----------
    params : dict
        Paramètres mean reversion::

            {
                "strategy_type": "mean_reversion",
                "rsi_period": 2,
                "rsi_entry_threshold": 5.0,
                "sma_trend_period": 200,
                "sma_exit_period": 5,
                "rsi_exit_threshold": 65.0,  # 0 = désactivé
                "sl_percent": 0.0,           # 0 = pas de SL (Connors)
                "position_fraction": 0.2,
                "cooldown_candles": 0,
                "sma_trend_buffer": 1.0,
            }

    cache : IndicatorCache
        Cache pré-calculé (doit contenir sma_by_period et rsi_by_period).
    config : BacktestConfig
        Configuration du backtest.

    Returns
    -------
    ISResult
        (params, sharpe, net_return_pct, profit_factor, n_trades)
    """
    trade_pnls, trade_returns, final_capital = _simulate_mean_reversion(
        cache, params, config,
    )
    return _compute_fast_metrics(
        params, trade_pnls, trade_returns, final_capital,
        config.initial_capital, cache.total_days,
    )
