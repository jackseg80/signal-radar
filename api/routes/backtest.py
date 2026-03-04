"""Backtest results endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
import itertools

from data.db import SignalRadarDB
from api.dependencies import get_db
from engine.indicator_cache import IndicatorCache
from validation.robustness import run_robustness

# Import strategies directly
from strategies.rsi2_mean_reversion import RSI2MeanReversion
from strategies.ibs_mean_reversion import IBSMeanReversion
from strategies.turn_of_month import TurnOfMonth

STRATEGIES_MAP = {
    "rsi2": RSI2MeanReversion,
    "ibs": IBSMeanReversion,
    "tom": TurnOfMonth,
}

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
        "results": results,
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
        "results": results,
        "total": len(results),
    }


@router.get("/compare")
def compare_strategies(
    symbols: str | None = None,
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Cross-strategy comparison for selected assets."""
    all_validations = db.get_validations_filtered()
    
    strategies_seen = sorted(list(set(v["strategy"] for v in all_validations)))
    
    # Collect symbols
    if symbols:
        symbol_list = [s.strip().upper() for s in symbols.split(",")]
    else:
        symbol_list = sorted(list(set(v["symbol"] for v in all_validations)))

    matrix = {}
    for v in all_validations:
        sym = v["symbol"]
        strat = v["strategy"]
        if sym in symbol_list:
            matrix.setdefault(sym, {})[strat] = {
                "pf": v["profit_factor"],
                "verdict": v["verdict"],
            }

    return {
        "assets": symbol_list,
        "strategies": strategies_seen,
        "matrix": matrix,
    }


@router.get("/robustness")
def get_robustness(
    strategy: str,
    symbol: str,
    universe: str,
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Calculate and return robustness matrix for a specific asset/strategy."""
    # Find matching strategy key (handle short or long names)
    strat_key = None
    for k in STRATEGIES_MAP:
        if k in strategy.lower():
            strat_key = k
            break
            
    if not strat_key:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy} unknown")
    
    strat_class = STRATEGIES_MAP[strat_key]
    strat_obj = strat_class()
    
    df = db.get_ohlcv(symbol)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"Data for {symbol} not found")
    
    cache = IndicatorCache(df)
    strat_obj.build_cache(cache)
    
    # Simple defaults for on-the-fly robustness
    from engine.backtest_config import BacktestConfig
    from engine.fee_model import US_STOCKS_USD
    config = BacktestConfig(symbol=symbol, capital=10000.0, whole_shares=True, fee_model=US_STOCKS_USD)
    
    start_idx = cache.get_idx_from_date("2014-01-01") or strat_obj.warmup(strat_obj.default_params())
    end_idx = len(cache.close) - 1
    
    result = run_robustness(
        strat_obj, cache, config, 
        start_idx=start_idx, end_idx=end_idx, symbol=symbol
    )
    
    grid = strat_obj.param_grid()
    if "rsi2" in strategy.lower():
        y_key, x_key = "rsi_entry_threshold", "sma_exit_period"
    elif "ibs" in strategy.lower():
        y_key, x_key = "ibs_entry_threshold", "ibs_exit_threshold"
    elif "tom" in strategy.lower():
        y_key, x_key = "entry_days_before_eom", "exit_day_of_new_month"
    else:
        keys = list(grid.keys())
        y_key, x_key = keys[0], keys[1]

    y_axis = grid[y_key]
    x_axis = grid[x_key]
    
    values_2d = []
    grid_keys = list(grid.keys())
    grid_values = [grid[k] for k in grid_keys]
    
    for y_val in y_axis:
        row = []
        for x_val in x_axis:
            matching_pfs = []
            for i, combo in enumerate(itertools.product(*grid_values)):
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
            "x_label": x_key.replace('_', ' ').title(),
            "y_label": y_key.replace('_', ' ').title()
        }
    }
