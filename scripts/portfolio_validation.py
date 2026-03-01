"""Validation portfolio Donchian 50/20 sur 10 US stocks.

Params fixes (pas de WFO), split IS=2010-2020 / OOS=2020-2025.
Equity curve JOURNALIERE (mark-to-market) pour MaxDD correct.
Compare au benchmark buy-and-hold.

Usage:
    python scripts/portfolio_validation.py
    python scripts/portfolio_validation.py --start-oos 2018-01-01
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import yaml
from loguru import logger

from data.yahoo_loader import YahooLoader
from data.base_loader import to_cache_arrays
from engine.backtest_config import BacktestConfig
from engine.fee_model import FeeModel
from engine.indicator_cache import build_cache
from engine.fast_backtest import _simulate_trend_follow


# --- Params fixes (style Turtle) -----------------------------------------

FIXED_PARAMS = {
    "entry_mode": "donchian",
    "donchian_entry_period": 50,
    "donchian_exit_period": 20,
    "adx_period": 14,
    "adx_threshold": 0,
    "atr_period": 14,
    "trailing_atr_mult": 3.0,
    "exit_mode": "trailing",
    "sl_percent": 10.0,
    "position_fraction": 0.2,
    "cooldown_candles": 3,
    "sides": ["long"],
}

CACHE_GRID = {
    "donchian_entry_period": [50],
    "donchian_exit_period": [20],
    "adx_period": [14],
    "atr_period": [14],
}


# --- Metriques ------------------------------------------------------------


def compute_max_drawdown(equity: np.ndarray) -> float:
    """Max drawdown en % du peak sur une equity curve journaliere."""
    peak = equity[0]
    max_dd = 0.0
    for val in equity:
        if val > peak:
            peak = val
        dd = (peak - val) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)
    return max_dd * 100.0


def compute_cagr(initial: float, final: float, years: float) -> float:
    """Compound Annual Growth Rate en %."""
    if initial <= 0 or final <= 0 or years <= 0:
        return 0.0
    return ((final / initial) ** (1.0 / years) - 1.0) * 100.0


def compute_sharpe(trade_returns: list[float], total_days: float) -> float:
    """Sharpe annualise sur les trade-returns."""
    n = len(trade_returns)
    if n < 3:
        return 0.0
    arr = np.array(trade_returns)
    std = float(np.std(arr))
    if std < 1e-10:
        return 0.0
    trades_per_year = n / max(total_days, 1) * 365
    return float(np.mean(arr) / std * np.sqrt(trades_per_year))


def compute_profit_factor(trade_pnls: list[float]) -> float:
    """Profit factor = gross wins / gross losses."""
    wins = sum(p for p in trade_pnls if p > 0)
    losses = abs(sum(p for p in trade_pnls if p <= 0))
    return wins / losses if losses > 0 else float("inf")


# --- Simulation par asset avec equity journaliere -------------------------


def run_asset_with_equity(
    symbol: str,
    df_period: pd.DataFrame,
    config: BacktestConfig,
) -> tuple[list[float], list[float], pd.Series]:
    """Backtest un asset, retourne (pnls, returns, daily_equity Series indexee par date)."""
    params = dict(FIXED_PARAMS)
    arrays = to_cache_arrays(df_period)
    cache = build_cache(arrays, CACHE_GRID)

    daily_eq = np.full(cache.n_candles, config.initial_capital, dtype=np.float64)
    pnls, returns, _ = _simulate_trend_follow(cache, params, config, daily_equity_out=daily_eq)

    eq_series = pd.Series(daily_eq, index=df_period.index, name=symbol)
    return pnls, returns, eq_series


# --- Buy-and-hold benchmark -----------------------------------------------


def buy_and_hold_equity(
    df: pd.DataFrame,
    capital_per_asset: float,
) -> pd.Series:
    """Equity curve buy-and-hold : achete au close du jour 1, hold."""
    prices = df["Adj_Close"].values
    shares = capital_per_asset / prices[0]
    daily_value = shares * prices
    return pd.Series(daily_value, index=df.index)


# --- Affichage -------------------------------------------------------------


def print_block(
    label: str,
    trade_pnls: list[float],
    trade_returns: list[float],
    portfolio_equity: np.ndarray,
    initial_capital: float,
    n_years: float,
    n_trading_days: int,
) -> None:
    """Affiche les metriques d'un bloc IS ou OOS."""
    if not trade_pnls:
        print(f"  {label}: aucun trade")
        return

    final_capital = float(portfolio_equity[-1])
    total_ret = (final_capital - initial_capital) / initial_capital * 100.0
    cagr = compute_cagr(initial_capital, final_capital, n_years)
    max_dd = compute_max_drawdown(portfolio_equity)
    sharpe = compute_sharpe(trade_returns, n_trading_days)
    pf = compute_profit_factor(trade_pnls)
    win_rate = sum(1 for p in trade_pnls if p > 0) / len(trade_pnls)

    print(f"  {label}:")
    print(f"    Trades       : {len(trade_pnls)}")
    print(f"    Total Return : {total_ret:+.2f}%")
    print(f"    CAGR         : {cagr:+.2f}%")
    print(f"    Sharpe       : {sharpe:+.3f}")
    print(f"    Profit Factor: {pf:.2f}")
    print(f"    Win Rate     : {win_rate:.0%}")
    print(f"    Max Drawdown : {max_dd:.1f}%")


