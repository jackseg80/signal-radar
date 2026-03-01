"""Script démo — Backtest Donchian sur un symbole via YahooLoader.

Usage:
    python scripts/optimize.py --strategy donchian --symbol AAPL
    python scripts/optimize.py --strategy donchian --symbol AAPL --start 2010-01-01 --end 2024-01-01
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ajouter la racine du projet au path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import yaml
from loguru import logger

from data.base_loader import to_cache_arrays
from data.universe import load_asset_config
from data.yahoo_loader import YahooLoader
from engine.backtest_config import BacktestConfig
from engine.fee_model import FeeModel
from engine.indicator_cache import build_cache
from engine.fast_backtest import run_backtest_from_cache


def main() -> None:
    parser = argparse.ArgumentParser(description="signal-radar backtest démo")
    parser.add_argument("--strategy", default="donchian", help="Nom de la stratégie")
    parser.add_argument("--symbol", default="AAPL", help="Symbole Yahoo Finance")
    parser.add_argument("--start", default="2010-01-01", help="Date début")
    parser.add_argument("--end", default="2025-01-01", help="Date fin")
    parser.add_argument("--asset-config", default=None, help="Chemin du fichier asset config YAML")
    args = parser.parse_args()

    # Charger fee model et sides depuis la config asset si disponible
    fee_model = FeeModel()
    sides = ["long"]

    if args.asset_config:
        ac = load_asset_config(args.asset_config)
        sides = ac.sides
        # Charger fee model depuis fee_models.yaml
        fee_path = Path("config/fee_models.yaml")
        if fee_path.exists():
            with open(fee_path, encoding="utf-8") as f:
                fee_models = yaml.safe_load(f)
            if ac.fee_model in fee_models:
                fee_model = FeeModel(**fee_models[ac.fee_model])
                logger.info("Fee model '{}' chargé", ac.fee_model)
    else:
        # Default US stocks
        fee_path = Path("config/fee_models.yaml")
        if fee_path.exists():
            with open(fee_path, encoding="utf-8") as f:
                fee_models = yaml.safe_load(f)
            if "us_stocks" in fee_models:
                fee_model = FeeModel(**fee_models["us_stocks"])

    # Télécharger les données
    loader = YahooLoader()
    logger.info("Chargement {} ({} → {})...", args.symbol, args.start, args.end)
    df = loader.get_daily_candles(args.symbol, args.start, args.end)
    logger.info("{} candles chargées", len(df))

    # Convertir en arrays numpy
    arrays = to_cache_arrays(df)

    # Charger param_grid
    pg_path = Path("config/param_grids.yaml")
    with open(pg_path, encoding="utf-8") as f:
        all_grids = yaml.safe_load(f)
    grid_values = all_grids.get("signal_donchian", {}).get("default", {})

    # Build cache
    cache = build_cache(arrays, grid_values)
    logger.info("Cache construit — {} candles, {:.0f} jours", cache.n_candles, cache.total_days)

    # Config
    config = BacktestConfig(
        symbol=args.symbol,
        initial_capital=100_000.0,
        slippage_pct=0.0003,
        fee_model=fee_model,
    )

    # Params par défaut
    params = {
        "entry_mode": "donchian",
        "donchian_entry_period": 50,
        "donchian_exit_period": 20,
        "adx_period": 14,
        "adx_threshold": 20,
        "atr_period": 14,
        "trailing_atr_mult": 4.0,
        "exit_mode": "trailing",
        "sl_percent": 10.0,
        "cooldown_candles": 3,
        "sides": sides,
        "position_fraction": 0.3,
    }

    logger.info("Backtest {} avec params: {}", args.symbol, params)

    # Run
    result = run_backtest_from_cache(params, cache, config)
    _, sharpe, net_return_pct, profit_factor, n_trades = result

    # Affichage
    print("\n" + "=" * 60)
    print(f"  {args.symbol} — Donchian Breakout ({args.start} → {args.end})")
    print("=" * 60)
    print(f"  Trades        : {n_trades}")
    print(f"  Sharpe        : {sharpe:.3f}")
    print(f"  Net Return    : {net_return_pct:+.2f}%")
    print(f"  Profit Factor : {profit_factor:.2f}")
    print(f"  Fee Model     : commission=${fee_model.commission_per_trade}, spread={fee_model.spread_pct*100:.2f}%, fx={fee_model.fx_conversion_pct*100:.2f}%")
    print("=" * 60)


if __name__ == "__main__":
    main()
