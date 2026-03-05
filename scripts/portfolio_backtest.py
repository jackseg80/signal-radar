"""Portfolio Backtest — Signal Radar (Strict Fixed Pool Model).

Rules:
1. Fixed Pool: Buy power = 5000 - current_exposure. Profits NOT reused for parallel trades.
2. Baseline: Sum of PnL for each trade with full $5000 power (account cloning).
3. Conflict tracking: Distinguish between Skips (0 shares) and Truncated (partial shares).
4. Overlaps: Distinguish signal correlation vs real capital conflicts.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from loguru import logger

# Path setup
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from data.base_loader import to_cache_arrays
from data.yahoo_loader import YahooLoader
from engine.indicator_cache import build_cache
from engine.types import Direction, Position
from strategies.rsi2_mean_reversion import RSI2MeanReversion
from strategies.ibs_mean_reversion import IBSMeanReversion
from strategies.turn_of_month import TurnOfMonth

# Constants
OOS_START = "2014-01-01"
OOS_END = "2025-01-01"
CONFIG_PATH = PROJECT_ROOT / "config" / "production_params.yaml"
OUTPUT_DIR = PROJECT_ROOT / "validation_results"

@dataclass
class PortfolioTrade:
    strategy: str
    symbol: str
    entry_date: str
    exit_date: str
    pnl: float
    return_pct: float
    is_truncated: bool = False

from engine.fee_model import FeeModel

def run_portfolio_simulation(
    initial_capital: float,
    strategies_config: dict[str, Any],
    caches: dict[str, Any],
    position_fractions: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Strict Fixed Pool Simulation with Fees."""
    available_pool = initial_capital
    total_realized_pnl = 0.0
    open_positions: dict[tuple[str, str], Position] = {}
    trades_log: list[PortfolioTrade] = []
    
    n_skipped = {"tom": 0, "rsi2": 0, "ibs": 0}
    n_truncated = {"tom": 0, "rsi2": 0, "ibs": 0}
    capital_conflicts = 0
    signal_overlaps_days = 0
    
    all_dates = sorted(set().union(*[c.dates for c in caches.values()]))
    all_dates = [d for d in all_dates if OOS_START <= str(pd.Timestamp(d).date()) < OOS_END]
    
    all_strats = {"rsi2": RSI2MeanReversion(), "ibs": IBSMeanReversion(), "tom": TurnOfMonth()}
    strats = {s: all_strats[s] for s in strategies_config if s in all_strats}
    fractions = position_fractions or {s: strategies_config[s]["params"].get("position_fraction", 1.0) for s in strats}
    max_pos = {s: strategies_config[s].get("max_positions", 1) for s in strats}
    priority = [s for s in ["tom", "rsi2", "ibs"] if s in strategies_config]
    fee_models = {s: FeeModel(strategies_config[s].get("fee_model", "us_stocks_usd_account")) for s in strats}

    for d_idx, date in enumerate(all_dates):
        date_str = str(pd.Timestamp(date).date())
        closed_today = set()
        
        # 1. Exits
        for key, pos in list(open_positions.items()):
            s_name, symbol = key
            cache = caches[symbol]
            try: local_i = np.where(cache.dates == date)[0][0]
            except IndexError: continue
                
            exit_sig = strats[s_name].check_exit(local_i, cache, strategies_config[s_name]["params"], pos)
            if exit_sig:
                exit_price = exit_sig.price
                exit_notional = exit_price * pos.quantity
                exit_fee = fee_models[s_name].total_exit_cost(exit_notional)
                
                # PnL net de frais
                gross_pnl = (exit_price - pos.entry_price) * pos.quantity * pos.direction
                net_pnl = gross_pnl - pos.entry_fee - exit_fee
                
                available_pool += pos.capital_allocated 
                total_realized_pnl += net_pnl
                
                trades_log.append(PortfolioTrade(
                    strategy=s_name, symbol=symbol,
                    entry_date=str(pd.Timestamp(cache.dates[pos.entry_candle]).date()),
                    exit_date=date_str,
                    pnl=net_pnl, return_pct=net_pnl / pos.capital_allocated,
                    is_truncated=pos.state.get("truncated", False)
                ))
                del open_positions[key]
                closed_today.add(key)

        # 2. Entries
        daily_signals = []
        for s_name in priority:
            for symbol in strategies_config[s_name]["universe"]:
                if (s_name, symbol) in closed_today: continue # Prevent same-day exit/entry
                if (s_name, symbol) in open_positions: continue
                
                cache = caches[symbol]
                try: local_i = np.where(cache.dates == date)[0][0]
                except IndexError: continue
                if local_i < strats[s_name].warmup(strategies_config[s_name]["params"]): continue
                
                direction = strats[s_name].check_entry(local_i, cache, strategies_config[s_name]["params"])
                if direction != Direction.FLAT:
                    daily_signals.append((s_name, symbol, direction, local_i))
        
        # 3. Process with Priority
        for s_name, symbol, direction, local_i in daily_signals:
            if sum(1 for k in open_positions if k[0] == s_name) >= max_pos[s_name]: continue
            
            entry_price = float(caches[symbol].opens[local_i])
            if entry_price <= 0: continue
            
            target_alloc = initial_capital * fractions[s_name]
            
            is_truncated = False
            if target_alloc > available_pool:
                capital_conflicts += 1
                if available_pool < entry_price:
                    n_skipped[s_name] += 1
                    continue
                else:
                    actual_alloc = available_pool
                    is_truncated = True
                    n_truncated[s_name] += 1
            else:
                actual_alloc = target_alloc
                
            shares = math.floor(actual_alloc / entry_price)
            if shares < 1:
                n_skipped[s_name] += 1
                continue
                
            cost = shares * entry_price
            entry_fee = fee_models[s_name].total_entry_cost(cost)
            
            available_pool -= cost
            open_positions[(s_name, symbol)] = Position(
                entry_price=entry_price, entry_candle=local_i, quantity=shares,
                direction=direction, capital_allocated=cost, entry_fee=entry_fee,
                state={"truncated": is_truncated}
            )
            
        if len({k[0] for k in open_positions}) > 1:
            signal_overlaps_days += 1

    net_pnl = round(total_realized_pnl, 2)
    returns = [t.return_pct for t in trades_log]
    if len(returns) > 2:
        span_days = (pd.Timestamp(all_dates[-1]) - pd.Timestamp(all_dates[0])).days
        span_years = span_days / 365.25
        tpy = len(trades_log) / span_years if span_years > 0 else 0
        sharpe = round(np.mean(returns) / np.std(returns) * math.sqrt(tpy), 2) if np.std(returns) > 0 else 0.0
    else:
        sharpe = 0.0

    return {
        "n_trades": len(trades_log),
        "n_skipped": sum(n_skipped.values()),
        "n_truncated": sum(n_truncated.values()),
        "skips_by_strategy": n_skipped,
        "truncated_by_strategy": n_truncated,
        "net_pnl": net_pnl,
        "sharpe": sharpe,
        "capital_conflicts": capital_conflicts,
        "signal_overlaps_days": signal_overlaps_days,
        "trades": trades_log
    }

