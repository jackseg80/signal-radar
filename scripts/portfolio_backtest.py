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

def run_portfolio_simulation(
    initial_capital: float,
    strategies_config: dict[str, Any],
    caches: dict[str, Any],
    position_fractions: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Strict Fixed Pool Simulation."""
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

    for d_idx, date in enumerate(all_dates):
        # 1. Exits (freed capital returns to pool, profit goes to vault)
        for key, pos in list(open_positions.items()):
            s_name, symbol = key
            cache = caches[symbol]
            try: local_i = np.where(cache.dates == date)[0][0]
            except IndexError: continue
                
            exit_sig = strats[s_name].check_exit(local_i, cache, strategies_config[s_name]["params"], pos)
            if exit_sig:
                pnl = (exit_sig.price - pos.entry_price) * pos.quantity * pos.direction
                available_pool += pos.capital_allocated # Only the basis returns
                total_realized_pnl += pnl
                
                trades_log.append(PortfolioTrade(
                    strategy=s_name, symbol=symbol,
                    entry_date=str(pd.Timestamp(cache.dates[pos.entry_candle]).date()),
                    exit_date=str(pd.Timestamp(date).date()),
                    pnl=pnl, return_pct=pnl / pos.capital_allocated,
                    is_truncated=pos.state.get("truncated", False)
                ))
                del open_positions[key]

        # 2. Entries
        daily_signals = []
        for s_name in priority:
            for symbol in strategies_config[s_name]["universe"]:
                cache = caches[symbol]
                try: local_i = np.where(cache.dates == date)[0][0]
                except IndexError: continue
                if local_i < strats[s_name].warmup(strategies_config[s_name]["params"]): continue
                if (s_name, symbol) in open_positions: continue
                
                direction = strats[s_name].check_entry(local_i, cache, strategies_config[s_name]["params"])
                if direction != Direction.FLAT:
                    daily_signals.append((s_name, symbol, direction, local_i))
        
        # 3. Process with Priority
        for s_name, symbol, direction, local_i in daily_signals:
            if sum(1 for k in open_positions if k[0] == s_name) >= max_pos[s_name]: continue
            
            entry_price = float(caches[symbol].opens[local_i])
            if entry_price <= 0: continue
            
            target_alloc = initial_capital * fractions[s_name]
            target_shares = math.floor(target_alloc / entry_price)
            if target_shares < 1: continue
            
            is_truncated = False
            # Can we afford the full target?
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
            if shares < 1: # Double check after floor
                n_skipped[s_name] += 1
                continue
                
            cost = shares * entry_price
            available_pool -= cost
            open_positions[(s_name, symbol)] = Position(
                entry_price=entry_price, entry_candle=local_i, quantity=shares,
                direction=direction, capital_allocated=cost, entry_fee=0.0,
                state={"truncated": is_truncated}
            )
            
        if len({k[0] for k in open_positions}) > 1:
            signal_overlaps_days += 1

    return {
        "n_trades": len(trades_log),
        "n_skipped": sum(n_skipped.values()),
        "n_truncated": sum(n_truncated.values()),
        "skips_by_strategy": n_skipped,
        "truncated_by_strategy": n_truncated,
        "net_pnl": round(total_realized_pnl, 2),
        "capital_conflicts": capital_conflicts,
        "signal_overlaps_days": signal_overlaps_days,
        "trades": trades_log
    }

def run_theoretical_baseline(initial_capital: float, strategies_config: dict, caches: dict) -> dict:
    """Cloned Account Model: Each trade gets a full $5000 pool."""
    total_pnl = 0.0
    total_trades = 0
    
    for s_name, cfg in strategies_config.items():
        # Simulate each strategy independently with a huge pool to avoid any internal conflict
        # but sizing is strictly floor(initial_capital * fraction / price)
        res = run_portfolio_simulation(initial_capital * 1000, {s_name: cfg}, caches, 
                                       position_fractions={s_name: cfg["params"].get("position_fraction", 1.0)})
        # Scaling adjustment: because run_portfolio_simulation uses initial_capital (which is now 1000x) for sizing,
        # we need to pass the target basis separately. 
        # Refactoring run_portfolio_simulation slightly to take sizing_basis.
        pass

    # Correct way: re-run simulation with available_pool = infinity
    total_pnl = 0.0
    total_trades = 0
    for s_name, cfg in strategies_config.items():
        # Manual trades collection for each asset in universe
        for symbol in cfg["universe"]:
            cache = caches[symbol]
            strat = {"rsi2": RSI2MeanReversion(), "ibs": IBSMeanReversion(), "tom": TurnOfMonth()}[s_name]
            params = cfg["params"]
            frac = params.get("position_fraction", 1.0)
            
            # Simple isolated simulation
            pos = None
            for i in range(strat.warmup(params), len(cache.dates)):
                date = cache.dates[i]
                if str(pd.Timestamp(date).date()) < OOS_START or str(pd.Timestamp(date).date()) >= OOS_END: continue
                
                if pos:
                    exit_sig = strat.check_exit(i, cache, params, pos)
                    if exit_sig:
                        total_pnl += (exit_sig.price - pos.entry_price) * pos.quantity * pos.direction
                        total_trades += 1
                        pos = None
                else:
                    direction = strat.check_entry(i, cache, params)
                    if direction != Direction.FLAT:
                        entry_price = float(cache.opens[i])
                        shares = math.floor((initial_capital * frac) / entry_price)
                        if shares >= 1:
                            pos = Position(entry_price, i, shares, direction, shares*entry_price, 0.0)
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
