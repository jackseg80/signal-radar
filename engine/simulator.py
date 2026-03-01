"""Moteur de simulation unique pour toutes les stratégies.

Remplace fast_backtest._simulate_trend_follow et
mean_reversion_backtest._simulate_mean_reversion par un moteur générique.

Le moteur gère :
- Position sizing (fractional ou whole shares)
- Fee model (entry + exit fees + overnight)
- Gap-aware exits (gap past SL → exit at open, pas au SL)
- Intraday SL check (avec slippage)
- Strategy exit slippage (via ExitSignal.apply_slippage)
- Force-close fin de données (exclus des résultats)
- Anti-look-ahead (signal sur [i-1], action sur open[i])
- Same-candle exit check (entry + exit possible sur la même candle)
- Cooldown après sortie
- DD guard (drawdown max → arrêt)

La stratégie fournit :
- check_entry(i) → Direction
- check_exit(i) → ExitSignal | None
- init_state() → dict initial pour Position.state
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from engine.backtest_config import BacktestConfig
from engine.indicator_cache import IndicatorCache
from engine.types import (
    BacktestResult,
    Direction,
    ExitSignal,
    Position,
    TradeResult,
)

if TYPE_CHECKING:
    from strategies.base import BaseStrategy


def _close_position(
    position: Position,
    exit_price: float,
    reason: str,
    i: int,
    config: BacktestConfig,
) -> tuple[TradeResult, float]:
    """Ferme une position et retourne (TradeResult, pnl_net).

    Le pnl_net inclut entry_fee, exit_fee et overnight cost.
    ATTENTION : ne PAS soustraire entry_fee du capital séparément —
    elle est déjà dans le pnl (bug Phase 1 corrigé).
    """
    direction = position.direction
    n_holding_days = i - position.entry_candle

    # Gross PnL
    gross_pnl = direction * (exit_price - position.entry_price) * position.quantity

    # Exit fee
    exit_notional = exit_price * position.quantity
    exit_fee = config.fee_model.total_exit_cost(exit_notional)

    # Overnight cost
    entry_notional = position.entry_price * position.quantity
    overnight = config.fee_model.overnight_cost(entry_notional, n_holding_days)

    # Net PnL (entry_fee incluse ici, PAS soustraite du capital séparément)
    pnl = gross_pnl - position.entry_fee - exit_fee - overnight

    # Return sur capital investi (pas sur capital total)
    return_pct = pnl / position.capital_allocated if position.capital_allocated > 0 else 0.0

    trade = TradeResult(
        direction=direction,
        entry_price=position.entry_price,
        exit_price=exit_price,
        entry_candle=position.entry_candle,
        exit_candle=i,
        quantity=position.quantity,
        pnl=pnl,
        return_pct=return_pct,
        holding_days=n_holding_days,
        exit_reason=reason,
        entry_fee=position.entry_fee,
        exit_fee=exit_fee,
    )
    return trade, pnl


def _try_exit_position(
    position: Position,
    exit_signal: ExitSignal,
    i: int,
    config: BacktestConfig,
    capital: float,
    trades: list[TradeResult],
) -> tuple[float, bool]:
    """Tente de fermer la position via un ExitSignal.

    Applique le slippage directionnel si apply_slippage est True.
    Enregistre le trade si capital > 0 après fermeture.

    Returns:
        (updated_capital, position_closed)
    """
    exit_price = exit_signal.price
    if exit_signal.apply_slippage:
        exit_price *= 1 - position.direction * config.slippage_pct

    trade, pnl = _close_position(position, exit_price, exit_signal.reason, i, config)
    capital += position.capital_allocated + pnl
    if capital > 0:
        trades.append(trade)
    return capital, True


def simulate(
    strategy: BaseStrategy,
    cache: IndicatorCache,
    params: dict,
    config: BacktestConfig,
    *,
    start_idx: int | None = None,
    end_idx: int | None = None,
) -> BacktestResult:
    """Simule une stratégie sur un jeu de données.

    Boucle principale fidèle aux moteurs existants :
    - fast_backtest._simulate_trend_follow() lignes 198-391
    - mean_reversion_backtest._simulate_mean_reversion() lignes 120-241

    Args:
        strategy: Stratégie implémentant BaseStrategy
        cache: Cache indicateurs pré-calculés
        params: Paramètres de la stratégie
        config: Configuration du backtest
        start_idx: Indice de début de la boucle (défaut: warmup).
            Doit être >= warmup. Utile pour OOS: cache construit sur
            toute la période, simulate() restreint à [start_idx, end_idx).
        end_idx: Indice de fin de la boucle (défaut: n_candles).

    Returns:
        BacktestResult avec trades, capital final, et compteur skipped
    """
    # -- Config --
    n = cache.n_candles
    opens = cache.opens
    highs = cache.highs
    lows = cache.lows
    slippage_pct = config.slippage_pct
    max_dd_pct = config.max_wfo_drawdown_pct / 100.0

    # -- State --
    capital = config.initial_capital
    position: Position | None = None
    trades: list[TradeResult] = []
    n_skipped = 0
    cooldown_remaining = 0
    peak_capital = capital

    # -- Warmup --
    warmup = strategy.warmup(params)

    # -- Loop bounds --
    loop_start = max(warmup, start_idx) if start_idx is not None else warmup
    loop_end = end_idx if end_idx is not None else n

    if start_idx is not None and start_idx < warmup:
        raise ValueError(
            f"start_idx ({start_idx}) < warmup ({warmup}). "
            f"Les indicateurs ne sont pas valides avant le warmup."
        )

    # -- Params communs --
    position_fraction: float = params.get("position_fraction", 1.0)
    sl_pct: float = params.get("sl_percent", 0.0) / 100.0
    cooldown_candles: int = params.get("cooldown_candles", 0)

    # ══════════════════════════════════════════════════════════════════
    # BOUCLE PRINCIPALE
    # ══════════════════════════════════════════════════════════════════
    for i in range(loop_start, loop_end):
        # DD guard
        equity = capital + (position.capital_allocated if position is not None else 0.0)
        if equity < peak_capital * (1 - max_dd_pct):
            break

        # ==============================================================
        # EN POSITION : EXIT CHECKS
        # ==============================================================
        if position is not None:
            direction = position.direction

            # -- Phase 1 : Gap SL check (si sl_price > 0) --
            if position.sl_price > 0:
                gap_triggered = False
                if direction == Direction.LONG and opens[i] <= position.sl_price:
                    gap_triggered = True
                elif direction == Direction.SHORT and opens[i] >= position.sl_price:
                    gap_triggered = True

                if gap_triggered:
                    trade, pnl = _close_position(
                        position, opens[i], "gap_sl", i, config,
                    )
                    capital += position.capital_allocated + pnl
                    if capital > 0:
                        trades.append(trade)
                    peak_capital = max(peak_capital, capital)
                    position = None
                    cooldown_remaining = cooldown_candles
                    continue

                # -- Phase 2 : Intraday SL check --
                intraday_triggered = False
                if direction == Direction.LONG and lows[i] <= position.sl_price:
                    intraday_triggered = True
                elif direction == Direction.SHORT and highs[i] >= position.sl_price:
                    intraday_triggered = True

                if intraday_triggered:
                    # Slippage sur SL : prix dégradé dans la direction du stop
                    sl_exit_price = position.sl_price * (1 - direction * slippage_pct)
                    trade, pnl = _close_position(
                        position, sl_exit_price, "intraday_sl", i, config,
                    )
                    capital += position.capital_allocated + pnl
                    if capital > 0:
                        trades.append(trade)
                    peak_capital = max(peak_capital, capital)
                    position = None
                    cooldown_remaining = cooldown_candles
                    continue

            # -- Phase 3 : Strategy exit --
            exit_signal = strategy.check_exit(i, cache, params, position)
            if exit_signal is not None:
                capital, _ = _try_exit_position(
                    position, exit_signal, i, config, capital, trades,
                )
                peak_capital = max(peak_capital, capital)
                position = None
                cooldown_remaining = cooldown_candles
                continue

            # Toujours en position
            continue

        # ==============================================================
        # PAS EN POSITION : ENTRY CHECKS
        # ==============================================================
        if cooldown_remaining > 0:
            cooldown_remaining -= 1
            continue

        # -- Phase 4 : Strategy entry --
        direction = strategy.check_entry(i, cache, params)
        if direction == Direction.FLAT:
            continue

        # -- Sizing --
        available = capital * position_fraction
        entry_price = opens[i] * (1 + direction * slippage_pct)
        quantity = available / entry_price

        if config.whole_shares:
            quantity = math.floor(quantity)
            if quantity < 1:
                n_skipped += 1
                continue

        # -- Fees --
        notional = quantity * entry_price
        entry_fee = config.fee_model.total_entry_cost(notional)

        # -- SL price --
        if sl_pct > 0:
            if direction == Direction.LONG:
                sl_price = entry_price * (1 - sl_pct)
            else:
                sl_price = entry_price * (1 + sl_pct)
        else:
            sl_price = 0.0

        # -- Init state --
        state = strategy.init_state(entry_price, i, cache, params, direction=direction)

        # -- Create position --
        capital_allocated = notional
        position = Position(
            entry_price=entry_price,
            entry_candle=i,
            quantity=quantity,
            direction=direction,
            capital_allocated=capital_allocated,
            entry_fee=entry_fee,
            sl_price=sl_price,
            state=state,
        )
        capital -= capital_allocated

        # ==============================================================
        # SAME-CANDLE EXIT CHECK (pas de gap SL — on vient d'entrer au open)
        # ==============================================================

        # -- Intraday SL on entry day --
        if sl_pct > 0:
            intraday_triggered = False
            if direction == Direction.LONG and lows[i] <= position.sl_price:
                intraday_triggered = True
            elif direction == Direction.SHORT and highs[i] >= position.sl_price:
                intraday_triggered = True

            if intraday_triggered:
                sl_exit_price = position.sl_price * (1 - direction * slippage_pct)
                trade, pnl = _close_position(
                    position, sl_exit_price, "intraday_sl", i, config,
                )
                capital += position.capital_allocated + pnl
                if capital > 0:
                    trades.append(trade)
                peak_capital = max(peak_capital, capital)
                position = None
                cooldown_remaining = cooldown_candles
                continue

        # -- Strategy exit on entry day --
        exit_signal = strategy.check_exit(i, cache, params, position)
        if exit_signal is not None:
            capital, _ = _try_exit_position(
                position, exit_signal, i, config, capital, trades,
            )
            peak_capital = max(peak_capital, capital)
            position = None
            cooldown_remaining = cooldown_candles
            continue

    # ══════════════════════════════════════════════════════════════════
    # FORCE-CLOSE fin de données — PAS dans trades (convention)
    # ══════════════════════════════════════════════════════════════════
    if position is not None:
        n_holding_days = (loop_end - 1) - position.entry_candle
        exit_price = cache.closes[loop_end - 1]

        # Recalcul PnL pour mettre à jour le capital
        gross_pnl = position.direction * (exit_price - position.entry_price) * position.quantity
        exit_notional = exit_price * position.quantity
        exit_fee = config.fee_model.total_exit_cost(exit_notional)
        entry_notional = position.entry_price * position.quantity
        overnight = config.fee_model.overnight_cost(entry_notional, n_holding_days)
        pnl = gross_pnl - position.entry_fee - exit_fee - overnight

        capital += position.capital_allocated + pnl

    return BacktestResult(
        trades=trades,
        final_capital=capital,
        initial_capital=config.initial_capital,
        n_skipped=n_skipped,
    )
