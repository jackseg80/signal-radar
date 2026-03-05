"""MAE Analysis — Stop Loss Impact.

Analyzes the Maximum Adverse Excursion (MAE) of every trade in OOS
to determine the optimal operational stop loss level.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

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
from engine.simulator import simulate
from engine.backtest_config import BacktestConfig
from engine.fee_model import FeeModel
from strategies.rsi2_mean_reversion import RSI2MeanReversion
from strategies.ibs_mean_reversion import IBSMeanReversion
from strategies.turn_of_month import TurnOfMonth

# Constants
OOS_START = "2014-01-01"
OOS_END = "2025-01-01"
CONFIG_PATH = PROJECT_ROOT / "config" / "production_params.yaml"
OUTPUT_DIR = PROJECT_ROOT / "validation_results"


class MAEAnalyzer:
    def __init__(self):
        self.all_trades = []

    def process_asset(self, strat_name: str, strat_obj, symbol: str, cache, params: dict, fee_model_name: str):
        # Find start and end indices for OOS
        try:
            start_idx = max(strat_obj.warmup(params), cache.get_idx_from_date(OOS_START))
            end_idx = cache.get_idx_before_date(OOS_END)
        except ValueError:
            return None

        bt_config = BacktestConfig(
            symbol=symbol,
            initial_capital=5000.0,
            slippage_pct=0.0,
            fee_model=FeeModel(fee_model_name),
            whole_shares=True
        )

        res = simulate(strat_obj, cache, params, bt_config, start_idx=start_idx, end_idx=end_idx)
        
        trades_data = []
        for t in res.trades:
            # Calculate MAE (Maximum Adverse Excursion)
            # We look at the lows from entry_candle to exit_candle (inclusive)
            # If short, we would look at highs, but these are long-only strategies
            period_lows = cache.lows[t.entry_candle:t.exit_candle + 1]
            if len(period_lows) > 0:
                min_low = np.min(period_lows)
                mae_pct = (min_low / t.entry_price) - 1.0
            else:
                mae_pct = 0.0
            
            is_winner = t.pnl > 0
            
            trade_info = {
                "strategy": strat_name,
                "symbol": symbol,
                "mae_pct": mae_pct,
                "return_pct": t.return_pct,
                "is_winner": is_winner
            }
            trades_data.append(trade_info)
            self.all_trades.append(trade_info)
            
        return trades_data

    def generate_report(self) -> str:
        lines = []
        lines.append("================================================================")
        lines.append(f"MAE ANALYSIS — Stop Loss Impact (OOS {OOS_START[:4]}-{OOS_END[:4]})")
        lines.append("================================================================")
        
        df = pd.DataFrame(self.all_trades)
        if df.empty:
            return "No trades found."

        sl_levels = [-0.05, -0.08, -0.10, -0.15, -0.20]
        
        # 1. By Strategy & Asset
        grouped = df.groupby(["strategy", "symbol"])
        
        for (strat, symbol), group in grouped:
            n_trades = len(group)
            if n_trades == 0: continue
            
            lines.append(f"\n{strat.upper()} — {symbol} ({n_trades} trades)")
            
            # MAE Distribution
            maes = group["mae_pct"].values
            p50 = np.percentile(maes, 50) # median is actually the 50th percentile of worst drops
            # But wait, MAE is negative. So worst drops are the low percentiles.
            # E.g. 5% of trades drop more than p05.
            # To match the spec: "p90 : -5.1% (90% des trades descendent moins que ça)"
            # This means we sort MAEs, and the 10th percentile is p90 of 'not dropping below'.
            # Let's use np.percentile. If sorted descending (0 to -1), 
            # 50% descendent moins que = percentile 50.
            # Actually, just taking percentile(maes, [50, 25, 10, 5, 1]) gives the thresholds.
            # wait, np.percentile(arr, 10) gives the value below which 10% of observations fall.
            # So 10% fall below -5%, meaning 90% fall ABOVE -5% (i.e. descendent moins que -5%).
            
            p50 = np.percentile(maes, 50)
            p75 = np.percentile(maes, 25)
            p90 = np.percentile(maes, 10)
            p95 = np.percentile(maes, 5)
            p99 = np.percentile(maes, 1)
            worst = np.min(maes)
            
            lines.append("  MAE distribution :")
            lines.append(f"    p50  : {p50*100:5.1f}%    (50% des trades descendent moins que ça)")
            lines.append(f"    p75  : {p75*100:5.1f}%")
            lines.append(f"    p90  : {p90*100:5.1f}%")
            lines.append(f"    p95  : {p95*100:5.1f}%")
            lines.append(f"    p99  : {p99*100:5.1f}%")
            lines.append(f"    max  : {worst*100:5.1f}%")
            
            lines.append("\n  Impact SL simulé (trades qui auraient été stoppés) :")
            sl_stats = {}
            for sl in sl_levels:
                stopped = group[group["mae_pct"] <= sl]
                n_stopped = len(stopped)
                pct_stopped = (n_stopped / n_trades) * 100
                n_saved_winners = len(stopped[stopped["is_winner"] == True])
                sl_stats[sl] = (n_stopped, pct_stopped, n_saved_winners)
                
                saved_str = f"— dont {n_saved_winners} gagnants sauvés" if n_saved_winners > 0 else ""
                lines.append(f"    SL {sl*100:.0f}% : {n_stopped:2d} trades stoppés ({pct_stopped:4.1f}%) {saved_str}")
                
            lines.append("\n  Trades stoppés qui auraient été gagnants (faux positifs) :")
            for sl in sl_levels:
                n_stopped, pct_stopped, n_saved_winners = sl_stats[sl]
                if n_stopped == 0:
                    lines.append(f"    SL {sl*100:.0f}% : 0/0 → N/A")
                    continue
                    
                false_pos_rate = n_saved_winners / n_stopped
                
                if sl == -0.05:
                    advice = "→ éviter" if false_pos_rate > 0.5 else "→ acceptable"
                elif sl == -0.08:
                    advice = "→ borderline" if false_pos_rate > 0.4 else "→ ok"
                elif sl == -0.10:
                    advice = "→ acceptable" if false_pos_rate < 0.5 else "→ déconseillé"
                else:
                    advice = "→ acceptable comme filet catastrophe" if false_pos_rate < 0.5 else "→ dangereux"
                    
                lines.append(f"    SL {sl*100:.0f}% : {n_saved_winners}/{n_stopped} auraient été gagnants {advice}")

        # 2. Consolidated Synthesis
        lines.append("\n================================================================")
        lines.append("SYNTHÈSE CONSOLIDÉE (tous assets × toutes stratégies)")
        lines.append("================================================================")
        
        total_trades = len(df)
        lines.append(f"  Total trades analysés : {total_trades}\n")
        
        recommended_sl = None
        
        for sl in sl_levels:
            stopped = df[df["mae_pct"] <= sl]
            n_stopped = len(stopped)
            pct_stopped = (n_stopped / total_trades) * 100
            n_saved_winners = len(stopped[stopped["is_winner"] == True])
            false_pos_rate = (n_saved_winners / n_stopped) * 100 if n_stopped > 0 else 0
            
            if sl == -0.05:
                tag = "DÉCONSEILLÉ" if false_pos_rate > 40 else "OK"
            elif sl == -0.08:
                tag = "BORDERLINE" if false_pos_rate > 40 else "OK"
            elif sl == -0.10:
                tag = "ACCEPTABLE"
            elif sl == -0.15:
                tag = "FILET SÉCURITÉ"
            else:
                tag = "CATASTROPHE ONLY"
                
            lines.append(f"  SL {sl*100:.0f}% : {pct_stopped:4.1f}% trades stoppés, {false_pos_rate:4.1f}% étaient gagnants → {tag}")
            
            # Recommendation criteria: < 3% trades stopped AND < 50% false positives
            if recommended_sl is None and pct_stopped < 3.0 and false_pos_rate < 50.0:
                recommended_sl = sl

        lines.append(f"\n  Recommandation : SL opérationnel suggéré = {recommended_sl*100:.0f}%" if recommended_sl else "\n  Recommandation : Aucun SL ne satisfait les critères stricts (<3% stopped, <50% false pos).")
        lines.append("  (critère : < 3% de trades stoppés ET < 50% de faux positifs)")
        lines.append("================================================================\n")

        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="MAE Analysis for Stop Loss selection")
    args = parser.parse_args()

    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = yaml.safe_load(f)["strategies"]
    
    all_assets = set()
    for s in ["rsi2", "ibs", "tom"]:
        if s in config:
            all_assets.update(config[s]["universe"])
            
    logger.info(f"Fetching data for {len(all_assets)} assets...")
    loader = YahooLoader()
    caches = {}
    for symbol in sorted(all_assets):
        df = loader.get_daily_candles(symbol, "2013-01-01", OOS_END)
        caches[symbol] = build_cache(to_cache_arrays(df), {"rsi_period":[2], "sma_trend_period":[200], "sma_exit_period":[5]}, dates=df.index.values)

    strats = {
        "rsi2": RSI2MeanReversion(),
        "ibs": IBSMeanReversion(),
        "tom": TurnOfMonth()
    }
    
    analyzer = MAEAnalyzer()
    
    logger.info("Running OOS simulations for all strategy-asset pairs...")
    for s_name in ["rsi2", "ibs", "tom"]:
        if s_name not in config: continue
        strat_obj = strats[s_name]
        params = config[s_name]["params"]
        fee_model_name = config[s_name].get("fee_model", "us_stocks_usd_account")
        
        for symbol in config[s_name]["universe"]:
            analyzer.process_asset(s_name, strat_obj, symbol, caches[symbol], params, fee_model_name)
            
    report = analyzer.generate_report()
    print(report)
    
    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / f"mae_analysis_{datetime.now():%Y%m%d_%H%M%S}.txt"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    logger.info(f"Report saved to {out_path}")

if __name__ == "__main__":
    main()