def print_benchmark_block(
    label: str,
    bh_equity: np.ndarray,
    initial_capital: float,
    n_years: float,
) -> None:
    """Affiche les metriques buy-and-hold."""
    final = float(bh_equity[-1])
    total_ret = (final - initial_capital) / initial_capital * 100.0
    cagr = compute_cagr(initial_capital, final, n_years)
    max_dd = compute_max_drawdown(bh_equity)

    print(f"  {label}:")
    print(f"    Total Return : {total_ret:+.2f}%")
    print(f"    CAGR         : {cagr:+.2f}%")
    print(f"    Max Drawdown : {max_dd:.1f}%")


def print_per_asset(
    label: str, per_asset: dict, initial_capital: float,
) -> None:
    """Tableau par asset."""
    print(f"\n  {label} -- par asset:")
    header = f"    {'Symbol':<8} {'Trades':>7} {'Return':>8} {'Sharpe':>7} {'PF':>6} {'WinRate':>8}"
    print(header)
    print(f"    {'-'*8} {'-'*7} {'-'*8} {'-'*7} {'-'*6} {'-'*8}")
    for sym, data in sorted(per_asset.items()):
        pnls = data["pnls"]
        rets = data["returns"]
        n = len(pnls)
        ret = sum(pnls) / initial_capital * 100 if pnls else 0.0
        sh = compute_sharpe(rets, data["days"])
        pf = compute_profit_factor(pnls) if pnls else 0.0
        wr = sum(1 for p in pnls if p > 0) / n if n > 0 else 0.0
        pf_str = f"{pf:.2f}" if math.isfinite(pf) else "inf"
        print(f"    {sym:<8} {n:>7} {ret:>+8.2f}% {sh:>+7.3f} {pf_str:>6} {wr:>7.0%}")


