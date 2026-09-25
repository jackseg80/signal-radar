"""Next-open fills, corporate actions, ranking and temporal validation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.fee_model import FeeModel
from engine.ranking import (
    HistoricalTrade, conservative_monthly_score, historical_next_open_trades,
)
from engine.types import Direction, ExitSignal, Position
from strategies.base import BaseStrategy
from validation.next_open import evaluate_histories, holm_adjust


class TriggerStrategy(BaseStrategy):
    """Enter after candle 1, exit after candle 3."""

    name = "trigger"

    def default_params(self) -> dict:
        return {}

    def param_grid(self) -> dict:
        return {}

    def warmup(self, params: dict) -> int:
        return 1

    def check_entry(self, i: int, cache, params: dict) -> Direction:
        return Direction.LONG if i == 1 else Direction.FLAT

    def check_exit(self, i: int, cache, params: dict, position: Position):
        return ExitSignal(cache.closes[i], "close_signal") if i == 3 else None


def test_entry_and_exit_signals_fill_at_next_raw_open_with_actions() -> None:
    """Both close signals fill next open; unpaid dividends cannot inflate cash."""
    dates = pd.to_datetime([
        "2026-09-21", "2026-09-22", "2026-09-23",
        "2026-09-24", "2026-09-25",
    ])
    df = pd.DataFrame({
        "Open": [100, 100, 100, 50, 55],
        "High": [102, 102, 102, 52, 57],
        "Low": [98, 98, 98, 48, 53],
        "Close": [100, 100, 100, 51, 56],
        "Adj_Open": [50, 50, 50, 50, 55],
        "Adj_High": [51, 51, 51, 52, 57],
        "Adj_Low": [49, 49, 49, 48, 53],
        "Adj_Close": [50, 50, 50, 51, 56],
        "Volume": [10000] * 5,
        "Dividends": [0, 0, 0, 1, 0],
        "Stock Splits": [0, 0, 0, 2, 0],
    }, index=dates)
    trades = historical_next_open_trades(df, TriggerStrategy(), {}, FeeModel())
    assert len(trades) == 1
    trade = trades[0]
    assert trade.entry_session == "2026-09-23"
    assert trade.exit_session == "2026-09-25"
    assert trade.entry_price == 100
    assert trade.exit_price == 55
    assert trade.split_factor == 2
    assert trade.dividend_per_entry_share == pytest.approx(2)
    assert trade.net_pnl_usd == pytest.approx(500)


def test_block_score_and_holm_are_deterministic() -> None:
    """Thirty completed trades and corrected family significance are required."""
    trades = [HistoricalTrade("2020-01-02", "2020-01-03", 10.0)] * 29
    assert conservative_monthly_score(trades, "2020-01-01", "2022-12-31").lower_monthly_return is None
    trades.append(HistoricalTrade("2020-02-03", "2020-02-04", 10.0))
    first = conservative_monthly_score(trades, "2020-01-01", "2022-12-31")
    second = conservative_monthly_score(trades, "2020-01-01", "2022-12-31")
    assert first == second
    assert holm_adjust({("a", "x"): .01, ("b", "x"): .02, ("c", "x"): .04}) == {
        ("a", "x"): .03, ("b", "x"): .04, ("c", "x"): .04,
    }


def test_temporal_holdout_does_not_validate_unreconciled_costs() -> None:
    """Positive past results remain provisional until Saxo costs are verified."""
    trades = []
    for year in range(2014, 2025):
        for month in range(1, 13):
            day = f"{year}-{month:02d}-15"
            trades.append(HistoricalTrade(day, day, 20.0, 100.0, 100.4, 50.0))
    for month in range(1, 7):
        day = f"2025-{month:02d}-15"
        trades.append(HistoricalTrade(day, day, 20.0, 100.0, 100.4, 50.0))
    result = evaluate_histories(
        {("tom", "META"): trades}, "2025-06-30", FeeModel(), False,
    )
    record = result["records"][0]
    assert record["n_trades"] == 132
    assert record["holdout_trades"] == 6
    assert record["verdict"] == "PROVISIONAL"
    assert result["train_period"] == ["2014-01-01", "2024-12-31"]
