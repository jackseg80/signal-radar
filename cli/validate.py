"""CLI pour valider une strategie sur un univers.

Usage:
    python -m cli.validate <strategy> <universe> [options]

Exemples:
    python -m cli.validate rsi2 us_stocks_large
    python -m cli.validate ibs us_etfs_sector
    python -m cli.validate tom us_etfs_broad
    python -m cli.validate rsi2 us_stocks_large --capital 100000 --no-whole-shares

Lister les ressources:
    python -m cli.validate --list-universes
    python -m cli.validate --list-strategies
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from config.universe_loader import list_universes, load_universe
from engine.fee_model import (
    FEE_MODEL_FOREX_SAXO,
    FEE_MODEL_US_ETFS_USD,
    FEE_MODEL_US_STOCKS_USD,
    FeeModel,
)
from strategies.base import BaseStrategy
from strategies.donchian_trend import DonchianTrend
from strategies.ibs_mean_reversion import IBSMeanReversion
from strategies.rsi2_mean_reversion import RSI2MeanReversion
from strategies.turn_of_month import TurnOfMonth
from validation.config import ValidationConfig
from validation.pipeline import validate
from validation.report import print_report, save_report

# ── Registres ──

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

# ── Defaults par marche ──

MARKET_DEFAULTS: dict[str, dict[str, Any]] = {
    "us_stocks": {"capital": 10_000.0, "whole_shares": True},
    "us_etfs": {"capital": 100_000.0, "whole_shares": False},
    "forex": {"capital": 100_000.0, "whole_shares": False},
}


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Validate trading strategy on an asset universe",
    )
    parser.add_argument("strategy", nargs="?", help="Strategy name (rsi2, ibs, tom, donchian)")
    parser.add_argument("universe", nargs="?", help="Universe name (YAML file in config/universes/)")
    parser.add_argument("--capital", type=float, default=None, help="Override initial capital")
    parser.add_argument("--no-whole-shares", action="store_true", help="Use fractional shares")
    parser.add_argument("--fee-model", type=str, default=None, help="Override fee model name")
    parser.add_argument("--is-end", type=str, default="2014-01-01", help="IS/OOS split date")
    parser.add_argument("--data-end", type=str, default="2025-01-01", help="Data end date")
    parser.add_argument("--oos-mid", type=str, default="2019-07-01", help="OOS mid-split date")
    parser.add_argument("--list-universes", action="store_true", help="List available universes")
    parser.add_argument("--list-strategies", action="store_true", help="List available strategies")
    parser.add_argument("--no-save", action="store_true", help="Don't save results to JSON")
    args = parser.parse_args()

    # -- Mode listing --
    if args.list_universes:
        print("\n  Available universes:")
        for u in list_universes():
            print(f"    {u}")
        print()
        return

    if args.list_strategies:
        print("\n  Available strategies:")
        for s in STRATEGIES:
            print(f"    {s}")
        print()
        return

    # -- Validation des arguments --
    if not args.strategy or not args.universe:
        parser.print_help()
        print(f"\n  Strategies: {', '.join(STRATEGIES.keys())}")
        print(f"  Universes:  {', '.join(list_universes())}")
        sys.exit(1)

    if args.strategy not in STRATEGIES:
        print(f"  Error: unknown strategy '{args.strategy}'")
        print(f"  Available: {', '.join(STRATEGIES.keys())}")
        sys.exit(1)

    # -- Charger univers --
    try:
        universe_config = load_universe(args.universe)
    except FileNotFoundError as e:
        print(f"  Error: {e}")
        sys.exit(1)

    # -- Resoudre fee model --
    fee_model_name = args.fee_model or universe_config.default_fee_model
    fee_model = FEE_MODELS.get(fee_model_name, FeeModel())

    # -- Defaults par marche --
    market_def = MARKET_DEFAULTS.get(universe_config.market, {"capital": 10_000.0, "whole_shares": True})
    capital = args.capital if args.capital is not None else market_def["capital"]
    whole_shares = not args.no_whole_shares and market_def["whole_shares"]

    # -- Config --
    val_config = ValidationConfig(
        universe=universe_config.assets,
        data_end=args.data_end,
        is_end=args.is_end,
        initial_capital=capital,
        whole_shares=whole_shares,
        slippage_pct=0.0003,
        fee_model=fee_model,
        oos_mid=args.oos_mid,
    )

    strategy = STRATEGIES[args.strategy]()

    print(f"\n  Pipeline de validation : {strategy.name} / {args.universe}")
    print(f"  Universe: {universe_config.name} ({len(universe_config.assets)} assets)")
    print(f"  Capital={val_config.initial_capital:,.0f}, "
          f"whole_shares={val_config.whole_shares}, "
          f"fee_model={fee_model_name}")
    print(f"  OOS={val_config.is_end} -> {val_config.data_end}\n")

    # -- Lancer validation --
    report = validate(strategy, val_config)
    report.universe_name = args.universe

    print_report(report)

    # -- Sauvegarde --
    if not args.no_save:
        path = save_report(report)
        print(f"\n  Results saved to {path}")

        try:
            from data.db import SignalRadarDB

            db = SignalRadarDB()
            db.save_validation(report)
            print(f"  Results saved to DB")
        except Exception as e:
            print(f"  Warning: could not save to DB ({e})")


if __name__ == "__main__":
    main()
