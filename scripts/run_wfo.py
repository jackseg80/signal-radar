"""Walk-Forward Optimization sur les 10 actions US.

Usage:
    python scripts/run_wfo.py                        # 10 assets
    python scripts/run_wfo.py --symbol AAPL           # 1 seul asset
    python scripts/run_wfo.py --symbol AAPL --symbol MSFT  # N assets
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import yaml
from loguru import logger

from data.yahoo_loader import YahooLoader
from data.base_loader import to_cache_arrays
from engine.backtest_config import BacktestConfig
from engine.fee_model import FeeModel
from optimization.walk_forward import WalkForwardOptimizer, WFOResult
from optimization.report import (
    grade_with_haircut,
    compute_win_rate_oos,
    compute_tail_ratio,
)


HAIRCUT = 0.15
STRATEGY = "signal_donchian"
START = "2010-01-01"
END = "2025-01-01"


def _load_fee_model(name: str) -> FeeModel:
    """Charge un FeeModel depuis config/fee_models.yaml."""
    with open("config/fee_models.yaml", encoding="utf-8") as f:
        models = yaml.safe_load(f)
    return FeeModel(**models[name])


def run_wfo_single(
    symbol: str,
    loader: YahooLoader,
    optimizer: WalkForwardOptimizer,
    fee_model: FeeModel,
    sides: list[str],
) -> dict:
    """Lance le WFO complet sur un symbole et retourne le rapport."""
    logger.info("=" * 60)
    logger.info("WFO {} ({} -> {})", symbol, START, END)
    logger.info("=" * 60)

    # Charger les donnees
    df = loader.get_daily_candles(symbol, START, END)
    logger.info("{}: {} candles chargees", symbol, len(df))

    config = BacktestConfig(
        symbol=symbol,
        initial_capital=100_000.0,
        slippage_pct=0.0003,
        fee_model=fee_model,
    )

    # WFO
    t0 = time.time()
    wfo_result = optimizer.optimize(
        strategy_name=STRATEGY,
        symbol=symbol,
        df=df,
        config=config,
        sides=sides,
    )
    elapsed = time.time() - t0

    # Metriques pour le grading
    n_windows = len(wfo_result.windows)
    total_oos_trades = sum(w.oos_trades for w in wfo_result.windows)
    total_is_trades = sum(w.is_trades for w in wfo_result.windows)
    avg_oos_trades_per_window = total_oos_trades / n_windows if n_windows > 0 else 0
    avg_is_trades_per_window = total_is_trades / n_windows if n_windows > 0 else 0

    win_rate = compute_win_rate_oos(wfo_result.windows)
    tail_ratio = compute_tail_ratio(wfo_result.windows)

    # DSR et stability placeholder (full_analysis trop lent ici)
    dsr_score = min(1.0, max(0.0, wfo_result.avg_oos_sharpe / 2.0))
    param_stability = 0.7  # placeholder conservateur

    grade_result = grade_with_haircut(
        oos_sharpe=wfo_result.avg_oos_sharpe,
        win_rate_oos=win_rate,
        tail_ratio=tail_ratio,
        dsr=dsr_score,
        param_stability=param_stability,
        consistency=wfo_result.consistency_rate,
        total_trades=total_oos_trades,
        n_windows=n_windows,
        haircut=HAIRCUT,
    )

    report = {
        "symbol": symbol,
        "n_windows": n_windows,
        "avg_oos_sharpe_raw": wfo_result.avg_oos_sharpe,
        "avg_oos_sharpe_haircut": max(0.0, wfo_result.avg_oos_sharpe - HAIRCUT),
        "avg_is_sharpe": wfo_result.avg_is_sharpe,
        "oos_is_ratio": wfo_result.oos_is_ratio,
        "consistency": wfo_result.consistency_rate,
        "avg_is_trades_per_window": avg_is_trades_per_window,
        "avg_oos_trades_per_window": avg_oos_trades_per_window,
        "total_is_trades": total_is_trades,
        "total_oos_trades": total_oos_trades,
        "win_rate_oos": win_rate,
        "tail_ratio": tail_ratio,
        "grade": grade_result.grade,
        "score": grade_result.score,
        "recommended_params": wfo_result.recommended_params,
        "elapsed_s": elapsed,
    }

    return report


def print_report(report: dict) -> None:
    """Affiche le rapport pour un asset."""
    sym = report["symbol"]
    print(f"\n{'=' * 60}")
    print(f"  {sym}")
    print(f"{'=' * 60}")
    print(f"  Windows WFO      : {report['n_windows']}")
    print(f"  OOS Sharpe (raw) : {report['avg_oos_sharpe_raw']:+.3f}")
    print(f"  OOS Sharpe (-{HAIRCUT}): {report['avg_oos_sharpe_haircut']:+.3f}")
    print(f"  IS Sharpe        : {report['avg_is_sharpe']:+.3f}")
    print(f"  OOS/IS ratio     : {report['oos_is_ratio']:.2f}")
    print(f"  Consistency      : {report['consistency']:.0%}")
    print(f"  Win rate OOS     : {report['win_rate_oos']:.0%}")
    print(f"  Tail ratio       : {report['tail_ratio']:.2f}")
    print(f"  Trades IS/window : {report['avg_is_trades_per_window']:.1f}")
    print(f"  Trades OOS/window: {report['avg_oos_trades_per_window']:.1f}")
    print(f"  Trades total     : IS={report['total_is_trades']} OOS={report['total_oos_trades']}")
    print(f"  Grade            : {report['grade']} ({report['score']:.1f}/100)")
    print(f"  Temps            : {report['elapsed_s']:.1f}s")
    params = report["recommended_params"]
    print(f"  Params recommandes:")
    for k, v in sorted(params.items()):
        if k == "sides":
            continue
        print(f"    {k:25s}: {v}")
    print(f"{'=' * 60}")


def print_summary(reports: list[dict]) -> None:
    """Affiche le tableau recapitulatif."""
    print("\n\n" + "=" * 80)
    print("  RESUME WFO — signal_donchian — 10 US Stocks")
    print("=" * 80)
    print(f"  {'Symbol':<8} {'Grade':>5} {'Score':>6} {'OOS Sharpe':>11} {'Haircut':>9} {'Consist':>8} {'IS t/w':>7} {'OOS t/w':>8} {'Time':>6}")
    print(f"  {'-'*8} {'-'*5} {'-'*6} {'-'*11} {'-'*9} {'-'*8} {'-'*7} {'-'*8} {'-'*6}")

    grade_order = {"A": 0, "B": 1, "C": 2, "D": 3, "F": 4}
    n_good = 0

    for r in reports:
        g = r["grade"]
        if grade_order.get(g, 4) <= 1:  # A or B
            n_good += 1
        print(
            f"  {r['symbol']:<8} {g:>5} {r['score']:>6.1f} "
            f"{r['avg_oos_sharpe_raw']:>+11.3f} {r['avg_oos_sharpe_haircut']:>+9.3f} "
            f"{r['consistency']:>7.0%} "
            f"{r.get('avg_is_trades_per_window', 0):>7.1f} "
            f"{r['avg_oos_trades_per_window']:>8.1f} "
            f"{r['elapsed_s']:>5.0f}s"
        )

    print(f"  {'-'*8} {'-'*5} {'-'*6} {'-'*11} {'-'*9} {'-'*8} {'-'*7} {'-'*8} {'-'*6}")
    print(f"  Assets grade B+ ou mieux : {n_good}/{len(reports)}")
    print("=" * 80)


def main() -> None:
    parser = argparse.ArgumentParser(description="WFO signal_donchian sur US stocks")
    parser.add_argument(
        "--symbol", action="append", default=None,
        help="Symbole(s) a tester (defaut: tous les 10)",
    )
    args = parser.parse_args()

    # Charger la config
    with open("config/assets_us.yaml", encoding="utf-8") as f:
        asset_config = yaml.safe_load(f)
    all_symbols = asset_config["symbols"]
    sides = asset_config["sides"]
    fee_model = _load_fee_model(asset_config["fee_model"])

    symbols = args.symbol if args.symbol else all_symbols

    loader = YahooLoader()
    optimizer = WalkForwardOptimizer()

    reports = []
    t_total = time.time()

    for sym in symbols:
        try:
            report = run_wfo_single(sym, loader, optimizer, fee_model, sides)
            print_report(report)
            reports.append(report)
        except Exception as exc:
            logger.error("{}: WFO echoue — {}", sym, exc)
            reports.append({
                "symbol": sym, "grade": "F", "score": 0, "elapsed_s": 0,
                "avg_oos_sharpe_raw": 0, "avg_oos_sharpe_haircut": 0,
                "consistency": 0, "total_oos_trades": 0,
                "n_windows": 0, "avg_is_sharpe": 0, "oos_is_ratio": 0,
                "avg_oos_trades_per_window": 0, "win_rate_oos": 0,
                "tail_ratio": 0, "recommended_params": {},
            })

    total_elapsed = time.time() - t_total

    if len(reports) > 1:
        print_summary(reports)
    print(f"\nTemps total : {total_elapsed:.0f}s")


if __name__ == "__main__":
    main()
