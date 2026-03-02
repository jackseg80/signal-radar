"""Backtest results endpoints."""

from fastapi import APIRouter, Depends

from data.db import SignalRadarDB
from api.config import load_production_config
from api.dependencies import get_db

router = APIRouter()


@router.get("/screens")
def get_screens(
    strategy: str | None = None,
    universe: str | None = None,
    min_pf: float = 1.0,
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Screening results from the database."""
    results = db.get_screens_filtered(
        strategy=strategy, universe=universe, min_pf=min_pf
    )
    return {
        "results": [
            {
                "strategy": r["strategy"],
                "universe": r["universe"],
                "symbol": r["symbol"],
                "n_trades": r["n_trades"],
                "win_rate": r["win_rate"],
                "profit_factor": r["profit_factor"],
                "sharpe": r["sharpe"],
            }
            for r in results
        ],
        "total": len(results),
    }


@router.get("/validations")
def get_validations(
    strategy: str | None = None,
    universe: str | None = None,
    verdict: str | None = None,
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Full validation results from the database."""
    results = db.get_validations_filtered(
        strategy=strategy, universe=universe, verdict=verdict
    )
    return {
        "results": [
            {
                "strategy": r["strategy"],
                "universe": r["universe"],
                "symbol": r["symbol"],
                "n_trades": r["n_trades"],
                "win_rate": r["win_rate"],
                "profit_factor": r["profit_factor"],
                "sharpe": r["sharpe"],
                "robustness_pct": r["robustness_pct"],
                "t_stat": r.get("ttest_p"),  # DB column is ttest_p
                "p_value": r.get("ttest_p"),
                "verdict": r["verdict"],
            }
            for r in results
        ],
        "total": len(results),
    }


@router.get("/compare")
def compare_strategies(
    symbols: str | None = None,
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Cross-strategy comparison for selected assets."""
    if symbols:
        symbol_list = [s.strip().upper() for s in symbols.split(",")]
    else:
        config = load_production_config()
        # Collect Tier 1 assets from all enabled strategies
        symbol_set: set[str] = set()
        for strat_cfg in config.get("strategies", {}).values():
            if strat_cfg.get("enabled", False):
                symbol_set.update(strat_cfg.get("universe", []))
        symbol_list = sorted(symbol_set)

    # Get validations for each symbol
    all_validations = db.get_validations_filtered()
    strategies_seen: set[str] = set()
    matrix: dict[str, dict[str, dict]] = {}

    for v in all_validations:
        sym = v["symbol"]
        strat = v["strategy"]
        if sym in symbol_list:
            strategies_seen.add(strat)
            matrix.setdefault(sym, {})[strat] = {
                "pf": v["profit_factor"],
                "verdict": v["verdict"],
            }

    return {
        "assets": symbol_list,
        "strategies": sorted(strategies_seen),
        "matrix": matrix,
    }
