"""Backtest results endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Any

from data.db import SignalRadarDB
from api.config import load_production_config
from api.dependencies import get_db
from cli.runner import STRATEGIES, resolve_market_params
from data.base_loader import BaseDataLoader
from engine.indicator_cache import IndicatorCache
from validation.robustness import run_robustness

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
                "t_stat": None,  # not stored in validations table
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


@router.get("/robustness")
def get_robustness(
    strategy: str,
    symbol: str,
    universe: str,
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Calculate and return robustness matrix for a specific asset/strategy.
    
    This recalculates the matrix on the fly (takes ~1s).
    """
    if strategy not in STRATEGIES:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy} unknown")
    
    strat_class = STRATEGIES[strategy]
    strat_obj = strat_class()
    
    # Load data
    df = db.get_ohlcv(symbol)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"Data for {symbol} not found")
    
    cache = IndicatorCache(df)
    strat_obj.build_cache(cache)
    
    # Resolve params
    from config.universe_loader import load_universe
    univ_cfg = load_universe(universe)
    cap, ws, fee_model, _ = resolve_market_params(univ_cfg)
    
    from engine.backtest_config import BacktestConfig
    config = BacktestConfig(symbol=symbol, capital=cap, whole_shares=ws, fee_model=fee_model)
    
    # Run robustness test
    # Use full OOS period (2014-today)
    start_idx = cache.get_idx_from_date("2014-01-01") or strat_obj.warmup(strat_obj.default_params())
    end_idx = len(cache.close) - 1
    
    result = run_robustness(
        strat_obj, cache, config, 
        start_idx=start_idx, end_idx=end_idx, symbol=symbol
    )
    
    # Format for Heatmap (requires a 2D matrix)
    # The grid is cartesian. We need to decide which params to use for X and Y.
    grid = strat_obj.param_grid()
    keys = list(grid.keys())
    
    if len(keys) < 2:
        return {"robustness": None, "detail": "Grid too small for matrix"}
    
    # For RSI2: rsi_period (1 value), rsi_entry_threshold (4), sma_trend_period (3), sma_exit_period (4)
    # Let's pick the two with most variations or hardcode per strategy
    if strategy == "rsi2":
        # Y: entry_threshold, X: sma_exit_period
        y_key, x_key = "rsi_entry_threshold", "sma_exit_period"
    elif strategy == "ibs":
        # Y: ibs_threshold, X: exit_threshold
        y_key, x_key = "ibs_entry_threshold", "ibs_exit_threshold"
    elif strategy == "tom":
        y_key, x_key = "entry_days_before_eom", "exit_day_of_new_month"
    else:
        y_key, x_key = keys[0], keys[1]

    y_axis = grid[y_key]
    x_axis = grid[x_key]
    
    # Re-map profit_factors into 2D values list
    # The robustness.profit_factors list follows the order of product(*grid.values())
    # We need to filter/group it for the specific X/Y keys
    
    # Simple approach: Re-run a sub-grid or re-sort
    # Let's rebuild the matrix by matching parameters
    values_2d = []
    defaults = strat_obj.default_params()
    
    for y_val in y_axis:
        row = []
        for x_val in x_axis:
            # For each cell, we take the BEST PF among other param variations
            # (e.g. if we vary SMA trend too, we pick the best for this X/Y pair)
            cell_params = {y_key: y_val, x_key: x_val}
            
            # Find all results in the full list that match these two params
            matching_pfs = []
            
            from itertools import product
            grid_keys = list(grid.keys())
            grid_values = [grid[k] for k in grid_keys]
            
            for i, combo in enumerate(product(*grid_values)):
                params_dict = dict(zip(grid_keys, combo))
                if params_dict[y_key] == y_val and params_dict[x_key] == x_val:
                    matching_pfs.append(result.profit_factors[i])
            
            row.append(max(matching_pfs) if matching_pfs else 0.0)
        values_2d.append(row)

    return {
        "robustness": {
            "x_axis": x_axis,
            "y_axis": y_axis,
            "values": values_2d,
            "x_label": x_key,
            "y_label": y_key
        }
    }
