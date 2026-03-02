"""CLI pour analyser et comparer les resultats.

Usage:
    python -m cli.analyze best rsi2                              # Meilleurs assets RSI2
    python -m cli.analyze best rsi2 --universe us_stocks_large   # Filtre par univers
    python -m cli.analyze best rsi2 --min-pf 1.3                 # PF minimum

    python -m cli.analyze compare us_stocks_large                # Tableau croise
    python -m cli.analyze compare us_stocks_large --strategies rsi2,ibs,tom

    python -m cli.analyze asset META                             # Tout sur META

    python -m cli.analyze summary                                # Vue d'ensemble
"""

from __future__ import annotations

import argparse
import sys

from validation.results_db import ResultsDB


def cmd_best(db: ResultsDB, args: argparse.Namespace) -> None:
    """Meilleurs assets pour une strategie."""
    source = args.source or "screens"
    rows = db.get_best_assets(
        args.strategy,
        universe=args.universe,
        min_pf=args.min_pf,
        source=source,
    )

    if not rows:
        print(f"  No results for {args.strategy} (source={source})")
        print("  Run 'python -m cli.screen <strategy> <universe>' first.")
        return

    sep = "=" * 72
    print(f"\n{sep}")
    label = f"  Best assets for {args.strategy} (PF >= {args.min_pf})"
    if args.universe:
        label += f" / {args.universe}"
    print(label)
    print(sep)

    header = (
        f"  {'Symbol':<10} {'Trades':>6} {'WR':>6} {'PF':>7} "
        f"{'Sharpe':>7} {'Net%':>8}  {'Universe':<20}"
    )
    print(header)
    print("  " + "-" * 68)

    for r in rows:
        pf_str = f"{r['profit_factor']:.2f}" if r["profit_factor"] < 100 else "inf"
        print(
            f"  {r['symbol']:<10} {r['n_trades']:>6} "
            f"{r['win_rate']:>5.0%} {pf_str:>7} "
            f"{r['sharpe']:>7.2f} {r['net_return_pct']:>+7.1f}%  "
            f"{r['universe']:<20}"
        )
    print(sep)


def cmd_compare(db: ResultsDB, args: argparse.Namespace) -> None:
    """Tableau croise strategies x assets."""
    if args.strategies:
        strategies = [s.strip() for s in args.strategies.split(",")]
    else:
        strategies = db.get_strategies(source="screens")
        if not strategies:
            strategies = db.get_strategies(source="validations")

    if not strategies:
        print("  No strategies found in DB.")
        print("  Run 'python -m cli.screen <strategy> <universe>' first.")
        return

    source = args.source or "screens"
    rows = db.compare_strategies(strategies, args.universe, source=source)

    if not rows:
        print(f"  No results for {args.universe}")
        return

    sep = "=" * (16 + len(strategies) * 10)
    print(f"\n{sep}")
    print(f"  Strategy comparison -- {args.universe}")
    print(sep)

    # Header
    header = f"  {'Symbol':<12}"
    for s in strategies:
        header += f" {s.upper():>8}"
    header += "  Score"
    print(header)
    print("  " + "-" * (10 + len(strategies) * 10 + 8))

    for r in rows:
        row_str = f"  {r['symbol']:<12}"
        stars = 0
        for s in strategies:
            pf = r.get(f"{s}_pf")
            if pf is not None:
                pf_str = f"{pf:.2f}" if pf < 100 else "inf"
                row_str += f" {pf_str:>8}"
                if pf > 1.2:
                    stars += 1
            else:
                row_str += f" {'---':>8}"

        # Score : * per strategy with PF > 1.2
        score = "*" * stars + "-" * (len(strategies) - stars)
        row_str += f"  {score}"
        print(row_str)

    # Resume
    print()
    for s in strategies:
        n_good = sum(1 for r in rows if r.get(f"{s}_pf", 0) > 1.2)
        print(f"  {s}: {n_good}/{len(rows)} assets with PF > 1.2")
    print(sep)


