"""Temporal validation for the next-open, Swiss-cost observation model."""

from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

from engine.ranking import (
    HistoricalTrade, conservative_monthly_score, simulate_common_portfolio,
)
from engine.fee_model import FeeModel


def monthly_net_returns(
    trades: list[HistoricalTrade], start: str, end: str,
) -> np.ndarray:
    """Include zero-trade months so short bursts do not dominate the test."""
    months = pd.period_range(start[:7], end[:7], freq="M")
    values = np.zeros(len(months), dtype=float)
    lookup = {str(month): i for i, month in enumerate(months)}
    for trade in trades:
        index = lookup.get(trade.exit_session[:7])
        if index is not None:
            values[index] += trade.net_pnl_usd / 5000.0
    return values


def block_bootstrap_pvalue(
    monthly: np.ndarray, *, repetitions: int = 2000,
    seed: int = 20260923,
) -> float:
    """One-sided centered three-month block bootstrap p-value."""
    if len(monthly) < 3 or monthly.mean() <= 0:
        return 1.0
    observed = float(monthly.mean())
    centered = monthly - observed
    blocks = np.array([centered[i:i + 3] for i in range(len(centered) - 2)])
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, len(blocks), size=(repetitions, (len(monthly) + 2) // 3))
    means = blocks[picks].reshape(repetitions, -1)[:, :len(monthly)].mean(axis=1)
    return float((1 + np.count_nonzero(means >= observed)) / (repetitions + 1))


def holm_adjust(pvalues: dict[tuple[str, str], float]) -> dict[tuple[str, str], float]:
    """Control family-wise error across all title/strategy comparisons."""
    ordered = sorted(pvalues, key=lambda key: pvalues[key])
    adjusted: dict[tuple[str, str], float] = {}
    running = 0.0
    for i, key in enumerate(ordered):
        running = max(running, min(1.0, (len(ordered) - i) * pvalues[key]))
        adjusted[key] = running
    return adjusted


def evaluate_histories(
    histories: dict[tuple[str, str], list[HistoricalTrade]],
    asof_session: str, fee_model: FeeModel, costs_verified: bool,
    *, scope: str = "production",
) -> dict:
    """Keep 2014-24 research and 2025+ temporal control separate."""
    raw_p: dict[tuple[str, str], float] = {}
    records: dict[tuple[str, str], dict] = {}
    for key, trades in histories.items():
        train = [trade for trade in trades
                 if trade.entry_session >= "2014-01-01"
                 and trade.exit_session <= "2024-12-31"]
        holdout = [trade for trade in trades
                   if trade.entry_session >= "2025-01-01"
                   and trade.exit_session <= asof_session]
        train_score = conservative_monthly_score(
            train, "2014-01-01", "2024-12-31",
        )
        holdout_months = monthly_net_returns(
            holdout, "2025-01-01", asof_session,
        )
        train_months = monthly_net_returns(
            train, "2014-01-01", "2024-12-31",
        )
        raw_p[key] = block_bootstrap_pvalue(train_months)
        yearly = defaultdict(float)
        for trade in train + holdout:
            yearly[trade.exit_session[:4]] += trade.net_pnl_usd
        records[key] = {
            "strategy": key[0], "symbol": key[1],
            "asof_session": asof_session, "scope": scope,
            "n_trades": len(train), "holdout_trades": len(holdout),
            "monthly_lower_bound": train_score.lower_monthly_return,
            "max_drawdown": train_score.max_drawdown,
            "train_monthly_return": float(train_months.mean()),
            "holdout_monthly_return": float(holdout_months.mean()),
            "train_p_raw": raw_p[key],
            "worst_year": min(yearly, key=yearly.get) if yearly else None,
            "worst_year_pnl_usd": round(min(yearly.values()), 2) if yearly else None,
            "costs_verified": costs_verified,
            "calibrated": costs_verified,
        }
    adjusted = holm_adjust(raw_p)
    for key, record in records.items():
        record["train_p_adjusted"] = adjusted[key]
        qualifies = (
            record["n_trades"] >= 30
            and record["holdout_trades"] >= 3
            and record["monthly_lower_bound"] is not None
            and record["monthly_lower_bound"] > 0
            and record["holdout_monthly_return"] > 0
            and adjusted[key] < 0.05
        )
        record["verdict"] = (
            "VALIDATED" if qualifies and costs_verified else
            "PROVISIONAL" if qualifies else "REJECTED"
        )
    portfolio = simulate_common_portfolio(
        histories, "2025-01-01", asof_session, fee_model,
    ) if scope == "production" else None
    return {
        "asof_session": asof_session,
        "train_period": ["2014-01-01", "2024-12-31"],
        "holdout_period": ["2025-01-01", asof_session],
        "cost_model": fee_model.name,
        "costs_verified": costs_verified,
        "comparison_correction": "Holm across title/strategy pairs",
        "records": sorted(records.values(), key=lambda item: (item["strategy"], item["symbol"])),
        "common_portfolio_holdout": portfolio,
    }
