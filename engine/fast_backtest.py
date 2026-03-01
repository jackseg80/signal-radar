"""DEPRECATED — Ancien moteur trend following.

Remplace par :
  - engine/simulator.py (moteur generique)
  - strategies/donchian_trend.py (strategie plugin)

Conserve pour reference historique et pour verify_migration.py.
Utiliser ``simulate(DonchianTrend(), ...)`` pour tout nouveau backtest.

---

Moteur de backtest trend following gap-aware pour signal-radar.

Adapte depuis scalp-radar/backend/optimization/fast_multi_backtest.py.
Changements critiques :
1. Gap-aware exits — exit a l'open si gap traverse le stop (pas au prix du stop)
2. FeeModel — remplace le flat taker_fee crypto
3. n_holding_days — tracking duree de detention pour cout overnight
4. Pas de leverage — position sizing simple (fraction du capital)
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from engine.backtest_config import BacktestConfig
from engine.fee_model import FeeModel
from engine.indicator_cache import IndicatorCache

# Type alias pour le résultat d'un backtest
ISResult = tuple[dict[str, Any], float, float, float, int]
# (params, sharpe, net_return_pct, profit_factor, n_trades)


def _close_trend_position(
    direction: int,
    entry_price: float,
    exit_price: float,
    quantity: float,
    fee_model: FeeModel,
    entry_fee: float,
    n_holding_days: int,
) -> float:
    """Calcule le PnL net d'une position trend follow avec FeeModel."""
    if direction == 1:
        gross_pnl = (exit_price - entry_price) * quantity
    else:
        gross_pnl = (entry_price - exit_price) * quantity

    exit_notional = exit_price * quantity
    exit_fee = fee_model.total_exit_cost(exit_notional)
    entry_notional = entry_price * quantity
    overnight = fee_model.overnight_cost(entry_notional, n_holding_days)

    return gross_pnl - entry_fee - exit_fee - overnight


