from pathlib import Path
import sys
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from data.yahoo_loader import YahooLoader
from data.base_loader import to_cache_arrays
from engine.indicator_cache import build_cache
from engine.simulator import simulate
from engine.backtest_config import BacktestConfig
from engine.fee_model import FeeModel
from strategies.rsi2_mean_reversion import RSI2MeanReversion
from scripts.portfolio_backtest import run_theoretical_baseline, run_portfolio_simulation

def main():
    print("--- SANITY CHECK: RSI2 META ---")
    capital = 5000.0
    symbol = "META"
    strat_name = "rsi2"
    
    loader = YahooLoader()
    df = loader.get_daily_candles(symbol, "2013-01-01", "2025-01-01")
    arrays = to_cache_arrays(df)
    
    # Grid pour RSI2
    grid = {"rsi_period": [2], "sma_trend_period": [200], "sma_exit_period": [5]}
    cache = build_cache(arrays, grid, dates=df.index.values)
    
    strat = RSI2MeanReversion()
    params = strat.default_params()
    params["position_fraction"] = 0.20  # Canonique
    
    # 1. PnL via le moteur officiel (simulate)
    bt_config = BacktestConfig(
        symbol=symbol,
        initial_capital=capital,
        slippage_pct=0.0,
        fee_model=FeeModel("us_stocks_usd_account"),
        whole_shares=True
    )
    
    # Trouver l'index correspondant à 2014-01-01 dans le cache
    oos_start_idx = cache.get_idx_from_date("2014-01-01")
    oos_end_idx = cache.get_idx_before_date("2025-01-01")
    
    res_simulate = simulate(strat, cache, params, bt_config, start_idx=oos_start_idx, end_idx=oos_end_idx)
    
    print(f"\n1. ENGINE OFFICIEL (simulate)")
    print(f"   Trades : {res_simulate.n_trades}")
    print(f"   Net PnL: ${res_simulate.final_capital - capital:,.2f}")
    
    # 2. PnL via la boucle run_theoretical_baseline actuelle
    strat_cfg = {"rsi2": {"params": params, "universe": [symbol], "fee_model": "us_stocks_usd_account"}}
    caches = {symbol: cache}
    res_theo = run_theoretical_baseline(capital, strat_cfg, caches)
    
    print(f"\n2. CURRENT THEORETICAL BASELINE")
    print(f"   Trades : {res_theo['n_trades']}")
    print(f"   Net PnL: ${res_theo['net_pnl']:,.2f}")

    # 3. PnL via run_portfolio_simulation (1 seul asset)
    res_port = run_portfolio_simulation(capital, strat_cfg, caches, position_fractions={"rsi2": 0.20})
    print(f"\n3. CURRENT PORTFOLIO SIMULATION")
    print(f"   Trades : {res_port['n_trades']}")
    print(f"   Net PnL: ${res_port['net_pnl']:,.2f}")

if __name__ == "__main__":
    main()
