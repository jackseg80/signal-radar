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

from cli.runner import STRATEGIES, run_validate
from config.universe_loader import list_universes
from validation.report import print_report


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

    # -- Run validation --
    print(f"\n  Pipeline de validation : {args.strategy} / {args.universe}")

    try:
        result = run_validate(
            args.strategy,
            args.universe,
            capital=args.capital,
            whole_shares=False if args.no_whole_shares else None,
            fee_model_name=args.fee_model,
            is_end=args.is_end,
            data_end=args.data_end,
            oos_mid=args.oos_mid,
            save_json=not args.no_save,
        )
    except FileNotFoundError as e:
        print(f"  Error: {e}")
        sys.exit(1)

    print_report(result.report)


if __name__ == "__main__":
    main()
