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

from cli.runner import STRATEGIES, run_screen
from config.universe_loader import list_universes


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

    # ── Run screen ──
    print(f"\n  Screen : {args.strategy} / {args.universe}")

    try:
        result = run_screen(
            args.strategy,
            args.universe,
            capital=args.capital,
            whole_shares=False if args.no_whole_shares else None,
            fee_model_name=args.fee_model,
            is_end=args.is_end,
            data_end=args.data_end,
        )
    except FileNotFoundError as e:
        print(f"  Error: {e}")
        sys.exit(1)

    # ── Affichage trie par PF ──
    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  Screen : {result.strategy_name} / {result.universe_name} -- {len(result.assets)} assets")
    print(sep)
    header = f"  {'Ticker':<10} {'Trades':>6} {'WR':>6} {'PF':>7} {'Sharpe':>7} {'Net%':>8}"
    print(header)
    print("  " + "-" * 56)

    for r in result.assets:
        pf = r["profit_factor"]
        pf_str = f"{pf:.2f}" if pf < 100 else "inf"
        print(
            f"  {r['symbol']:<10} {r['n_trades']:>6} "
            f"{r['win_rate']:>5.0%} {pf_str:>7} "
            f"{r['sharpe']:>7.2f} {r['net_return_pct']:>+7.1f}%"
        )

    # ── Resume ──
    print(f"\n  {result.n_profitable}/{len(result.assets)} assets with PF > 1.0")
    print(sep)


if __name__ == "__main__":
    main()