def _simulate_trend_follow(
    cache: IndicatorCache,
    params: dict[str, Any],
    config: BacktestConfig,
    daily_equity_out: np.ndarray | None = None,
) -> tuple[list[float], list[float], float]:
    """Simulation Trend Following sur Daily (EMA cross ou Donchian breakout).

    Moteur gap-aware pour actions/forex. Position unique, trailing stop ATR /
    channel exit, SL fixe.

    Entry modes:
    - "ema_cross": EMA fast/slow crossover
    - "donchian": N-day channel breakout (Turtle Traders)

    Exit modes:
    - "trailing": ATR trailing stop
    - "signal": EMA cross inverse (ema_cross entry only)
    - "channel": Donchian exit channel (donchian entry only)

    Structure boucle gap-aware par candle :
    1. Gap check à l'ouverture (exit à opens[i] si gap traverse stop)
    2. Update trailing (gap favorable)
    3. SL/trailing intraday (SL prime sur trailing via elif)
    4. Channel exit (sur close[i])

    Signal sur candle [i-1], entrée sur open[i] (pas de look-ahead).
    """
    # ── Params ──
    entry_mode = params.get("entry_mode", "ema_cross")
    ema_fast_period = params.get("ema_fast", 9)
    ema_slow_period = params.get("ema_slow", 50)
    donchian_entry_period = params.get("donchian_entry_period", 50)
    donchian_exit_period = params.get("donchian_exit_period", 20)
    adx_period = params.get("adx_period", 14)
    adx_threshold = params.get("adx_threshold", 20.0)
    atr_period = params.get("atr_period", 14)
    trailing_atr_mult = params.get("trailing_atr_mult", 4.0)
    exit_mode = params.get("exit_mode", "trailing")
    sl_pct = params["sl_percent"] / 100.0
    cooldown = params.get("cooldown_candles", 3)
    sides = params.get("sides", ["long"])
    position_fraction = params.get("position_fraction", 0.3)
    allow_long = "long" in sides
    allow_short = "short" in sides

    # ── Déduplication : normaliser les params non utilisés ──
    if entry_mode == "donchian":
        ema_fast_period = 9
        ema_slow_period = 50
    else:
        donchian_entry_period = 50
        donchian_exit_period = 20
    if exit_mode == "signal":
        trailing_atr_mult = 0.0
    if exit_mode == "channel" and entry_mode != "donchian":
        exit_mode = "trailing"

    # ── Arrays depuis le cache ──
    n = cache.n_candles
    opens = cache.opens
    highs = cache.highs
    lows = cache.lows
    closes = cache.closes

    # ADX — le cache stocke (adx, di_plus, di_minus) mais on n'utilise que adx pour le filtre
    adx_tuple = cache.adx_by_period.get(adx_period)
    adx_arr = adx_tuple[0] if adx_tuple is not None else None

    atr_arr = cache.atr_by_period[atr_period]

    # Arrays spécifiques au mode d'entrée
    if entry_mode == "ema_cross":
        ema_fast = cache.ema_by_period[ema_fast_period]
        ema_slow = cache.ema_by_period[ema_slow_period]
        rolling_high_entry = None
        rolling_low_entry = None
        rolling_high_exit = None
        rolling_low_exit = None
    else:  # donchian
        ema_fast = None
        ema_slow = None
        rolling_high_entry = cache.rolling_high[donchian_entry_period]
        rolling_low_entry = cache.rolling_low[donchian_entry_period]
        if exit_mode == "channel":
            rolling_high_exit = cache.rolling_high[donchian_exit_period]
            rolling_low_exit = cache.rolling_low[donchian_exit_period]
        else:
            rolling_high_exit = None
            rolling_low_exit = None

    # ── Config ──
    capital = config.initial_capital
    fee_model = config.fee_model
    slippage_pct = config.slippage_pct
    max_dd_pct = config.max_wfo_drawdown_pct / 100.0

    trade_pnls: list[float] = []
    trade_returns: list[float] = []

    # ── State ──
    in_position = False
    direction = 0          # +1 LONG, -1 SHORT
    entry_price = 0.0
    quantity = 0.0
    entry_fee = 0.0
    capital_allocated = 0.0  # capital locked (available + entry_fee)
    trailing_level = 0.0
    sl_price = 0.0
    hwm = 0.0              # High Water Mark (LONG) / Low Water Mark (SHORT)
    entry_candle = -1
    cooldown_remaining = 0
    peak_capital = capital

    # ── Warmup ──
    if entry_mode == "ema_cross":
        warmup = max(ema_slow_period, adx_period * 2 if adx_arr is not None else 0) + 2
    else:
        warmup = max(
            donchian_entry_period,
            donchian_exit_period if exit_mode == "channel" else 0,
            adx_period * 2 if adx_arr is not None else 0,
        ) + 2

    # ── Helper : fermer position et enregistrer trade ──
    def _exit(exit_price: float, candle_idx: int) -> None:
        nonlocal capital, in_position, cooldown_remaining, peak_capital
        n_holding_days = candle_idx - entry_candle
        pnl = _close_trend_position(
            direction, entry_price, exit_price, quantity,
            fee_model, entry_fee, n_holding_days,
        )
        capital += capital_allocated + pnl
        if capital > 0:
            trade_pnls.append(pnl)
            trade_returns.append(pnl / capital)
        peak_capital = max(peak_capital, capital)
        in_position = False
        cooldown_remaining = cooldown

    # ── Initialiser daily equity (warmup = capital flat) ──
    if daily_equity_out is not None:
        for j in range(warmup):
            daily_equity_out[j] = capital

    # ══════════════════════════════════════════════════════════════════════
    # BOUCLE PRINCIPALE
    # ══════════════════════════════════════════════════════════════════════
    for i in range(warmup, n):
        # DD guard — equity = capital + capital en position
        equity = capital + (capital_allocated if in_position else 0.0)
        if equity < peak_capital * (1 - max_dd_pct):
            break

        prev = i - 1

        # ADX check (partagé par les deux modes d'entrée)
        adx_ok = True
        if adx_arr is not None and adx_threshold > 0:
            adx_val = adx_arr[prev]
            if math.isnan(adx_val) or adx_val < adx_threshold:
                adx_ok = False

        atr_val = atr_arr[prev] if not math.isnan(atr_arr[prev]) else 0.0

        # ==========================================================
        # PHASE ENTRÉE (si pas en position et pas en cooldown)
        # ==========================================================
        if not in_position:
            if cooldown_remaining > 0:
                cooldown_remaining -= 1
                continue

            bull_signal = False
            bear_signal = False

            if entry_mode == "ema_cross":
                ef_prev = ema_fast[prev]
                es_prev = ema_slow[prev]
                ef_prev2 = ema_fast[prev - 1]
                es_prev2 = ema_slow[prev - 1]
                if (
                    math.isnan(ef_prev)
                    or math.isnan(es_prev)
                    or math.isnan(ef_prev2)
                    or math.isnan(es_prev2)
                ):
                    continue
                bull_signal = ef_prev > es_prev and ef_prev2 <= es_prev2
                bear_signal = ef_prev < es_prev and ef_prev2 >= es_prev2

            else:  # donchian
                rh = rolling_high_entry[prev]
                rl = rolling_low_entry[prev]
                if math.isnan(rh) or math.isnan(rl):
                    continue
                close_prev = closes[prev]
                bull_signal = close_prev > rh
                bear_signal = close_prev < rl

            if bull_signal and allow_long and adx_ok:
                direction = 1
                entry_price = opens[i] * (1 + slippage_pct)
                available = capital * position_fraction
                quantity = available / entry_price
                entry_notional = quantity * entry_price
                entry_fee = fee_model.total_entry_cost(entry_notional)
                capital_allocated = available
                capital -= capital_allocated

                sl_price = entry_price * (1 - sl_pct)
                hwm = entry_price

                if exit_mode == "trailing" and atr_val > 0:
                    trailing_level = entry_price - atr_val * trailing_atr_mult
                else:
                    trailing_level = 0.0

                in_position = True
                entry_candle = i
                # PAS de continue — PHASE SORTIE vérifie SL le jour même

            elif bear_signal and allow_short and adx_ok:
                direction = -1
                entry_price = opens[i] * (1 - slippage_pct)
                available = capital * position_fraction
                quantity = available / entry_price
                entry_notional = quantity * entry_price
                entry_fee = fee_model.total_entry_cost(entry_notional)
                capital_allocated = available
                capital -= capital_allocated

                sl_price = entry_price * (1 + sl_pct)
                hwm = entry_price  # Low Water Mark pour SHORT

                if exit_mode == "trailing" and atr_val > 0:
                    trailing_level = entry_price + atr_val * trailing_atr_mult
                else:
                    trailing_level = float("inf")

                in_position = True
                entry_candle = i

            else:
                continue

        # ==========================================================
        # PHASE SORTIE — gap-aware
        # ==========================================================
        if not in_position:
            continue

        open_i = opens[i]
        high_i = highs[i]
        low_i = lows[i]
        close_i = closes[i]

        # ── ÉTAPE 1 : Gap check à l'ouverture ──
        # Si l'open traverse le SL ou le trailing, exit immédiat à l'open
        if direction == 1:
            if open_i <= sl_price or (trailing_level > 0 and open_i <= trailing_level):
                _exit(open_i, i)
                continue
        else:  # SHORT
            if open_i >= sl_price or (trailing_level < float("inf") and open_i >= trailing_level):
                _exit(open_i, i)
                continue

        # ── ÉTAPE 2 : Update trailing (gap favorable, pas de gap adverse) ──
        # Day 0 : pas de mise à jour trailing
        if exit_mode == "trailing" and atr_val > 0 and i > entry_candle:
            if direction == 1:
                if high_i > hwm:
                    hwm = high_i
                    trailing_level = hwm - atr_val * trailing_atr_mult
            else:
                if low_i < hwm:
                    hwm = low_i
                    trailing_level = hwm + atr_val * trailing_atr_mult

        # ── ÉTAPE 3 : SL/trailing intraday (après update) ──
        # SL PRIME sur trailing (elif) — le SL est plus éloigné,
        # si SL touché le trailing l'est aussi, on prend le pire cas.
        if direction == 1:
            if low_i <= sl_price:
                _exit(sl_price * (1 - slippage_pct), i)
                continue
            elif i > entry_candle and trailing_level > 0 and low_i <= trailing_level:
                _exit(trailing_level * (1 - slippage_pct), i)
                continue
        else:  # SHORT
            if high_i >= sl_price:
                _exit(sl_price * (1 + slippage_pct), i)
                continue
            elif i > entry_candle and trailing_level < float("inf") and high_i >= trailing_level:
                _exit(trailing_level * (1 + slippage_pct), i)
                continue

        # ── ÉTAPE 4 : Channel exit (sur close[i]) ──
        if exit_mode == "channel" and i > entry_candle:
            if direction == 1:
                ch = rolling_low_exit[prev]
                if not math.isnan(ch) and close_i < ch:
                    _exit(close_i, i)
                    continue
            else:
                ch = rolling_high_exit[prev]
                if not math.isnan(ch) and close_i > ch:
                    _exit(close_i, i)
                    continue

        # ── ÉTAPE 5 : Signal inverse (exit_mode=="signal", ema_cross only) ──
        if exit_mode == "signal" and entry_mode == "ema_cross":
            ef_prev = ema_fast[prev]
            es_prev = ema_slow[prev]
            ef_prev2 = ema_fast[prev - 1]
            es_prev2 = ema_slow[prev - 1]
            if direction == 1 and ef_prev < es_prev and ef_prev2 >= es_prev2:
                _exit(opens[i] * (1 - slippage_pct), i)
                continue
            elif direction == -1 and ef_prev > es_prev and ef_prev2 <= es_prev2:
                _exit(opens[i] * (1 + slippage_pct), i)
                continue

        # ── Daily equity tracking (fin de candle i) ──
        if daily_equity_out is not None:
            if in_position:
                unrealized = (closes[i] - entry_price) * quantity * direction
                daily_equity_out[i] = capital + capital_allocated + unrealized
            else:
                daily_equity_out[i] = capital

    # Force-close fin de données — N'AJOUTE PAS à trade_pnls (convention)
    if in_position:
        n_holding_days = (n - 1) - entry_candle
        exit_price = closes[n - 1]
        pnl = _close_trend_position(
            direction, entry_price, exit_price, quantity,
            fee_model, entry_fee, n_holding_days,
        )
        capital += capital_allocated + pnl

    return trade_pnls, trade_returns, capital