# --- Main ------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Portfolio validation Donchian 50/20")
    parser.add_argument("--start-is", default="2010-01-01", help="Debut IS")
    parser.add_argument("--start-oos", default="2020-01-01", help="Debut OOS = fin IS")
    parser.add_argument("--end-oos", default="2025-01-01", help="Fin OOS")
    parser.add_argument("--symbol", action="append", default=None)
    args = parser.parse_args()

    with open("config/assets_us.yaml", encoding="utf-8") as f:
        asset_cfg = yaml.safe_load(f)
    with open("config/fee_models.yaml", encoding="utf-8") as f:
        fee_models_cfg = yaml.safe_load(f)

    symbols = args.symbol if args.symbol else asset_cfg["symbols"]
    fee_model = FeeModel(**fee_models_cfg[asset_cfg["fee_model"]])

    capital_per_asset = 100_000.0
    config = BacktestConfig(
        symbol="PORTFOLIO",
        initial_capital=capital_per_asset,
        slippage_pct=0.0003,
        fee_model=fee_model,
    )

    loader = YahooLoader()

    start_is = args.start_is
    start_oos = args.start_oos
    end_oos = args.end_oos

    # --- Collect per-asset results ---
    per_asset_is: dict = {}
    per_asset_oos: dict = {}
    is_equity_series: dict[str, pd.Series] = {}
    oos_equity_series: dict[str, pd.Series] = {}
    is_bh_series: dict[str, pd.Series] = {}
    oos_bh_series: dict[str, pd.Series] = {}

    for sym in symbols:
        try:
            df = loader.get_daily_candles(sym, start_is, end_oos)
            df_is = df.loc[df.index < start_oos]
            df_oos = df.loc[df.index >= start_oos]

            if len(df_is) < 100 or len(df_oos) < 20:
                logger.warning("{}: donnees insuffisantes, skip", sym)
                continue

            # Backtest IS
            is_pnls, is_rets, is_eq = run_asset_with_equity(sym, df_is, config)
            # Backtest OOS
            oos_pnls, oos_rets, oos_eq = run_asset_with_equity(sym, df_oos, config)

            logger.info(
                "{:6s}: IS  {} trades | OOS  {} trades",
                sym, len(is_pnls), len(oos_pnls),
            )

            per_asset_is[sym] = {"pnls": is_pnls, "returns": is_rets, "days": len(df_is)}
            per_asset_oos[sym] = {"pnls": oos_pnls, "returns": oos_rets, "days": len(df_oos)}
            is_equity_series[sym] = is_eq
            oos_equity_series[sym] = oos_eq

            # Buy-and-hold
            is_bh_series[sym] = buy_and_hold_equity(df_is, capital_per_asset)
            oos_bh_series[sym] = buy_and_hold_equity(df_oos, capital_per_asset)

        except Exception as exc:
            logger.error("{}: erreur -- {}", sym, exc)

    n_assets = len(per_asset_is)
    if n_assets == 0:
        print("Aucun asset traite.")
        return

    total_capital = capital_per_asset * n_assets

    # --- Build portfolio equity curves (jour par jour) ---
    is_eq_df = pd.DataFrame(is_equity_series).sort_index()
    oos_eq_df = pd.DataFrame(oos_equity_series).sort_index()
    is_eq_df = is_eq_df.ffill().bfill()
    oos_eq_df = oos_eq_df.ffill().bfill()

    portfolio_is_equity = is_eq_df.sum(axis=1).values
    portfolio_oos_equity = oos_eq_df.sum(axis=1).values

    # Buy-and-hold portfolio equity
    is_bh_df = pd.DataFrame(is_bh_series).sort_index().ffill().bfill()
    oos_bh_df = pd.DataFrame(oos_bh_series).sort_index().ffill().bfill()
    bh_is_equity = is_bh_df.sum(axis=1).values
    bh_oos_equity = oos_bh_df.sum(axis=1).values

    # Pooled trades
    all_is_pnls = [p for d in per_asset_is.values() for p in d["pnls"]]
    all_is_returns = [r for d in per_asset_is.values() for r in d["returns"]]
    all_oos_pnls = [p for d in per_asset_oos.values() for p in d["pnls"]]
    all_oos_returns = [r for d in per_asset_oos.values() for r in d["returns"]]

    # Periods
    is_trading_days = len(is_eq_df)
    oos_trading_days = len(oos_eq_df)
    is_years = is_trading_days / 252.0
    oos_years = oos_trading_days / 252.0

    # --- Header ---
    print(f"\n  Params : Donchian {FIXED_PARAMS['donchian_entry_period']}/{FIXED_PARAMS['donchian_exit_period']}")
    print(f"           trailing_atr_mult={FIXED_PARAMS['trailing_atr_mult']}, sl={FIXED_PARAMS['sl_percent']}%")
    print(f"           position_fraction={FIXED_PARAMS['position_fraction']}, sides={FIXED_PARAMS['sides']}")
    print(f"  IS     : {start_is} -> {start_oos} ({is_trading_days} jours, {is_years:.1f} ans)")
    print(f"  OOS    : {start_oos} -> {end_oos} ({oos_trading_days} jours, {oos_years:.1f} ans)")
    print(f"  Assets : {', '.join(sorted(per_asset_is.keys()))} ({n_assets})")
    print(f"  Capital: ${capital_per_asset:,.0f}/asset = ${total_capital:,.0f} total")

    # ================================================================
    # 1. PORTFOLIO DONCHIAN (equity journaliere, MaxDD correct)
    # ================================================================
    print("\n" + "=" * 65)
    print("  1. VALIDATION PORTFOLIO -- Donchian 50/20 (Equity Journaliere)")
    print("=" * 65)

    print_block(
        f"PORTFOLIO IS  ({start_is} -> {start_oos})",
        all_is_pnls, all_is_returns,
        portfolio_is_equity, total_capital,
        is_years, is_trading_days,
    )
    print()
    print_block(
        f"PORTFOLIO OOS ({start_oos} -> {end_oos})",
        all_oos_pnls, all_oos_returns,
        portfolio_oos_equity, total_capital,
        oos_years, oos_trading_days,
    )

    # ================================================================
    # 2. BENCHMARK BUY-AND-HOLD
    # ================================================================
    print("\n" + "=" * 65)
    print("  2. BENCHMARK BUY-AND-HOLD (equal weight)")
    print("=" * 65)

    print_benchmark_block(
        f"BUY-AND-HOLD IS  ({start_is} -> {start_oos})",
        bh_is_equity, total_capital, is_years,
    )
    print()
    print_benchmark_block(
        f"BUY-AND-HOLD OOS ({start_oos} -> {end_oos})",
        bh_oos_equity, total_capital, oos_years,
    )

    # Comparison
    donchian_is_ret = (float(portfolio_is_equity[-1]) - total_capital) / total_capital * 100
    donchian_oos_ret = (float(portfolio_oos_equity[-1]) - total_capital) / total_capital * 100
    bh_is_ret = (float(bh_is_equity[-1]) - total_capital) / total_capital * 100
    bh_oos_ret = (float(bh_oos_equity[-1]) - total_capital) / total_capital * 100

    print(f"\n  Donchian vs Buy-and-Hold:")
    print(f"    IS  : Donchian {donchian_is_ret:+.2f}%  vs  B&H {bh_is_ret:+.2f}%  -> {'DONCHIAN' if donchian_is_ret > bh_is_ret else 'B&H'}")
    print(f"    OOS : Donchian {donchian_oos_ret:+.2f}%  vs  B&H {bh_oos_ret:+.2f}%  -> {'DONCHIAN' if donchian_oos_ret > bh_oos_ret else 'B&H'}")

    donchian_oos_dd = compute_max_drawdown(portfolio_oos_equity)
    bh_oos_dd = compute_max_drawdown(bh_oos_equity)
    print(f"    MaxDD OOS : Donchian {donchian_oos_dd:.1f}%  vs  B&H {bh_oos_dd:.1f}%")

    # ================================================================
    # 3. SANS NVDA (robustesse)
    # ================================================================
    if "NVDA" in per_asset_oos:
        print("\n" + "=" * 65)
        print("  3. ROBUSTESSE -- OOS sans NVDA")
        print("=" * 65)

        oos_pnls_no_nvda = [
            p for sym, d in per_asset_oos.items() if sym != "NVDA" for p in d["pnls"]
        ]
        oos_rets_no_nvda = [
            r for sym, d in per_asset_oos.items() if sym != "NVDA" for r in d["returns"]
        ]

        # Portfolio equity without NVDA
        oos_eq_no_nvda = pd.DataFrame({
            s: eq for s, eq in oos_equity_series.items() if s != "NVDA"
        }).sort_index().ffill().bfill()
        portfolio_oos_no_nvda = oos_eq_no_nvda.sum(axis=1).values
        capital_no_nvda = capital_per_asset * (n_assets - 1)

        print_block(
            f"PORTFOLIO OOS sans NVDA ({n_assets - 1} assets)",
            oos_pnls_no_nvda, oos_rets_no_nvda,
            portfolio_oos_no_nvda, capital_no_nvda,
            oos_years, oos_trading_days,
        )

        # Also buy-and-hold without NVDA
        oos_bh_no_nvda = pd.DataFrame({
            s: eq for s, eq in oos_bh_series.items() if s != "NVDA"
        }).sort_index().ffill().bfill()
        bh_oos_no_nvda = oos_bh_no_nvda.sum(axis=1).values

        print()
        print_benchmark_block(
            f"BUY-AND-HOLD OOS sans NVDA",
            bh_oos_no_nvda, capital_no_nvda, oos_years,
        )

        d_ret = (float(portfolio_oos_no_nvda[-1]) - capital_no_nvda) / capital_no_nvda * 100
        b_ret = (float(bh_oos_no_nvda[-1]) - capital_no_nvda) / capital_no_nvda * 100
        print(f"\n  Sans NVDA : Donchian {d_ret:+.2f}%  vs  B&H {b_ret:+.2f}%  -> {'DONCHIAN' if d_ret > b_ret else 'B&H'}")

    # ================================================================
    # 4. DETAIL PAR ASSET
    # ================================================================
    print("\n" + "=" * 65)
    print("  4. DETAIL PAR ASSET")
    print("=" * 65)
    print_per_asset("IS", per_asset_is, capital_per_asset)
    print_per_asset("OOS", per_asset_oos, capital_per_asset)

    # ================================================================
    # VERDICT
    # ================================================================
    print("\n" + "=" * 65)
    print("  VERDICT")
    print("=" * 65)

    n_pos = sum(1 for d in per_asset_oos.values() if sum(d["pnls"]) > 0)
    print(f"  Assets OOS profitables    : {n_pos}/{n_assets}")
    print(f"  Donchian OOS Total Return : {donchian_oos_ret:+.2f}%")
    print(f"  Donchian OOS CAGR         : {compute_cagr(total_capital, float(portfolio_oos_equity[-1]), oos_years):+.2f}%")
    print(f"  Donchian OOS MaxDD        : {donchian_oos_dd:.1f}%")
    print(f"  Buy-and-Hold OOS Return   : {bh_oos_ret:+.2f}%")
    print(f"  Buy-and-Hold OOS CAGR     : {compute_cagr(total_capital, float(bh_oos_equity[-1]), oos_years):+.2f}%")
    print(f"  Buy-and-Hold OOS MaxDD    : {bh_oos_dd:.1f}%")

    if "NVDA" in per_asset_oos:
        d_ret_nn = (float(portfolio_oos_no_nvda[-1]) - capital_no_nvda) / capital_no_nvda * 100
        print(f"  Donchian OOS sans NVDA    : {d_ret_nn:+.2f}%")

    print("=" * 65)


if __name__ == "__main__":
    main()
