"""CLI pour gerer les donnees OHLCV.

Usage:
    python -m cli.data info                          # Lister les assets en DB
    python -m cli.data download us_stocks_large      # Telecharger un univers
    python -m cli.data update us_stocks_large        # Mise a jour incrementale
    python -m cli.data update --all                  # Mettre a jour tout
    python -m cli.data clear                         # Vider les prix
    python -m cli.data clear AAPL                    # Supprimer un symbol
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta

from config.universe_loader import list_universes
from data.db import SignalRadarDB


def cmd_info(db: SignalRadarDB) -> None:
    """Affiche les assets en DB."""
    assets = db.list_assets()
    if not assets:
        print("  Database is empty.")
        print("  Use 'python -m cli.data download <universe>' to populate.")
        return

    sep = "=" * 56
    print(f"\n{sep}")
    print(f"  Data -- {len(assets)} assets in DB")
    print(sep)
    header = f"  {'Symbol':<12} {'Rows':>6} {'Start':>12} {'End':>12}"
    print(header)
    print("  " + "-" * 52)

    for a in assets:
        print(
            f"  {a['symbol']:<12} {a['rows']:>6} "
            f"{a['start']:>12} {a['end']:>12}"
        )
    print(sep)


def cmd_download(db: SignalRadarDB, universe: str, data_end: str) -> None:
    """Telecharge un univers complet."""
    from config.universe_loader import load_universe
    from data.yahoo_loader import YahooLoader

    loader = YahooLoader()
    univ = load_universe(universe)
    total = len(univ.assets)

    print(f"\n  Downloading universe: {universe}")
    for i, (symbol, start_date) in enumerate(univ.assets.items(), 1):
        print(f"  [{i}/{total}] {symbol}...", end=" ", flush=True)
        try:
            df = loader.get_daily_candles(symbol, start_date, data_end)
            print(f"{len(df)} rows")
        except Exception as e:
            print(f"FAILED ({e})")
    print("  Done.")


def cmd_update(db: SignalRadarDB, universe: str | None, update_all: bool) -> None:
    """Met a jour les donnees (incremental)."""
    from data.yahoo_loader import YahooLoader

    loader = YahooLoader()
    today = datetime.now().strftime("%Y-%m-%d")

    if update_all:
        assets = db.list_assets()
        if not assets:
            print("  Database is empty. Nothing to update.")
            return
        symbols = [(a["symbol"], a["end"]) for a in assets]
    elif universe:
        from config.universe_loader import load_universe

        univ = load_universe(universe)
        symbols = []
        for symbol in univ.assets:
            date_range = db.ohlcv_date_range(symbol)
            last = date_range[1] if date_range else "2003-01-01"
            symbols.append((symbol, last))
    else:
        print("  Error: specify a universe or --all")
        sys.exit(1)

    total = len(symbols)
    print(f"\n  Updating {total} assets...")
    for i, (symbol, last_date) in enumerate(symbols, 1):
        print(f"  [{i}/{total}] {symbol}...", end=" ", flush=True)
        try:
            overlap_start = (
                datetime.strptime(last_date, "%Y-%m-%d") - timedelta(days=5)
            ).strftime("%Y-%m-%d")
            df = loader.get_daily_candles(symbol, overlap_start, today)
            print(f"{len(df)} rows")
        except Exception as e:
            print(f"FAILED ({e})")
    print("  Done.")


def cmd_clear(db: SignalRadarDB, symbol: str | None) -> None:
    """Supprime les donnees OHLCV."""
    if symbol:
        if db.has_ohlcv(symbol):
            db.clear_ohlcv(symbol)
            print(f"  Cleared data for {symbol}")
        else:
            print(f"  {symbol} not in DB")
    else:
        assets = db.list_assets()
        if not assets:
            print("  Database is already empty.")
            return
        db.clear_ohlcv()
        print(f"  Cleared {len(assets)} assets")


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Manage OHLCV data",
    )
    subparsers = parser.add_subparsers(dest="command")

    # info
    subparsers.add_parser("info", help="List assets in DB")

    # download
    dl_parser = subparsers.add_parser("download", help="Download universe data")
    dl_parser.add_argument("universe", help="Universe name")
    dl_parser.add_argument("--data-end", default="2025-01-01", help="End date")

    # update
    up_parser = subparsers.add_parser("update", help="Update data (incremental)")
    up_parser.add_argument("universe", nargs="?", help="Universe name")
    up_parser.add_argument("--all", action="store_true", help="Update all assets")

    # clear
    cl_parser = subparsers.add_parser("clear", help="Clear OHLCV data")
    cl_parser.add_argument("symbol", nargs="?", help="Symbol to clear (all if omitted)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        print(f"\n  Available universes: {', '.join(list_universes())}")
        sys.exit(1)

    db = SignalRadarDB()

    if args.command == "info":
        cmd_info(db)
    elif args.command == "download":
        cmd_download(db, args.universe, args.data_end)
    elif args.command == "update":
        cmd_update(db, args.universe, args.all)
    elif args.command == "clear":
        cmd_clear(db, args.symbol)


if __name__ == "__main__":
    main()
