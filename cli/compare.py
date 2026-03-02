"""Compare les resultats de validation sauvegardes.

Usage:
    python -m cli.compare
    python -m cli.compare --dir validation_results

Charge tous les fichiers JSON dans validation_results/ et affiche un
tableau croise strategie x asset avec les PF et verdicts.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load_results(results_dir: Path) -> list[dict]:
    """Charge tous les fichiers JSON de resultats."""
    files = sorted(results_dir.glob("*.json"))
    results = []
    for f in files:
        with open(f, encoding="utf-8") as fh:
            data = json.load(fh)
            data["_file"] = f.name
            results.append(data)
    return results


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Compare validation results")
    parser.add_argument("--dir", type=str, default="validation_results", help="Results directory")
    args = parser.parse_args()

    results_dir = Path(args.dir)
    if not results_dir.exists():
        print(f"  Error: directory '{results_dir}' not found")
        sys.exit(1)

    results = _load_results(results_dir)
    if not results:
        print(f"  No results found in {results_dir}/")
        print("  Run 'python -m cli.validate <strategy> <universe>' first.")
        sys.exit(0)

    # ── Index : strategies et symbols ──
    strategies: list[str] = []
    seen_strategies: set[str] = set()
    # {strategy: {symbol: {"pf": ..., "verdict": ...}}}
    data_map: dict[str, dict[str, dict]] = {}

    all_symbols: set[str] = set()

    for r in results:
        strat = r.get("strategy", "?")
        univ = r.get("universe", "?")
        key = f"{strat}/{univ}"
        if key not in seen_strategies:
            strategies.append(key)
            seen_strategies.add(key)
        data_map[key] = {}
        for a in r.get("assets", []):
            sym = a["symbol"]
            all_symbols.add(sym)
            data_map[key][sym] = {
                "pf": a.get("profit_factor", 0.0),
                "verdict": a.get("verdict", "?"),
            }

    # Trier les symboles par ordre alphabetique
    symbols = sorted(all_symbols)

    if not strategies:
        print("  No strategies found in results.")
        sys.exit(0)

    # ── Affichage ──
    sep = "=" * (14 + len(strategies) * 14)
    print(f"\n{sep}")
    print("  Validation Results Comparison")
    print(sep)

    # Header
    header = f"  {'Ticker':<12}"
    for s in strategies:
        # Truncate long names
        label = s[:12]
        header += f" {label:>12}"
    print(header)
    print("  " + "-" * (10 + len(strategies) * 14))

    # Verdict symbols
    verdict_markers = {
        "VALIDATED": "[V]",
        "CONDITIONAL": "[C]",
        "REJECTED": "[R]",
    }

    for sym in symbols:
        row = f"  {sym:<12}"
        for strat_key in strategies:
            asset_data = data_map.get(strat_key, {}).get(sym)
            if asset_data is None:
                row += f" {'---':>12}"
            else:
                pf = asset_data["pf"]
                marker = verdict_markers.get(asset_data["verdict"], "?")
                pf_str = f"{pf:.2f}" if pf < 100 else "inf"
                row += f" {pf_str + ' ' + marker:>12}"
        print(row)

    # ── Resume par strategie ──
    print()
    for strat_key in strategies:
        assets = data_map.get(strat_key, {})
        n_v = sum(1 for a in assets.values() if a["verdict"] == "VALIDATED")
        n_c = sum(1 for a in assets.values() if a["verdict"] == "CONDITIONAL")
        n_r = sum(1 for a in assets.values() if a["verdict"] == "REJECTED")
        print(f"  {strat_key}: {n_v} VALIDATED, {n_c} CONDITIONAL, {n_r} REJECTED")

    # ── Source files ──
    print(f"\n  Source files ({len(results)}):")
    for r in results:
        print(f"    {r['_file']}")

    print(sep)


if __name__ == "__main__":
    main()
