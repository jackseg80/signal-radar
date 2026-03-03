"""Core backtest runner functions (importable, no CLI/argparse).

Used by:
    - cli/screen.py (CLI wrapper)
    - cli/validate.py (CLI wrapper)
    - scripts/monthly_refresh.py (automated monthly refresh)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd

from config.universe_loader import UniverseConfig, load_universe
from data.base_loader import to_cache_arrays
from data.db import SignalRadarDB
from data.yahoo_loader import YahooLoader
from engine.backtest_config import BacktestConfig
from engine.fee_model import (
    FEE_MODEL_FOREX_SAXO,
    FEE_MODEL_US_ETFS_USD,
    FEE_MODEL_US_STOCKS_USD,
    FeeModel,
)
from engine.indicator_cache import build_cache
from engine.simulator import simulate
from strategies.base import BaseStrategy
from strategies.donchian_trend import DonchianTrend
from strategies.ibs_mean_reversion import IBSMeanReversion
from strategies.rsi2_mean_reversion import RSI2MeanReversion
from strategies.turn_of_month import TurnOfMonth
from validation.config import ValidationConfig
from validation.pipeline import validate
from validation.report import ValidationReport, save_report

# ── Registries (single source of truth) ──

STRATEGIES: dict[str, type[BaseStrategy]] = {
    "rsi2": RSI2MeanReversion,
    "ibs": IBSMeanReversion,
    "tom": TurnOfMonth,
    "donchian": DonchianTrend,
}

FEE_MODELS: dict[str, FeeModel] = {
    "us_stocks_usd_account": FEE_MODEL_US_STOCKS_USD,
    "us_etfs_usd_account": FEE_MODEL_US_ETFS_USD,
    "forex_saxo": FEE_MODEL_FOREX_SAXO,
    "default": FeeModel(),
}

MARKET_DEFAULTS: dict[str, dict[str, Any]] = {
    "us_stocks": {"capital": 10_000.0, "whole_shares": True},
    "us_etfs": {"capital": 100_000.0, "whole_shares": False},
    "forex": {"capital": 100_000.0, "whole_shares": False},
}


# ── Utilities ──


def _merge_grid_with_defaults(strategy: BaseStrategy) -> dict[str, list]:
    """Merge param_grid + default_params for complete cache coverage."""
    grid = dict(strategy.param_grid())
    defaults = strategy.default_params()
    for key, value in defaults.items():
        if "period" in key and key not in grid and isinstance(value, (int, float)):
            grid[key] = [int(value)]
    return grid


def resolve_market_params(
    universe_config: UniverseConfig,
    *,
    capital: float | None = None,
    whole_shares: bool | None = None,
    fee_model_name: str | None = None,
) -> tuple[float, bool, FeeModel, str]:
    """Resolve capital, whole_shares, fee_model from universe defaults.

    Args:
        universe_config: Loaded universe configuration.
        capital: Override capital (None = market default).
        whole_shares: Override whole_shares (None = market default).
        fee_model_name: Override fee model (None = universe default).

    Returns:
        (capital, whole_shares, fee_model, fee_model_name)
    """
    fm_name = fee_model_name or universe_config.default_fee_model
    fm = FEE_MODELS.get(fm_name, FeeModel())
    market_def = MARKET_DEFAULTS.get(
        universe_config.market, {"capital": 10_000.0, "whole_shares": True}
    )
    cap = capital if capital is not None else market_def["capital"]
    ws = whole_shares if whole_shares is not None else market_def["whole_shares"]
    return cap, ws, fm, fm_name


# ── Result dataclasses ──


@dataclass
class ScreenResult:
    """Result of screening one strategy x universe."""

    strategy_key: str
    strategy_name: str
    universe_name: str
    assets: list[dict[str, Any]] = field(default_factory=list)
    n_profitable: int = 0


@dataclass
class ValidateResult:
    """Result of validating one strategy x universe."""

    strategy_key: str
    strategy_name: str
    universe_name: str
    report: ValidationReport = field(default_factory=lambda: ValidationReport(strategy_name=""))


# ── Core functions ──


def run_screen(
    strategy_key: str,
    universe_name: str,
    *,
    capital: float | None = None,
    whole_shares: bool | None = None,
    fee_model_name: str | None = None,
    is_end: str = "2014-01-01",
    data_end: str | None = None,
    db: SignalRadarDB | None = None,
) -> ScreenResult:
    """Run a screen (quick backtest) for one strategy x universe.

    Args:
        strategy_key: Short strategy name ("rsi2", "ibs", "tom").
        universe_name: Universe YAML name ("us_stocks_large").
        capital: Override initial capital (None = market default).
        whole_shares: Override whole_shares (None = market default).
        fee_model_name: Override fee model (None = universe default).
        is_end: IS/OOS split date.
        data_end: Data end date (None = today).
        db: DB instance (None = create default).

    Returns:
        ScreenResult with per-asset metrics sorted by profit_factor desc.

    Raises:
        ValueError: If strategy_key is unknown.
        FileNotFoundError: If universe YAML not found.
    """
    if data_end is None:
        data_end = datetime.now().strftime("%Y-%m-%d")
    if strategy_key not in STRATEGIES:
        raise ValueError(f"Unknown strategy: {strategy_key}")

    universe_config = load_universe(universe_name)
    cap, ws, fm, _ = resolve_market_params(
        universe_config,
        capital=capital,
        whole_shares=whole_shares,
        fee_model_name=fee_model_name,
    )

    strategy = STRATEGIES[strategy_key]()
    cache_grid = _merge_grid_with_defaults(strategy)
    params = strategy.default_params()
    loader = YahooLoader()

    results: list[dict[str, Any]] = []

    for symbol, start_date in universe_config.assets.items():
        try:
            df = loader.get_daily_candles(symbol, start_date, data_end)
        except Exception:
            continue

        oos_start_idx = int(df.index.searchsorted(pd.Timestamp(is_end)))
        warmup = strategy.warmup(params)
        if oos_start_idx < warmup:
            oos_start_idx = warmup

        if len(df) - oos_start_idx < 50:
            continue

        arrays = to_cache_arrays(df)
        dates = df.index.values
        cache = build_cache(arrays, cache_grid, dates=dates)

        bt_config = BacktestConfig(
            symbol=symbol,
            initial_capital=cap,
            slippage_pct=0.0003,
            fee_model=fm,
            whole_shares=ws,
        )

        result = simulate(
            strategy, cache, params, bt_config,
            start_idx=oos_start_idx, end_idx=len(df),
        )

        results.append({
            "symbol": symbol,
            "n_trades": result.n_trades,
            "win_rate": result.win_rate,
            "profit_factor": result.profit_factor,
            "sharpe": result.sharpe,
            "net_return_pct": result.net_return_pct,
        })

    results.sort(key=lambda r: r["profit_factor"], reverse=True)
    n_profitable = sum(1 for r in results if r["profit_factor"] > 1.0)

    # Save to DB
    try:
        if db is None:
            db = SignalRadarDB()
        screen_records = [
            {
                "symbol": r["symbol"],
                "n_trades": r["n_trades"],
                "win_rate": r["win_rate"],
                "profit_factor": r["profit_factor"],
                "sharpe": r["sharpe"],
                "net_return_pct": r["net_return_pct"],
            }
            for r in results
        ]
        db.save_screen(strategy_key, universe_name, screen_records)
    except Exception:
        pass

    return ScreenResult(
        strategy_key=strategy_key,
        strategy_name=strategy.name,
        universe_name=universe_name,
        assets=results,
        n_profitable=n_profitable,
    )


def run_validate(
    strategy_key: str,
    universe_name: str,
    *,
    capital: float | None = None,
    whole_shares: bool | None = None,
    fee_model_name: str | None = None,
    is_end: str = "2014-01-01",
    data_end: str | None = None,
    oos_mid: str = "2019-07-01",
    save_json: bool = True,
    db: SignalRadarDB | None = None,
) -> ValidateResult:
    """Run full validation for one strategy x universe.

    Args:
        strategy_key: Short strategy name ("rsi2", "ibs", "tom").
        universe_name: Universe YAML name ("us_stocks_large").
        capital: Override initial capital (None = market default).
        whole_shares: Override whole_shares (None = market default).
        fee_model_name: Override fee model (None = universe default).
        is_end: IS/OOS split date.
        data_end: Data end date (None = today).
        oos_mid: OOS mid-split date for sub-period stability.
        save_json: Save JSON report to validation_results/.
        db: DB instance (None = create default).

    Returns:
        ValidateResult with full ValidationReport.

    Raises:
        ValueError: If strategy_key is unknown.
        FileNotFoundError: If universe YAML not found.
    """
    if data_end is None:
        data_end = datetime.now().strftime("%Y-%m-%d")
    if strategy_key not in STRATEGIES:
        raise ValueError(f"Unknown strategy: {strategy_key}")

    universe_config = load_universe(universe_name)
    cap, ws, fm, _ = resolve_market_params(
        universe_config,
        capital=capital,
        whole_shares=whole_shares,
        fee_model_name=fee_model_name,
    )

    strategy = STRATEGIES[strategy_key]()

    val_config = ValidationConfig(
        universe=universe_config.assets,
        data_end=data_end,
        is_end=is_end,
        initial_capital=cap,
        whole_shares=ws,
        slippage_pct=0.0003,
        fee_model=fm,
        oos_mid=oos_mid,
    )

    report = validate(strategy, val_config)
    report.universe_name = universe_name

    # Save JSON report
    if save_json:
        try:
            save_report(report)
        except Exception:
            pass

    # Save to DB
    try:
        if db is None:
            db = SignalRadarDB()
        db.save_validation(report)
    except Exception:
        pass

    return ValidateResult(
        strategy_key=strategy_key,
        strategy_name=strategy.name,
        universe_name=universe_name,
        report=report,
    )
