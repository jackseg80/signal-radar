"""Past-only, next-open trade scoring for scanner candidates."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from data.base_loader import to_cache_arrays
from engine.fee_model import FeeModel
from engine.indicator_cache import build_cache
from engine.types import Direction, Position
from strategies.base import BaseStrategy


@dataclass(frozen=True)
class HistoricalTrade:
    """A completed whole-share trade, filled at next-session raw opens."""

    entry_session: str
    exit_session: str
    net_pnl_usd: float
    entry_price: float = 0.0
    exit_price: float = 0.0
    entry_shares: float = 0.0
    split_factor: float = 1.0
    dividend_per_entry_share: float = 0.0


@dataclass(frozen=True)
class RankingScore:
    """Conservative monthly net return and realised monthly drawdown."""

    lower_monthly_return: float | None
    max_drawdown: float | None
    n_trades: int


def historical_next_open_trades(
    df: pd.DataFrame,
    strategy: BaseStrategy,
    params: dict,
    fee_model: FeeModel,
    capital_usd: float = 5000.0,
) -> list[HistoricalTrade]:
    """Replay close signals at raw next opens with split-adjusted holdings.

    This single-symbol history is for ranking; portfolio overlaps are handled
    separately. An order at the final close remains unfilled and is excluded.
    """
    if len(df) < strategy.warmup(params) + 2:
        return []
    grid = {key: [value] for key, value in params.items()
            if key in {"rsi_period", "sma_trend_period", "sma_exit_period"}}
    cache = build_cache(to_cache_arrays(df), grid, dates=df.index.values)
    raw_opens = df["Open"].to_numpy(dtype=float)
    splits = df["Stock Splits"].to_numpy(dtype=float) if "Stock Splits" in df else np.zeros(len(df))
    dividends = df["Dividends"].to_numpy(dtype=float) if "Dividends" in df else np.zeros(len(df))
    dates = pd.DatetimeIndex(df.index)
    trades: list[HistoricalTrade] = []
    position: Position | None = None
    pending_entry = False
    pending_exit: str | None = None
    dividends_received = 0.0

    for i in range(max(1, strategy.warmup(params)), len(df)):
        if position is not None:
            if splits[i] > 0:
                position.quantity *= float(splits[i])
            if dividends[i] > 0:
                dividends_received += float(dividends[i]) * position.quantity
        if position is not None and pending_exit is not None:
            exit_price = float(raw_opens[i])
            exit_notional = exit_price * position.quantity
            exit_fee = fee_model.total_exit_cost(exit_notional)
            # Ex-date entitlements are not spendable proceeds. Yahoo does not
            # provide the Saxo pay date or withholding for a net cash credit.
            pnl = (exit_notional - exit_fee
                   - position.capital_allocated - position.entry_fee)
            entry_shares = position.capital_allocated / position.entry_price
            trades.append(HistoricalTrade(
                str(dates[position.entry_candle].date()),
                str(dates[i].date()), pnl,
                entry_price=position.entry_price, exit_price=exit_price,
                entry_shares=entry_shares,
                split_factor=position.quantity / entry_shares,
                dividend_per_entry_share=dividends_received / entry_shares,
            ))
            position = None
            pending_exit = None
            dividends_received = 0.0
            # Do not spend an opening sale's proceeds on a simultaneous buy.
            continue

        if position is None and pending_entry:
            pending_entry = False
            entry_price = float(raw_opens[i])
            shares = math.floor(capital_usd / entry_price)
            while shares > 0:
                cost = shares * entry_price
                fee = fee_model.total_entry_cost(cost)
                if cost + fee <= capital_usd:
                    break
                shares -= 1
            if shares > 0:
                position = Position(
                    entry_price=entry_price, entry_candle=i, quantity=shares,
                    direction=Direction.LONG, capital_allocated=shares * entry_price,
                    entry_fee=fee_model.total_entry_cost(shares * entry_price),
                )

        if position is None:
            # Today's close is observable only after today's open has passed.
            pending_entry = strategy.check_entry(i, cache, params) == Direction.LONG
            continue

        # Exit checks are made after this close; their order fills at open[i+1].
        exit_signal = strategy.check_exit(i, cache, params, position)
        if exit_signal is not None:
            pending_exit = exit_signal.reason
    return trades


def conservative_monthly_score(
    trades: list[HistoricalTrade],
    first_session: str,
    last_session: str,
    *,
    minimum_trades: int = 30,
    repetitions: int = 2000,
    seed: int = 20260923,
) -> RankingScore:
    """Bootstrap contiguous three-month blocks of realised net returns."""
    if len(trades) < minimum_trades:
        return RankingScore(None, None, len(trades))
    months = pd.period_range(first_session[:7], last_session[:7], freq="M")
    monthly = np.zeros(len(months), dtype=float)
    location = {str(month): i for i, month in enumerate(months)}
    for trade in trades:
        month_idx = location.get(trade.exit_session[:7])
        if month_idx is not None:
            monthly[month_idx] += trade.net_pnl_usd / 5000.0
    if len(monthly) < 3:
        return RankingScore(None, None, len(trades))
    blocks = np.array([monthly[i:i + 3] for i in range(len(monthly) - 2)])
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, len(blocks), size=(repetitions, math.ceil(len(monthly) / 3)))
    sampled = blocks[picks].reshape(repetitions, -1)[:, :len(monthly)]
    lower = float(np.quantile(sampled.mean(axis=1), 0.05))
    equity = np.cumprod(1.0 + monthly)
    peaks = np.maximum.accumulate(np.r_[1.0, equity])
    drawdown = float(np.max(1.0 - np.r_[1.0, equity] / peaks))
    return RankingScore(lower, drawdown, len(trades))


def simulate_common_portfolio(
    histories: dict[tuple[str, str], list[HistoricalTrade]],
    start_session: str,
    end_session: str,
    fee_model: FeeModel,
) -> dict:
    """Replay overlapping signals through one whole-share USD 5,000 portfolio.

    A candidate's rank uses only trades completed before its source session.
    Opening sale proceeds cannot fund another purchase at the same open.
    """
    candidates: dict[str, list[tuple[str, str, HistoricalTrade]]] = {}
    for (strategy, symbol), trades in histories.items():
        for trade in trades:
            if start_session <= trade.entry_session <= end_session:
                candidates.setdefault(trade.entry_session, []).append((strategy, symbol, trade))
    equity = 5000.0
    occupied_through = ""
    selected: list[dict] = []
    overlap_count = 0
    accrued_dividends = 0.0
    score_cache: dict[tuple[str, str, str], RankingScore] = {}
    for entry_session in sorted(candidates):
        day_candidates = candidates[entry_session]
        if entry_session <= occupied_through:
            overlap_count += len(day_candidates)
            continue
        ranked: list[tuple[float, float, str, str, HistoricalTrade]] = []
        month_start = entry_session[:7] + "-01"
        for strategy, symbol, trade in day_candidates:
            key = (strategy, symbol, month_start)
            if key not in score_cache:
                prior = [item for item in histories[(strategy, symbol)]
                         if "2014-01-01" <= item.exit_session < month_start]
                score_cache[key] = conservative_monthly_score(
                    prior, "2014-01-01", prior[-1].exit_session if prior else month_start,
                )
            score = score_cache[key]
            if score.lower_monthly_return is not None and score.lower_monthly_return > 0:
                ranked.append((score.lower_monthly_return,
                               score.max_drawdown or 0.0, symbol, strategy, trade))
        if not ranked:
            continue
        ranked.sort(key=lambda item: (-item[0], item[1], item[2], item[3]))
        _, _, symbol, strategy, trade = ranked[0]
        overlap_count += len(day_candidates) - 1
        if trade.entry_price <= 0 or trade.exit_price <= 0:
            continue
        budget = min(5000.0, equity)
        shares = math.floor(budget / trade.entry_price)
        while shares and shares * trade.entry_price + fee_model.total_entry_cost(
            shares * trade.entry_price
        ) > budget:
            shares -= 1
        if shares < 1:
            continue
        entry_cost = shares * trade.entry_price
        exit_shares = shares * trade.split_factor
        exit_value = exit_shares * trade.exit_price
        dividend_entitlement = shares * trade.dividend_per_entry_share
        pnl = (exit_value - fee_model.total_exit_cost(exit_value)
               - entry_cost - fee_model.total_entry_cost(entry_cost))
        accrued_dividends += dividend_entitlement
        equity += pnl
        occupied_through = trade.exit_session
        selected.append({
            "strategy": strategy, "symbol": symbol,
            "entry_session": entry_session, "exit_session": trade.exit_session,
            "shares": shares, "net_pnl_usd": round(pnl, 2),
            "equity_usd": round(equity, 2),
        })
    values = np.r_[5000.0, [item["equity_usd"] for item in selected]]
    peaks = np.maximum.accumulate(values)
    drawdown = float(np.max(1.0 - values / peaks)) if len(values) else 0.0
    return {
        "initial_capital_usd": 5000.0,
        "final_equity_usd": round(equity, 2),
        "unpaid_dividend_entitlements_usd": round(accrued_dividends, 2),
        "max_drawdown": round(drawdown, 4),
        "overlapping_signals_skipped": overlap_count,
        "trades": selected,
    }