from engine.simulator import simulate
from engine.backtest_config import BacktestConfig

def run_theoretical_baseline(initial_capital: float, strategies_config: dict, caches: dict) -> dict:
    """Cloned Account Model using official engine to ensure 100% matched logic."""
    total_pnl = 0.0
    total_trades = 0
    
    all_strats = {"rsi2": RSI2MeanReversion(), "ibs": IBSMeanReversion(), "tom": TurnOfMonth()}
    strats = {s: all_strats[s] for s in strategies_config if s in all_strats}
    fractions = {s: strategies_config[s]["params"].get("position_fraction", 1.0) for s in strats}

    for s_name, cfg in strategies_config.items():
        if s_name not in strats: continue
        strat = strats[s_name]
        params = cfg["params"]
        frac = fractions[s_name]
        fee_model_name = cfg.get("fee_model", "us_stocks_usd_account")
        fmodel = FeeModel(fee_model_name)
        
        # We enforce the fixed sizing fraction requested in config
        params_fixed = params.copy()
        params_fixed["position_fraction"] = frac
        
        for symbol in cfg["universe"]:
            cache = caches[symbol]
            
            # Find the index corresponding to OOS_START to match portfolio filter
            try:
                start_idx = max(strat.warmup(params_fixed), cache.get_idx_from_date(OOS_START))
                end_idx = cache.get_idx_before_date(OOS_END)
            except ValueError:
                continue

            bt_config = BacktestConfig(
                symbol=symbol,
                initial_capital=initial_capital, # This causes compounding in official engine
                slippage_pct=0.0,
                fee_model=FeeModel(fee_model_name),
                whole_shares=True
            )
            
            # Run official simulation
            res = simulate(strat, cache, params_fixed, bt_config, start_idx=start_idx, end_idx=end_idx)
            
            # Recalculate exactly with fixed $5000 to match portfolio sizing
            for trade in res.trades:
                entry_price = trade.entry_price
                target_alloc = initial_capital * frac
                shares = math.floor(target_alloc / entry_price)
                if shares >= 1:
                    cost = shares * entry_price
                    entry_fee = fmodel.total_entry_cost(cost)
                    exit_fee = fmodel.total_exit_cost(shares * trade.exit_price)
                    gross_pnl = (trade.exit_price - entry_price) * shares * trade.direction
                    net_pnl = gross_pnl - entry_fee - exit_fee
                    total_pnl += net_pnl
                    total_trades += 1

    return {"n_trades": total_trades, "net_pnl": round(total_pnl, 2)}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--capital", type=float, default=5000.0)
    args = parser.parse_args()

    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = yaml.safe_load(f)["strategies"]
    
    all_assets = set()
    for s in config: all_assets.update(config[s]["universe"])
    
    loader = YahooLoader()
    caches = {}
    for symbol in sorted(all_assets):
        df = loader.get_daily_candles(symbol, "2013-01-01", OOS_END)
        caches[symbol] = build_cache(to_cache_arrays(df), {"rsi_period":[2], "sma_trend_period":[200], "sma_exit_period":[5]}, dates=df.index.values)

    actual = run_portfolio_simulation(args.capital, config, caches)
    theo = run_theoretical_baseline(args.capital, config, caches)
    
    print(f"================================================================")
    print(f"PORTFOLIO BACKTEST (STRICT FIXED POOL)")
    print(f"Capital : ${args.capital:,.0f} | Pool: FIXED (No compounding)")
    print(f"================================================================")
    print(f"\nRÉSULTATS RÉELS")
    print(f"  PnL Net          : ${actual['net_pnl']:+,.2f}")
    print(f"  Trades exécutés  : {actual['n_trades']}")
    print(f"  Trades skippés   : {actual['n_skipped']} (Pool vide)")
    print(f"  Trades tronqués  : {actual['n_truncated']} (Pool partiel)")
    
    print(f"\nBASELINE THÉORIQUE (Somme des trades isolés à ${args.capital:,.0f})")
    print(f"  PnL Net          : ${theo['net_pnl']:+,.2f}")
    print(f"  Trades total     : {theo['n_trades']}")
    
    print(f"\nFRICTION & CONFLITS")
    print(f"  PnL perdu        : ${theo['net_pnl'] - actual['net_pnl']:,.2f}")
    print(f"  Conflits capital : {actual['capital_conflicts']} évènements")
    print(f"  Overlaps signaux : {actual['signal_overlaps_days']} jours")
    
    print(f"\nRECOMMANDATION")
    ratio = actual['net_pnl'] / theo['net_pnl'] if theo['net_pnl'] else 0
    print(f"  Efficacité cap.  : {ratio*100:.1f}% de l'alpha capturé")
    print(f"  Cap. suggéré     : ${args.capital * (1/ratio) if ratio > 0.1 else args.capital*5:,.0f}")
    print(f"================================================================")

if __name__ == "__main__":
    main()
