"""Portfolio Backtest — Signal Radar.

Simulates multiple strategies running on shared capital ($5,000).
Quantifies capital conflicts, skipped trades, and sizing recommendations.

Priority Rule: TOM > RSI2 > IBS
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
from engine.types import Direction, ExitSignal, Position, TradeResult
from strategies.rsi2_mean_reversion import RSI2MeanReversion
from strategies.ibs_mean_reversion import IBSMeanReversion
from strategies.turn_of_month import TurnOfMonth

# Constants
OOS_START = "2014-01-01"
OOS_END = "2025-01-01"
CONFIG_PATH = PROJECT_ROOT / "config" / "production_params.yaml"
OUTPUT_DIR = PROJECT_ROOT / "validation_results"

# ---------------------------------------------------------------------------
# Core simulation logic
# ---------------------------------------------------------------------------

@dataclass
class PortfolioTrade:
    strategy: str
    symbol: str
    entry_date: str
    exit_date: str
    pnl: float
    return_pct: float
    holding_days: int

def run_portfolio_simulation(
    initial_capital: float,
    strategies_config: dict[str, Any],
    caches: dict[str, Any],
    position_fractions: dict[str, float] | None = None,
    use_compounding: bool = False,
) -> dict[str, Any]:
    """Runs a day-by-day simulation across all strategies and assets."""
    shared_capital = initial_capital
    open_positions: dict[tuple[str, str], Position] = {}
    trades_log: list[PortfolioTrade] = []
    
    # Track statistics
    n_skipped = {"tom": 0, "rsi2": 0, "ibs": 0}
    overlaps = {"rsi2_ibs": 0, "tom_rsi2": 0, "tom_ibs": 0, "all_three": 0}
    
    all_dates = sorted(set().union(*[c.dates for c in caches.values()]))
    all_dates = [d for d in all_dates if OOS_START <= str(pd.Timestamp(d).date()) < OOS_END]
    
    all_strats = {
        "rsi2": RSI2MeanReversion(),
        "ibs": IBSMeanReversion(),
        "tom": TurnOfMonth(),
    }
    strats = {s: all_strats[s] for s in strategies_config if s in all_strats}
    
    fractions = position_fractions or {
        s: strategies_config[s]["params"].get("position_fraction", 1.0)
        for s in strats
    }
    
    max_pos = {s: strategies_config[s].get("max_positions", 1) for s in strats}
    priority = [s for s in ["tom", "rsi2", "ibs"] if s in strategies_config]

    for d_idx, date in enumerate(all_dates):
        date_str = str(pd.Timestamp(date).date())
        
        # 1. Handle Exits
        for key, pos in list(open_positions.items()):
            s_name, symbol = key
            cache = caches[symbol]
            try:
                local_i = np.where(cache.dates == date)[0][0]
            except IndexError: continue
                
            exit_sig = strats[s_name].check_exit(local_i, cache, strategies_config[s_name]["params"], pos)
            if exit_sig:
                exit_price = exit_sig.price
                pnl = (exit_price - pos.entry_price) * pos.quantity * pos.direction
                shared_capital += pos.capital_allocated + pnl
                
                trades_log.append(PortfolioTrade(
                    strategy=s_name, symbol=symbol,
                    entry_date=str(pd.Timestamp(cache.dates[pos.entry_candle]).date()),
                    exit_date=date_str, pnl=pnl,
                    return_pct=pnl / pos.capital_allocated,
                    holding_days=local_i - pos.entry_candle
                ))
                del open_positions[key]

        # 2. Collect Entry Signals
        daily_signals = []
        for s_name in priority:
            for symbol in strategies_config[s_name]["universe"]:
                cache = caches[symbol]
                try:
                    local_i = np.where(cache.dates == date)[0][0]
                except IndexError: continue
                
                if local_i < strats[s_name].warmup(strategies_config[s_name]["params"]): continue
                    
                direction = strats[s_name].check_entry(local_i, cache, strategies_config[s_name]["params"])
                if direction != Direction.FLAT:
                    daily_signals.append((s_name, symbol, direction, local_i))
        
        # 3. Process Entries
        for s_name, symbol, direction, local_i in daily_signals:
            if (s_name, symbol) in open_positions: continue
                
            n_open_strat = sum(1 for k in open_positions if k[0] == s_name)
            if n_open_strat >= max_pos[s_name]: continue
                
            # Fixed Sizing (No compounding)
            # Use a fraction of INITIAL capital for sizing if use_compounding is False
            basis = shared_capital if use_compounding else initial_capital
            required_capital = basis * fractions[s_name]
            
            # Capital guard: check against CURRENT shared capital
            if required_capital > shared_capital:
                # Could we buy at least 1 share with what's left?
                # If not, it's a skip
                if shared_capital < caches[symbol].opens[local_i]:
                    n_skipped[s_name] += 1
                    continue
                else:
                    # Scale down to available capital (partial fill)
                    required_capital = shared_capital
                
            entry_price = float(caches[symbol].opens[local_i])
            if entry_price <= 0: continue
            
            shares = math.floor(required_capital / entry_price)
            cost = shares * entry_price
            
            if shares < 1:
                n_skipped[s_name] += 1
                continue
                
            shared_capital -= cost
            open_positions[(s_name, symbol)] = Position(
                entry_price=entry_price, entry_candle=local_i, quantity=shares,
                direction=direction, capital_allocated=cost, entry_fee=0.0
            )
            
        # 4. Track overlaps
        active_strats = {k[0] for k in open_positions}
        if "rsi2" in active_strats and "ibs" in active_strats: overlaps["rsi2_ibs"] += 1
        if "tom" in active_strats and "rsi2" in active_strats: overlaps["tom_rsi2"] += 1
        if "tom" in active_strats and "ibs" in active_strats: overlaps["tom_ibs"] += 1
        if len(active_strats) == 3: overlaps["all_three"] += 1

    net_pnl = sum(t.pnl for t in trades_log)
    returns = [t.return_pct for t in trades_log]
    
    if len(returns) > 2:
        span_years = (pd.Timestamp(all_dates[-1]) - pd.Timestamp(all_dates[0])).days / 365.25
        tpy = len(trades_log) / span_years
        sharpe = np.mean(returns) / np.std(returns) * math.sqrt(tpy)
    else: sharpe = 0.0
        
    return {
        "n_trades": len(trades_log),
        "n_skipped": sum(n_skipped.values()),
        "skips_by_strategy": n_skipped,
        "net_pnl": round(net_pnl, 2),
        "sharpe": round(sharpe, 2),
        "overlaps": overlaps,
        "final_capital": round(shared_capital + sum(p.capital_allocated for p in open_positions.values()), 2),
        "trades": trades_log
    }

# ---------------------------------------------------------------------------
# Baseline & Sizing Search
# ---------------------------------------------------------------------------

def run_baseline(initial_capital: float, strategies_config: dict, caches: dict) -> dict:
    """Calculates theoretical PnL (isolated backtests, infinite capital)."""
    # Simply sum results of simulations with infinite capital (or 100% per trade)
    # but ignoring shared constraints.
    total_pnl = 0.0
    total_trades = 0
    
    for s_name in ["rsi2", "ibs", "tom"]:
        # Run each strategy standalone
        s_cfg = {s_name: strategies_config[s_name]}
        # Force position_fraction to 1.0/0.2 as per standard sizing
        res = run_portfolio_simulation(initial_capital * 10, s_cfg, caches)
        total_pnl += res["net_pnl"]
        total_trades += res["n_trades"]
        
    return {"n_trades": total_trades, "net_pnl": total_pnl}

def find_sizing_recommendation(initial_capital: float, strategies_config: dict, caches: dict) -> dict:
    """Brute force search for better sizing fractions."""
    best_pnl = -float("inf")
    best_fracs = {}
    
    logger.info("Searching for sizing recommendation...")
    
    # We keep RSI2 at 0.2 (canonical)
    # Search IBS [0.3 to 1.0] and TOM [0.5 to 1.0]
    for ibs_f in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0]:
        for tom_f in [0.5, 0.6, 0.7, 0.8, 1.0]:
            fracs = {"rsi2": 0.2, "ibs": ibs_f, "tom": tom_f}
            res = run_portfolio_simulation(initial_capital, strategies_config, caches, fracs)
            if res["net_pnl"] > best_pnl:
                best_pnl = res["net_pnl"]
                best_fracs = fracs
                
    return best_fracs

# ---------------------------------------------------------------------------
# CLI & Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Portfolio Backtest Analyzer")
    parser.add_argument("--capital", type=float, default=5000.0, help="Initial shared capital")
    parser.add_argument("--dry-run", action="store_true", help="Afficher la config sans lancer")
    args = parser.parse_args()

    # 1. Load Config
    with open(CONFIG_PATH, encoding="utf-8") as f:
        full_config = yaml.safe_load(f)
    
    strategies_config = full_config["strategies"]
    
    # Extract unique assets across all validated universes
    all_assets = set()
    for s_name in ["rsi2", "ibs", "tom"]:
        all_assets.update(strategies_config[s_name]["universe"])
    
    print(f"================================================================")
    print(f"PORTFOLIO BACKTEST — Signal Radar")
    print(f"Capital partagé : ${args.capital:,.0f} | Période : 2014-2025")
    print(f"Priorité        : TOM > RSI2 > IBS")
    print(f"Assets          : {len(all_assets)} unique symbols")
    print(f"================================================================")
    
    if args.dry_run:
        print("Dry run complete.")
        return

    # 2. Fetch Data
    logger.info("Fetching data for {} assets...", len(all_assets))
    loader = YahooLoader()
    caches = {}
    for symbol in sorted(all_assets):
        try:
            # We fetch a bit extra for warmup
            df = loader.get_daily_candles(symbol, "2013-01-01", OOS_END)
            arrays = to_cache_arrays(df)
            # Precompute indicators for all strategies at once
            grid = {
                "rsi_period": [2],
                "sma_trend_period": [200],
                "sma_exit_period": [5],
            }
            caches[symbol] = build_cache(arrays, grid, dates=df.index.values)
        except Exception as e:
            logger.error(f"Failed to fetch {symbol}: {e}")

    # 3. Simulations
    logger.info("Running portfolio simulation...")
    actual = run_portfolio_simulation(args.capital, strategies_config, caches)
    
    logger.info("Running theoretical baseline...")
    theoretical = run_baseline(args.capital, strategies_config, caches)
    
    # 4. Sizing Search
    rec_fracs = find_sizing_recommendation(args.capital, strategies_config, caches)
    
    # 5. Report
    friction_pnl = theoretical["net_pnl"] - actual["net_pnl"]
    actual_return = (actual["net_pnl"] / args.capital) * 100
    theo_return = (theoretical["net_pnl"] / args.capital) * 100
    
    print(f"\nRÉSULTATS RÉELS (capital partagé ${args.capital:,.0f})")
    print(f"  Trades tentés    : {theoretical['n_trades']}")
    print(f"  Trades exécutés  : {actual['n_trades']}  ({actual['n_trades']/theoretical['n_trades']*100:.1f}%)")
    print(f"  Trades skippés   : {actual['n_skipped']}   ({actual['n_skipped']/theoretical['n_trades']*100:.1f}%)")
    print(f"  Net PnL          : ${actual['net_pnl']:+,.2f}  ({actual_return:+.1f}%)")
    print(f"  Sharpe           : {actual['sharpe']}")

    print(f"\nBASELINE THÉORIQUE (3 backtests isolés, capital infini)")
    print(f"  Trades total     : {theoretical['n_trades']}")
    print(f"  Net PnL          : ${theoretical['net_pnl']:+,.2f}  ({theo_return:+.1f}%)")

    print(f"\nCOÛT DES CONFLITS DE CAPITAL")
    print(f"  PnL perdu        : ${friction_pnl:,.2f}  ({friction_pnl/args.capital*100:.1f} points)")
    print(f"  Skips par stratégie:")
    for s, n in actual["skips_by_strategy"].items():
        print(f"    {s.upper():4s} : {n}")

    print(f"\nCHEVAUCHEMENTS DÉTECTÉS (en jours de trading)")
    print(f"  RSI2 + IBS simultanés  : {actual['overlaps']['rsi2_ibs']}x")
    print(f"  TOM  + RSI2 simultanés : {actual['overlaps']['tom_rsi2']}x")
    print(f"  TOM  + IBS  simultanés : {actual['overlaps']['tom_ibs']}x")
    print(f"  TOM  + RSI2 + IBS      : {actual['overlaps']['all_three']}x")

    print(f"\nRECOMMANDATIONS (sizing basé sur l'analyse des conflits)")
    print(f"  Position fraction optimale  : RSI2={rec_fracs['rsi2']:.2f}, IBS={rec_fracs['ibs']:.2f}, TOM={rec_fracs['tom']:.2f}")
    
    # Estimate min capital for zero friction (simple heuristic)
    # Friction cost relative to theoretical PnL gives a hint on capital deficiency
    required_increase = (theoretical["net_pnl"] / actual["net_pnl"]) if actual["net_pnl"] > 0 else 2.0
    min_cap = args.capital * required_increase
    print(f"  Capital minimum sans friction: ~${min_cap:,.0f}")
    
    if actual["skips_by_strategy"]["ibs"] > actual["skips_by_strategy"]["rsi2"]:
        print(f"  → Avec ${args.capital:,.0f} : réduire IBS fraction pour éviter les skips les plus coûteux")

    print(f"================================================================\n")

    # 6. Save JSON
    report = {
        "run_date": datetime.now().isoformat(),
        "capital": args.capital,
        "period": {"start": OOS_START, "end": OOS_END},
        "actual": {
            "n_trades": actual["n_trades"],
            "n_skipped": actual["n_skipped"],
            "net_pnl": actual["net_pnl"],
            "sharpe": actual["sharpe"]
        },
        "theoretical": theoretical,
        "friction_cost": round(friction_pnl, 2),
        "overlaps": actual["overlaps"],
        "skips_by_strategy": actual["skips_by_strategy"],
        "recommendations": {
            "position_fractions": rec_fracs,
            "min_capital_no_friction": round(min_cap, 0)
        }
    }
    
    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / f"portfolio_backtest_{datetime.now():%Y%m%d_%H%M%S}.json"
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)
    logger.info(f"Report saved to {out_path}")

if __name__ == "__main__":
    main()
