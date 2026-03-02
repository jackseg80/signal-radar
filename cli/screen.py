"""Screening rapide -- backtest simple (pas de robustesse) sur un univers.

Usage:
    python -m cli.screen <strategy> <universe>

Exemple:
    python -m cli.screen rsi2 us_stocks_large

Affiche un tableau trie par PF. Plus rapide que validate
(pas de robustesse/sous-periodes/t-test).
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import pandas as pd

from config.universe_loader import list_universes, load_universe
from data.base_loader import to_cache_arrays
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


def _merge_grid_with_defaults(strategy: BaseStrategy) -> dict[str, list]:
    """Fusionne param_grid + default_params pour couverture cache complete."""
    grid = dict(strategy.param_grid())
    defaults = strategy.default_params()
    for key, value in defaults.items():
        if "period" in key and key not in grid and isinstance(value, (int, float)):
            grid[key] = [int(value)]
    return grid


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Quick screen: backtest on universe (no robustness)")
    parser.add_argument("strategy", nargs="?", help="Strategy name")
    parser.add_argument("universe", nargs="?", help="Universe name")
    parser.add_argument("--capital", type=float, default=None)
    parser.add_argument("--no-whole-shares", action="store_true")
    parser.add_argument("--fee-model", type=str, default=None)
    parser.add_argument("--is-end", type=str, default="2014-01-01")
    parser.add_argument("--data-end", type=str, default="2025-01-01")
    args = parser.parse_args()

    if not args.strategy or not args.universe:
        parser.print_help()
        print(f"\n  Strategies: {', '.join(STRATEGIES.keys())}")
        print(f"  Universes:  {', '.join(list_universes())}")
        sys.exit(1)

    if args.strategy not in STRATEGIES:
        print(f"  Error: unknown strategy '{args.strategy}'")
        sys.exit(1)

    try:
        universe_config = load_universe(args.universe)
    except FileNotFoundError as e:
        print(f"  Error: {e}")
        sys.exit(1)

    fee_model_name = args.fee_model or universe_config.default_fee_model
    fee_model = FEE_MODELS.get(fee_model_name, FeeModel())
    market_def = MARKET_DEFAULTS.get(universe_config.market, {"capital": 10_000.0, "whole_shares": True})
    capital = args.capital if args.capital is not None else market_def["capital"]
    whole_shares = not args.no_whole_shares and market_def["whole_shares"]

    strategy = STRATEGIES[args.strategy]()
    cache_grid = _merge_grid_with_defaults(strategy)
    params = strategy.default_params()
    loader = YahooLoader()

    print(f"\n  Screen : {strategy.name} / {args.universe}")
    print(f"  Universe: {universe_config.name} ({len(universe_config.assets)} assets)")
    print(f"  Capital={capital:,.0f}, whole_shares={whole_shares}, fee_model={fee_model_name}")
    print(f"  OOS={args.is_end} -> {args.data_end}\n")

    # ── Screening ──
    results: list[dict[str, Any]] = []

    for symbol, start_date in universe_config.assets.items():
        print(f"  {symbol}...", end=" ", flush=True)
        try:
            df = loader.get_daily_candles(symbol, start_date, args.data_end)
        except Exception as e:
            print(f"SKIP ({e})")
            continue

        oos_start_idx = int(df.index.searchsorted(pd.Timestamp(args.is_end)))
        oos_end_idx = len(df)

        # Garantir que start_idx >= warmup (assets avec start > is_end)
        warmup = strategy.warmup(params)
        if oos_start_idx < warmup:
            oos_start_idx = warmup

        if oos_end_idx - oos_start_idx < 50:
            print("SKIP (insufficient OOS data)")
            continue

        arrays = to_cache_arrays(df)
        dates = df.index.values
        cache = build_cache(arrays, cache_grid, dates=dates)

        bt_config = BacktestConfig(
            symbol=symbol,
            initial_capital=capital,
            slippage_pct=0.0003,
            fee_model=fee_model,
            whole_shares=whole_shares,
        )

        result = simulate(
            strategy, cache, params, bt_config,
            start_idx=oos_start_idx, end_idx=oos_end_idx,
        )

        results.append({
            "symbol": symbol,
            "n_trades": result.n_trades,
            "win_rate": result.win_rate,
            "pf": result.profit_factor,
            "sharpe": result.sharpe,
            "net_pct": result.net_return_pct,
        })
        print(f"{result.n_trades} trades, PF {result.profit_factor:.2f}")

    # ── Affichage trie par PF ──
    results.sort(key=lambda r: r["pf"], reverse=True)

    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  Screen : {strategy.name} / {args.universe} -- {len(results)} assets")
    print(sep)
    header = f"  {'Ticker':<10} {'Trades':>6} {'WR':>6} {'PF':>7} {'Sharpe':>7} {'Net%':>8}"
    print(header)
    print("  " + "-" * 56)

    for r in results:
        pf_str = f"{r['pf']:.2f}" if r['pf'] < 100 else "inf"
        print(
            f"  {r['symbol']:<10} {r['n_trades']:>6} "
            f"{r['win_rate']:>5.0%} {pf_str:>7} "
            f"{r['sharpe']:>7.2f} {r['net_pct']:>+7.1f}%"
        )

    # ── Resume ──
    n_profitable = sum(1 for r in results if r["pf"] > 1.0)
    print(f"\n  {n_profitable}/{len(results)} assets with PF > 1.0")

    # ── Sauvegarde DB ──
    try:
        from validation.results_db import ResultsDB

        db = ResultsDB()
        screen_records = [
            {
                "symbol": r["symbol"],
                "n_trades": r["n_trades"],
                "win_rate": r["win_rate"],
                "profit_factor": r["pf"],
                "sharpe": r["sharpe"],
                "net_return_pct": r["net_pct"],
            }
            for r in results
        ]
        db.save_screen(args.strategy, args.universe, screen_records)
        print(f"  Results saved to DB ({len(screen_records)} assets)")
    except Exception as e:
        print(f"  Warning: could not save to DB ({e})")

    print(sep)


if __name__ == "__main__":
    main()
