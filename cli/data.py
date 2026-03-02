"""CLI pour gerer le cache de donnees OHLCV.

Usage:
    python -m cli.data info                          # Lister le cache
    python -m cli.data download us_stocks_large      # Telecharger un univers
    python -m cli.data update us_stocks_large        # Mise a jour incrementale
    python -m cli.data update --all                  # Mettre a jour tout le cache
    python -m cli.data clear                         # Vider le cache
    python -m cli.data clear AAPL                    # Supprimer un symbol
"""

from __future__ import annotations

import argparse
import sys

from config.universe_loader import list_universes
from data.cache_manager import CacheManager


def cmd_info(cm: CacheManager) -> None:
    """Affiche le contenu du cache."""
    assets = cm.info()
    if not assets:
        print("  Cache is empty.")
        print("  Use 'python -m cli.data download <universe>' to populate.")
        return

    total_kb = sum(a["size_kb"] for a in assets)

    sep = "=" * 64
    print(f"\n{sep}")
    print(f"  Data Cache -- {len(assets)} assets, {total_kb:.0f} KB total")
    print(sep)
    header = f"  {'Symbol':<12} {'Rows':>6} {'Start':>12} {'End':>12} {'KB':>8}"
    print(header)
    print("  " + "-" * 60)

    for a in assets:
        print(
            f"  {a['symbol']:<12} {a['rows']:>6} "
            f"{a['start']:>12} {a['end']:>12} {a['size_kb']:>7.0f}"
        )
    print(sep)


def cmd_download(cm: CacheManager, universe: str, data_end: str) -> None:
    """Telecharge un univers complet."""
    print(f"\n  Downloading universe: {universe}")
    cm.download_universe(universe, end=data_end)
    print("  Done.")


def cmd_update(cm: CacheManager, universe: str | None, update_all: bool) -> None:
    """Met a jour le cache (incremental)."""
    if update_all:
        assets = cm.info()
        if not assets:
            print("  Cache is empty. Nothing to update.")
            return
        total = len(assets)
        print(f"\n  Updating all {total} cached assets...")
        for i, a in enumerate(assets, 1):
            print(f"  [{i}/{total}] {a['symbol']}...", end=" ", flush=True)
            try:
                df = cm.update(a["symbol"])
                rows = len(df) if not df.empty else 0
                print(f"{rows} rows")
            except Exception as e:
                print(f"FAILED ({e})")
        print("  Done.")
    elif universe:
        print(f"\n  Updating universe: {universe}")
        cm.update_universe(universe)
        print("  Done.")
    else:
        print("  Error: specify a universe or --all")
        sys.exit(1)


def cmd_clear(cm: CacheManager, symbol: str | None) -> None:
    """Supprime le cache."""
    if symbol:
        if cm.has(symbol):
            cm.clear(symbol)
            print(f"  Cleared cache for {symbol}")
        else:
            print(f"  {symbol} not in cache")
    else:
        assets = cm.info()
        if not assets:
            print("  Cache is already empty.")
            return
        cm.clear()
        print(f"  Cleared {len(assets)} cached files")


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Manage OHLCV data cache",
    )
    subparsers = parser.add_subparsers(dest="command")

    # info
    subparsers.add_parser("info", help="List cached assets")

    # download
    dl_parser = subparsers.add_parser("download", help="Download universe data")
    dl_parser.add_argument("universe", help="Universe name")
    dl_parser.add_argument("--data-end", default="2025-01-01", help="End date")

    # update
    up_parser = subparsers.add_parser("update", help="Update cache (incremental)")
    up_parser.add_argument("universe", nargs="?", help="Universe name")
    up_parser.add_argument("--all", action="store_true", help="Update all cached assets")

    # clear
    cl_parser = subparsers.add_parser("clear", help="Clear cache")
    cl_parser.add_argument("symbol", nargs="?", help="Symbol to clear (all if omitted)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        print(f"\n  Available universes: {', '.join(list_universes())}")
        sys.exit(1)

    cm = CacheManager()

    if args.command == "info":
        cmd_info(cm)
    elif args.command == "download":
        cmd_download(cm, args.universe, args.data_end)
    elif args.command == "update":
        cmd_update(cm, args.universe, args.all)
    elif args.command == "clear":
        cmd_clear(cm, args.symbol)


if __name__ == "__main__":
    main()