def _compute_fast_metrics(
    params: dict[str, Any],
    trade_pnls: list[float],
    trade_returns: list[float],
    final_capital: float,
    initial_capital: float,
    total_days: float,
) -> ISResult:
    """Calcule les métriques (sharpe, return, PF) sans objets lourds.

    Copié exactement depuis scalp-radar — purement mathématique.
    """
    n_trades = len(trade_pnls)

    if n_trades == 0:
        return (params, 0.0, 0.0, 0.0, 0)

    net_return_pct = sum(trade_pnls) / initial_capital * 100

    net_wins = sum(p for p in trade_pnls if p > 0)
    net_losses = abs(sum(p for p in trade_pnls if p <= 0))
    profit_factor = net_wins / net_losses if net_losses > 0 else float("inf")

    sharpe = 0.0
    if n_trades >= 3 and len(trade_returns) >= 2:
        arr = np.array(trade_returns)
        std = float(np.std(arr))
        if std > 1e-10:
            trades_per_year = n_trades / max(total_days, 1) * 365
            sharpe = float(np.mean(arr) / std * np.sqrt(trades_per_year))
            sharpe = min(100.0, sharpe)

    return (params, sharpe, net_return_pct, profit_factor, n_trades)


def run_backtest_from_cache(
    params: dict[str, Any],
    cache: IndicatorCache,
    config: BacktestConfig,
) -> ISResult:
    """Point d'entrée : backtest trend follow depuis un IndicatorCache.

    Returns
    -------
    ISResult
        (params, sharpe, net_return_pct, profit_factor, n_trades)
    """
    trade_pnls, trade_returns, final_capital = _simulate_trend_follow(
        cache, params, config,
    )
    return _compute_fast_metrics(
        params, trade_pnls, trade_returns, final_capital,
        config.initial_capital, cache.total_days,
    )
