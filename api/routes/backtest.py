"""Backtest results endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
import itertools
import math
import pandas as pd

from data.db import SignalRadarDB
from api.dependencies import get_db
from api.config import load_production_config
from data.yahoo_loader import YahooLoader
from data.base_loader import to_cache_arrays
from engine.indicator_cache import build_cache, IndicatorCache
from engine.backtest_config import BacktestConfig
from engine.fee_model import (
    FEE_MODEL_FOREX_SAXO,
    FEE_MODEL_US_ETFS_USD,
    FEE_MODEL_US_STOCKS_USD,
    FeeModel,
)
from engine.simulator import simulate
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

FEE_MODELS: dict[str, FeeModel] = {
    "us_stocks_usd_account": FEE_MODEL_US_STOCKS_USD,
    "us_etfs_usd_account": FEE_MODEL_US_ETFS_USD,
    "forex_saxo": FEE_MODEL_FOREX_SAXO,
    "default": FeeModel(),
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
                "win_rate": v["win_rate"],
                "n_trades": v["n_trades"],
                "sharpe": v["sharpe"]
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
    strat_key = None
    if strategy:
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
    
    cache = IndicatorCache(
        n_candles=len(df),
        opens=df["open"].values,
        highs=df["high"].values,
        lows=df["low"].values,
        closes=df["close"].values,
        volumes=df["volume"].values,
        total_days=len(df) * 365.0 / 252.0
    )
    strat_obj.build_cache(cache)
    
    from engine.backtest_config import BacktestConfig
    from engine.fee_model import FEE_MODEL_US_STOCKS_USD
    config = BacktestConfig(symbol=symbol, initial_capital=10000.0, whole_shares=True, fee_model=FEE_MODEL_US_STOCKS_USD)
    
    start_idx = strat_obj.warmup(strat_obj.default_params())
    end_idx = len(cache.closes) - 1
    
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


@router.get("/equity-curve")
def get_backtest_equity_curve(
    strategy: str,
    symbol: str,
) -> dict:
    """Calculate equity curve and individual trades for an asset/strategy combo."""
    config = load_production_config()
    strat_cfg = config.get("strategies", {}).get(strategy)
    
    if not strat_cfg or symbol not in strat_cfg.get("universe", []):
        raise HTTPException(status_code=404, detail=f"{symbol} not in {strategy} universe")

    params = strat_cfg["params"]
    initial = config.get("capital", 5000.0)
    fee_model_name = strat_cfg.get("fee_model", "us_stocks_usd_account")
    fee_model = FEE_MODELS.get(fee_model_name, FEE_MODELS["default"])

    loader = YahooLoader()
    df = loader.get_daily_candles(symbol, "2013-01-01", "2025-01-01")
    if df.empty:
        raise HTTPException(status_code=404, detail=f"Data for {symbol} not found")

    strat_class = STRATEGIES_MAP.get(strategy)
    if not strat_class:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy} unknown")
    
    strat_obj = strat_class()
    
    # Grid for cache: only the production parameters
    cache_grid = {k: [v] for k, v in params.items() if isinstance(v, (int, float))}
    # Add common MR periods just in case they are missing from params but needed by build_cache
    for p in ["rsi_period", "sma_trend_period", "sma_exit_period", "adx_period", "atr_period"]:
        if p not in cache_grid and p in params:
             cache_grid[p] = [params[p]]
    
    # build_cache expectations: it needs a grid to know which periods to precompute
    # Actually, for a single run, we can just pass the params as single-item lists
    arrays = to_cache_arrays(df)
    cache = build_cache(arrays, cache_grid, dates=df.index.values)

    oos_start_date = "2014-01-01"
    try:
        oos_start = cache.get_idx_from_date(oos_start_date)
    except ValueError:
        oos_start = strat_obj.warmup(params)

    bt_config = BacktestConfig(
        symbol=symbol, 
        initial_capital=initial,
        slippage_pct=0.0, 
        fee_model=fee_model,
        whole_shares=True,
    )
    
    result = simulate(strat_obj, cache, params, bt_config, start_idx=oos_start)

    equity = initial
    peak = initial
    equity_curve = [{"date": oos_start_date, "equity": initial, "drawdown_pct": 0.0}]
    trades_out = []

    for t in result.trades:
        equity += t.pnl
        peak = max(peak, equity)
        dd = (equity - peak) / peak * 100
        
        entry_date = str(pd.Timestamp(cache.dates[t.entry_candle]).date())
        exit_date  = str(pd.Timestamp(cache.dates[t.exit_candle]).date())
        
        equity_curve.append({
            "date": exit_date,
            "equity": round(equity, 2),
            "drawdown_pct": round(dd, 3),
        })
        
        trades_out.append({
            "entry_date":  entry_date,
            "exit_date":   exit_date,
            "entry_price": round(float(t.entry_price), 2),
            "exit_price":  round(float(t.exit_price), 2),
            "return_pct":  round(float(t.return_pct) * 100, 2),
            "pnl":         round(float(t.pnl), 2),
            "is_winner":   bool(t.pnl > 0),
        })

    dds = [float(p["drawdown_pct"]) for p in equity_curve]
    max_dd_idx = dds.index(min(dds)) if dds else 0
    returns = [float(t["return_pct"]) for t in trades_out]

    return {
        "symbol": symbol, 
        "strategy": strategy,
        "n_trades": len(trades_out),
        "equity_curve": equity_curve,
        "trades": trades_out,
        "stats": {
            "max_drawdown_pct":  round(float(min(dds)), 2) if dds else 0.0,
            "max_drawdown_date": equity_curve[max_dd_idx]["date"] if trades_out else None,
            "best_trade_pct":    round(float(max(returns)), 2) if returns else 0.0,
            "worst_trade_pct":   round(float(min(returns)), 2) if returns else 0.0,
            "avg_holding_days":  round(
                float(sum((pd.Timestamp(t["exit_date"]) - pd.Timestamp(t["entry_date"])).days
                    for t in trades_out) / len(trades_out)), 1
            ) if trades_out else 0.0,
        },
    }
