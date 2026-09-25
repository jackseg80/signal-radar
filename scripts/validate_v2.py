"""Run next-open validation without changing the tradeable universe."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.universe_loader import load_universe
from data.db import SignalRadarDB
from data.yahoo_loader import YahooLoader
from engine.fee_model import load_saxo_ch_costs
from engine.ranking import historical_next_open_trades
from engine.trading_calendar import last_completed_session, next_session
from scripts.daily_scanner import load_config
from scripts.safe_scanner import STRATEGIES
from validation.next_open import evaluate_histories


def run_validation(scope: str = "production") -> dict:
    """Recompute all fixed-parameter pairs and save an observational report."""
    if scope not in {"production", "universe"}:
        raise ValueError("scope must be production or universe")
    db = SignalRadarDB()
    loader = YahooLoader()
    model, verified = load_saxo_ch_costs()
    source = last_completed_session()
    end = next_session(source)
    config = load_config()["strategies"]
    if scope == "production":
        pairs = {(name, symbol) for name, cfg in config.items()
                 if cfg.get("enabled", True) for symbol in cfg["universe"]}
    else:
        full = set(load_universe("us_stocks_large").assets)
        full.update(load_universe("us_etfs_broad").assets)
        pairs = {(name, symbol) for name in STRATEGIES for symbol in full}
    histories = {}
    errors = {}
    frames = {}
    for symbol in sorted({symbol for _, symbol in pairs}):
        try:
            frames[symbol] = loader.get_daily_candles_strict(
                symbol, "2013-01-01", end, source,
            )
        except Exception as exc:
            errors[symbol] = str(exc)
    for name, symbol in sorted(pairs):
        if symbol not in frames:
            continue
        strategy = STRATEGIES[name]()
        params = {**strategy.default_params(),
                  **config.get(name, {}).get("params", {}),
                  "position_fraction": 1.0}
        histories[(name, symbol)] = historical_next_open_trades(
            frames[symbol], strategy, params, model,
        )
    report = evaluate_histories(histories, source, model, verified, scope=scope)
    report["data_errors"] = errors
    report["complete"] = not errors
    if errors:
        report["common_portfolio_holdout_partial"] = report["common_portfolio_holdout"]
        report["common_portfolio_holdout"] = None
    report["promotion_policy"] = "No title is added to production configuration automatically"
    if scope == "production" and not errors:
        for row in report["records"]:
            db.upsert_score(row)
    output_dir = Path("validation_results")
    output_dir.mkdir(exist_ok=True)
    path = output_dir / f"next-open-{scope}-{source}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"report_path": str(path), **report}


def main() -> None:
    """CLI entry point for scheduled monthly and quarterly validation."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", choices=["production", "universe"], default="production")
    args = parser.parse_args()
    result = run_validation(args.scope)
    print(f"Validation saved: {result['report_path']}")
    print(f"Pairs: {len(result['records'])}; data errors: {len(result['data_errors'])}")
    print("Costs: verified" if result["costs_verified"] else "Costs: provisional")


if __name__ == "__main__":
    main()