def cmd_asset(db: ResultsDB, args: argparse.Namespace) -> None:
    """Tous les resultats pour un symbol."""
    rows = db.get_cross_strategy(args.symbol)

    if not rows:
        print(f"  No results for {args.symbol}")
        return

    sep = "=" * 80
    print(f"\n{sep}")
    print(f"  {args.symbol} -- All results")
    print(sep)

    header = (
        f"  {'Strategy':<10} {'Universe':<20} {'Trades':>6} {'WR':>6} "
        f"{'PF':>7} {'Sharpe':>7} {'Net%':>8}  {'Source':<12}"
    )
    print(header)
    print("  " + "-" * 76)

    for r in rows:
        pf = r["profit_factor"]
        pf_str = f"{pf:.2f}" if pf < 100 else "inf"
        source = r["source"]
        verdict = r.get("verdict", "")
        if verdict == "VALIDATED":
            source += " [V]"
        elif verdict == "CONDITIONAL":
            source += " [C]"
        elif verdict == "REJECTED":
            source += " [R]"

        print(
            f"  {r['strategy']:<10} {r['universe']:<20} "
            f"{r['n_trades']:>6} {r['win_rate']:>5.0%} "
            f"{pf_str:>7} {r['sharpe']:>7.2f} "
            f"{r['net_return_pct']:>+7.1f}%  {source:<12}"
        )
    print(sep)


def cmd_summary(db: ResultsDB) -> None:
    """Vue d'ensemble."""
    sep = "=" * 60

    strats_screen = db.get_strategies("screens")
    strats_valid = db.get_strategies("validations")
    univs_screen = db.get_universes("screens")
    univs_valid = db.get_universes("validations")
    n_screens = db.count("screens")
    n_validations = db.count("validations")

    all_strats = sorted(set(strats_screen + strats_valid))
    all_univs = sorted(set(univs_screen + univs_valid))

    print(f"\n{sep}")
    print("  Signal Radar -- Results Summary")
    print(sep)

    if not all_strats:
        print("  No results in DB.")
        print("  Run 'python -m cli.screen <strategy> <universe>' first.")
        print(sep)
        return

    print(f"  Strategies tested: {len(all_strats)} ({', '.join(all_strats)})")
    print(f"  Universes tested:  {len(all_univs)} ({', '.join(all_univs)})")
    print(f"  Total screens:     {n_screens} asset-strategy pairs")
    print(f"  Total validations: {n_validations} asset-strategy pairs")

    # Best cross-strategy assets
    if strats_screen and univs_screen:
        print()
        for univ in univs_screen:
            rows = db.compare_strategies(strats_screen, univ, source="screens")
            n_strats = len(strats_screen)
            # Assets with PF > 1.2 in all strategies
            multi_good = [
                r["symbol"] for r in rows
                if sum(1 for s in strats_screen if r.get(f"{s}_pf", 0) > 1.2) >= min(n_strats, 2)
            ]
            if multi_good:
                print(f"  {univ} -- top assets (PF>1.2 in 2+ strategies):")
                print(f"    {', '.join(multi_good[:10])}")

    print(sep)


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Analyze validation/screen results")
    subparsers = parser.add_subparsers(dest="command")

    # best
    best_p = subparsers.add_parser("best", help="Best assets for a strategy")
    best_p.add_argument("strategy", help="Strategy name")
    best_p.add_argument("--universe", help="Filter by universe")
    best_p.add_argument("--min-pf", type=float, default=1.0, help="Min profit factor")
    best_p.add_argument("--source", choices=["screens", "validations"], default=None)

    # compare
    cmp_p = subparsers.add_parser("compare", help="Cross-strategy comparison")
    cmp_p.add_argument("universe", help="Universe name")
    cmp_p.add_argument("--strategies", help="Comma-separated strategy names")
    cmp_p.add_argument("--source", choices=["screens", "validations"], default=None)

    # asset
    ast_p = subparsers.add_parser("asset", help="All results for a symbol")
    ast_p.add_argument("symbol", help="Ticker symbol")

    # summary
    subparsers.add_parser("summary", help="Overview of all results")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    db = ResultsDB()

    if args.command == "best":
        cmd_best(db, args)
    elif args.command == "compare":
        cmd_compare(db, args)
    elif args.command == "asset":
        cmd_asset(db, args)
    elif args.command == "summary":
        cmd_summary(db)


if __name__ == "__main__":
    main()
