"""Investigation IBS Forex -- pourquoi WR 37-48% avec PF 2.5-3.8 ?

Analyse en profondeur des trades IBS sur forex majors pour comprendre
le pattern inhabituel (low WR + high PF = profil momentum, pas MR).

6 analyses :
1. Distribution des returns (skew, kurtosis, percentiles)
2. Concentration du profit (top N trades)
3. Duree des trades (correlation duree/return)
4. Analyse temporelle (PF par annee)
5. Direction vs tendance (SMA200 slope, distance)
6. Comparaison stocks vs forex
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

# -- Path setup --
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.base_loader import to_cache_arrays
from data.yahoo_loader import YahooLoader
from engine.backtest_config import BacktestConfig
from engine.fee_model import FEE_MODEL_FOREX_SAXO, FEE_MODEL_US_STOCKS_USD
from engine.indicator_cache import build_cache
from engine.simulator import simulate
from engine.types import BacktestResult, TradeResult
from strategies.ibs_mean_reversion import IBSMeanReversion
from validation.pipeline import _merge_grid_with_defaults

# -- Config --
FOREX_PAIRS = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X",
    "AUDUSD=X", "USDCAD=X", "NZDUSD=X",
]
STOCK_COMPARE = "NVDA"

OOS_START = "2014-01-01"
OOS_END = "2025-01-01"

FOREX_CAPITAL = 100_000.0
STOCK_CAPITAL = 10_000.0


def run_backtest(
    symbol: str,
    fee_model,
    capital: float,
    whole_shares: bool,
) -> tuple[BacktestResult, pd.DataFrame, dict]:
    """Run IBS backtest and return (result, df, cache_meta).

    cache_meta contains the cache and indices for further analysis.
    """
    loader = YahooLoader()
    strategy = IBSMeanReversion()

    df = loader.get_daily_candles(symbol, "2005-01-01", OOS_END)
    arrays = to_cache_arrays(df)
    dates = df.index.values

    cache_grid = _merge_grid_with_defaults(strategy)
    cache = build_cache(arrays, cache_grid, dates=dates)

    oos_start_idx = int(df.index.searchsorted(pd.Timestamp(OOS_START)))
    oos_end_idx = len(df)

    warmup = strategy.warmup(strategy.default_params())
    if oos_start_idx < warmup:
        oos_start_idx = warmup

    bt_config = BacktestConfig(
        symbol=symbol,
        initial_capital=capital,
        slippage_pct=0.0003,
        fee_model=fee_model,
        whole_shares=whole_shares,
    )

    result = simulate(
        strategy, cache, strategy.default_params(), bt_config,
        start_idx=oos_start_idx, end_idx=oos_end_idx,
    )

    cache_meta = {
        "cache": cache,
        "oos_start_idx": oos_start_idx,
        "oos_end_idx": oos_end_idx,
        "dates": dates,
        "df": df,
    }

    return result, df, cache_meta


def print_header(title: str) -> None:
    """Print formatted section header."""
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def analyze_distribution(symbol: str, result: BacktestResult) -> dict:
    """Analyse 1 -- Distribution des returns."""
    returns = np.array(result.returns) * 100  # en %
    pnls = np.array(result.pnls)

    wins = returns[returns > 0]
    losses = returns[returns <= 0]

    avg_win = float(wins.mean()) if len(wins) > 0 else 0.0
    avg_loss = float(losses.mean()) if len(losses) > 0 else 0.0
    wl_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else float("inf")

    print(f"\n  {symbol} ({result.n_trades} trades, "
          f"WR {result.win_rate:.0%}, PF {result.profit_factor:.2f})")
    print()
    print("  Returns distribution (%):")
    print(f"    Mean:     {returns.mean():+.4f}%")
    print(f"    Median:   {np.median(returns):+.4f}%")
    print(f"    Std:      {returns.std():.4f}%")
    print(f"    Skew:     {float(sp_stats.skew(returns)):+.2f}")
    print(f"    Kurtosis: {float(sp_stats.kurtosis(returns)):.2f}")
    print()
    print("  Percentiles:")
    for p in [1, 5, 25, 50, 75, 95, 99]:
        print(f"    P{p:<3d} {np.percentile(returns, p):+.4f}%")
    print(f"    Max: {returns.max():+.4f}%")
    print(f"    Min: {returns.min():+.4f}%")
    print()
    print("  Win/Loss profile:")
    print(f"    Avg Win:       {avg_win:+.4f}%")
    print(f"    Avg Loss:      {avg_loss:+.4f}%")
    print(f"    Win/Loss ratio: {wl_ratio:.2f}")

    return {
        "mean": float(returns.mean()),
        "median": float(np.median(returns)),
        "skew": float(sp_stats.skew(returns)),
        "kurtosis": float(sp_stats.kurtosis(returns)),
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "wl_ratio": wl_ratio,
    }


def analyze_concentration(symbol: str, result: BacktestResult) -> None:
    """Analyse 2 -- Concentration du profit."""
    pnls = np.array(result.pnls)
    returns = np.array(result.returns)
    total_profit = pnls.sum()

    # Sort by PnL descending
    sorted_idx = np.argsort(pnls)[::-1]
    sorted_pnls = pnls[sorted_idx]
    sorted_rets = returns[sorted_idx] * 100

    print(f"\n  {symbol} -- Profit concentration")
    print()

    # Top N trades as % of total profit
    for n in [5, 10, 20, 50]:
        if n > len(pnls):
            continue
        top_n_profit = sorted_pnls[:n].sum()
        pct = top_n_profit / total_profit * 100 if total_profit != 0 else 0
        print(f"    Top {n:>2d} trades: {pct:6.1f}% du profit total "
              f"(${top_n_profit:,.0f} / ${total_profit:,.0f})")

    print()
    print("  Top 10 trades (% return):")
    for rank in range(min(10, len(sorted_rets))):
        print(f"    #{rank+1:>2d}: {sorted_rets[rank]:+.4f}% "
              f"(${sorted_pnls[rank]:+,.0f})")

    # PF without top N
    print()
    print("  PF sans les meilleurs trades:")
    for n in [5, 10, 20]:
        if n >= len(pnls):
            continue
        remaining = pnls[sorted_idx[n:]]
        gp = remaining[remaining > 0].sum()
        gl = abs(remaining[remaining <= 0].sum())
        pf_remaining = gp / gl if gl > 0 else float("inf")
        wr_remaining = (remaining > 0).sum() / len(remaining)
        print(f"    Sans top {n:>2d}: PF {pf_remaining:.2f}, "
              f"WR {wr_remaining:.0%} ({len(remaining)} trades)")


def analyze_duration(symbol: str, result: BacktestResult) -> None:
    """Analyse 3 -- Duree des trades."""
    durations = np.array([t.holding_days for t in result.trades])
    returns = np.array(result.returns) * 100
    pnls = np.array(result.pnls)

    print(f"\n  {symbol} -- Trade duration (trading days)")
    print()
    print(f"    Mean:   {durations.mean():.1f} days")
    print(f"    Median: {np.median(durations):.1f} days")
    print(f"    Min:    {durations.min()} day(s)")
    print(f"    Max:    {durations.max()} days")
    print(f"    P95:    {np.percentile(durations, 95):.0f} days")

    print()
    print("  Duration vs return:")

    # Buckets
    buckets = [
        ("Short (1d)", durations == 1),
        ("Medium (2-3d)", (durations >= 2) & (durations <= 3)),
        ("Long (4-7d)", (durations >= 4) & (durations <= 7)),
        ("Very long (8+d)", durations >= 8),
    ]
    for label, mask in buckets:
        n = mask.sum()
        if n == 0:
            continue
        mean_ret = returns[mask].mean()
        mean_pnl = pnls[mask].mean()
        wr = (pnls[mask] > 0).sum() / n
        print(f"    {label:<20s}: N={n:>3d}, mean ret {mean_ret:+.4f}%, "
              f"WR {wr:.0%}, avg PnL ${mean_pnl:+,.0f}")

    # Correlation duration vs return
    if len(durations) > 2:
        corr, pval = sp_stats.pearsonr(durations, returns)
        print(f"\n    Correlation duration/return: r={corr:.3f}, p={pval:.4f}")


def analyze_temporal(
    symbol: str, result: BacktestResult, cache_meta: dict,
) -> None:
    """Analyse 4 -- Analyse temporelle par annee."""
    dates = cache_meta["dates"]
    trades = result.trades

    print(f"\n  {symbol} -- Returns by year")
    print()
    print(f"    {'Year':<6s} {'N':>4s} {'WR':>6s} {'PF':>7s} "
          f"{'Avg Ret':>10s} {'Total PnL':>12s}")
    print("    " + "-" * 52)

    # Group trades by year using entry_candle -> date
    years: dict[int, list[TradeResult]] = {}
    for t in trades:
        entry_date = pd.Timestamp(dates[t.entry_candle])
        year = entry_date.year
        if year not in years:
            years[year] = []
        years[year].append(t)

    for year in sorted(years.keys()):
        year_trades = years[year]
        n = len(year_trades)
        wr = sum(1 for t in year_trades if t.pnl > 0) / n
        gp = sum(t.pnl for t in year_trades if t.pnl > 0)
        gl = abs(sum(t.pnl for t in year_trades if t.pnl <= 0))
        pf = gp / gl if gl > 0 else float("inf")
        avg_ret = np.mean([t.return_pct for t in year_trades]) * 100
        total_pnl = sum(t.pnl for t in year_trades)
        print(f"    {year:<6d} {n:>4d} {wr:>5.0%} {pf:>7.2f} "
              f"{avg_ret:>+9.4f}% ${total_pnl:>+10,.0f}")

    # Count years with PF < 1
    pf_below_1 = 0
    for year in sorted(years.keys()):
        year_trades = years[year]
        gp = sum(t.pnl for t in year_trades if t.pnl > 0)
        gl = abs(sum(t.pnl for t in year_trades if t.pnl <= 0))
        pf = gp / gl if gl > 0 else float("inf")
        if pf < 1.0:
            pf_below_1 += 1
    n_years = len(years)
    print(f"\n    Annees PF < 1.0: {pf_below_1}/{n_years}")


def analyze_trend(
    symbol: str, result: BacktestResult, cache_meta: dict,
) -> None:
    """Analyse 5 -- Direction du trade vs tendance macro."""
    cache = cache_meta["cache"]
    dates = cache_meta["dates"]
    trades = result.trades

    # SMA200
    sma200 = cache.sma_by_period.get(200)
    if sma200 is None:
        print(f"\n  {symbol} -- SMA200 non disponible, skip trend analysis")
        return

    closes = cache.closes

    print(f"\n  {symbol} -- Trend analysis (SMA200)")
    print()

    # For each trade, compute SMA200 slope and distance at entry
    slopes = []
    distances = []
    rets_by_slope = {"rising": [], "flat": [], "falling": []}

    for t in trades:
        entry_i = t.entry_candle
        # SMA200 slope over last 20 days (annualized % change)
        if entry_i >= 20:
            sma_now = sma200[entry_i - 1]  # signal on [i-1]
            sma_20ago = sma200[entry_i - 21]
            if sma_20ago > 0 and not np.isnan(sma_now) and not np.isnan(sma_20ago):
                slope_pct = (sma_now - sma_20ago) / sma_20ago * 100
                slopes.append(slope_pct)

                # Distance close to SMA200
                close_prev = closes[entry_i - 1]
                dist_pct = (close_prev - sma_now) / sma_now * 100
                distances.append(dist_pct)

                # Categorize
                if slope_pct > 0.5:
                    rets_by_slope["rising"].append(t.return_pct * 100)
                elif slope_pct < -0.5:
                    rets_by_slope["falling"].append(t.return_pct * 100)
                else:
                    rets_by_slope["flat"].append(t.return_pct * 100)

    slopes = np.array(slopes)
    distances = np.array(distances)

    print("  SMA200 slope at entry (20d change %):")
    print(f"    Mean slope:   {slopes.mean():+.3f}%")
    print(f"    Median slope: {np.median(slopes):+.3f}%")
    print()

    print("  Returns by SMA200 slope:")
    for label, rets in rets_by_slope.items():
        if len(rets) == 0:
            continue
        rets_arr = np.array(rets)
        n = len(rets_arr)
        mean = rets_arr.mean()
        wr = (rets_arr > 0).sum() / n
        gp = rets_arr[rets_arr > 0].sum()
        gl = abs(rets_arr[rets_arr <= 0].sum())
        pf = gp / gl if gl > 0 else float("inf")
        print(f"    {label:<10s}: N={n:>3d}, mean ret {mean:+.4f}%, "
              f"WR {wr:.0%}, PF {pf:.2f}")

    print()
    print("  Distance to SMA200 at entry:")
    buckets = [
        ("Close (< 2%)", distances < 2),
        ("Mid (2-5%)", (distances >= 2) & (distances < 5)),
        ("Far (> 5%)", distances >= 5),
    ]

    # We need to align distances with returns -- only trades that had valid slope
    valid_trades = []
    for t in trades:
        entry_i = t.entry_candle
        if entry_i >= 20:
            sma_now = sma200[entry_i - 1]
            sma_20ago = sma200[entry_i - 21]
            if sma_20ago > 0 and not np.isnan(sma_now) and not np.isnan(sma_20ago):
                valid_trades.append(t)

    valid_rets = np.array([t.return_pct * 100 for t in valid_trades])

    for label, mask in buckets:
        n = mask.sum()
        if n == 0:
            continue
        bucket_rets = valid_rets[mask]
        mean = bucket_rets.mean()
        wr = (bucket_rets > 0).sum() / n
        print(f"    {label:<15s}: N={n:>3d}, mean ret {mean:+.4f}%, WR {wr:.0%}")

    # Correlation slope vs return
    if len(slopes) > 2:
        corr, pval = sp_stats.pearsonr(slopes, valid_rets)
        print(f"\n    Correlation SMA200_slope/return: r={corr:.3f}, p={pval:.4f}")


def analyze_exit_reasons(symbol: str, result: BacktestResult) -> None:
    """Bonus -- Repartition des raisons de sortie."""
    reasons: dict[str, list[TradeResult]] = {}
    for t in result.trades:
        if t.exit_reason not in reasons:
            reasons[t.exit_reason] = []
        reasons[t.exit_reason].append(t)

    print(f"\n  {symbol} -- Exit reasons")
    print()
    print(f"    {'Reason':<20s} {'N':>4s} {'WR':>6s} {'PF':>7s} "
          f"{'Avg Ret':>10s} {'Avg Days':>9s}")
    print("    " + "-" * 60)

    for reason in sorted(reasons.keys()):
        trades = reasons[reason]
        n = len(trades)
        wr = sum(1 for t in trades if t.pnl > 0) / n
        gp = sum(t.pnl for t in trades if t.pnl > 0)
        gl = abs(sum(t.pnl for t in trades if t.pnl <= 0))
        pf = gp / gl if gl > 0 else float("inf")
        avg_ret = np.mean([t.return_pct for t in trades]) * 100
        avg_days = np.mean([t.holding_days for t in trades])
        print(f"    {reason:<20s} {n:>4d} {wr:>5.0%} {pf:>7.2f} "
              f"{avg_ret:>+9.4f}% {avg_days:>8.1f}d")


def main() -> None:
    """Run all investigations."""
    print_header("IBS Forex -- Investigation approfondie")
    print("  OOS: 2014-2025, Capital: $100k fractional, Fee: Forex Saxo")
    print("  Strategie: IBS MR (entry IBS<0.2 + close>SMA200, "
          "exit IBS>0.8 ou close>high[j-1])")

    # ================================================================
    # Run all forex backtests
    # ================================================================
    forex_results: dict[str, tuple[BacktestResult, pd.DataFrame, dict]] = {}

    print_header("Chargement et backtest des 7 paires forex")
    for symbol in FOREX_PAIRS:
        print(f"  {symbol}...", end=" ", flush=True)
        try:
            res, df, meta = run_backtest(
                symbol, FEE_MODEL_FOREX_SAXO, FOREX_CAPITAL, whole_shares=False,
            )
            forex_results[symbol] = (res, df, meta)
            print(f"{res.n_trades} trades, WR {res.win_rate:.0%}, "
                  f"PF {res.profit_factor:.2f}")
        except Exception as e:
            print(f"ERREUR: {e}")

    # Stock comparison
    print(f"\n  {STOCK_COMPARE} (stock comparison)...", end=" ", flush=True)
    stock_res, stock_df, stock_meta = run_backtest(
        STOCK_COMPARE, FEE_MODEL_US_STOCKS_USD, STOCK_CAPITAL, whole_shares=True,
    )
    print(f"{stock_res.n_trades} trades, WR {stock_res.win_rate:.0%}, "
          f"PF {stock_res.profit_factor:.2f}")

    # ================================================================
    # ANALYSE 1 -- Distribution des returns
    # ================================================================
    print_header("Analyse 1 -- Distribution des returns")
    forex_stats: dict[str, dict] = {}
    for symbol in FOREX_PAIRS:
        if symbol not in forex_results:
            continue
        res, _, _ = forex_results[symbol]
        forex_stats[symbol] = analyze_distribution(symbol, res)

    # ================================================================
    # ANALYSE 2 -- Concentration du profit
    # ================================================================
    print_header("Analyse 2 -- Concentration du profit")
    for symbol in FOREX_PAIRS:
        if symbol not in forex_results:
            continue
        res, _, _ = forex_results[symbol]
        analyze_concentration(symbol, res)

    # ================================================================
    # ANALYSE 3 -- Duree des trades
    # ================================================================
    print_header("Analyse 3 -- Duree des trades")
    for symbol in FOREX_PAIRS:
        if symbol not in forex_results:
            continue
        res, _, _ = forex_results[symbol]
        analyze_duration(symbol, res)

    # ================================================================
    # ANALYSE 4 -- Analyse temporelle
    # ================================================================
    print_header("Analyse 4 -- Analyse temporelle (par annee)")
    for symbol in FOREX_PAIRS:
        if symbol not in forex_results:
            continue
        res, _, meta = forex_results[symbol]
        analyze_temporal(symbol, res, meta)

    # ================================================================
    # ANALYSE 5 -- Direction vs tendance
    # ================================================================
    print_header("Analyse 5 -- Direction du trade vs tendance macro")
    for symbol in FOREX_PAIRS:
        if symbol not in forex_results:
            continue
        res, _, meta = forex_results[symbol]
        analyze_trend(symbol, res, meta)

    # ================================================================
    # BONUS -- Exit reasons
    # ================================================================
    print_header("Bonus -- Raisons de sortie")
    for symbol in FOREX_PAIRS:
        if symbol not in forex_results:
            continue
        res, _, _ = forex_results[symbol]
        analyze_exit_reasons(symbol, res)

    # ================================================================
    # ANALYSE 6 -- Comparaison forex vs stock
    # ================================================================
    print_header(f"Analyse 6 -- Comparaison Forex vs {STOCK_COMPARE}")

    # Pick best forex pair for comparison
    best_pair = max(
        forex_results.keys(),
        key=lambda s: forex_results[s][0].profit_factor,
    )
    best_res = forex_results[best_pair][0]

    stock_returns = np.array(stock_res.returns) * 100
    forex_returns = np.array(best_res.returns) * 100

    stock_wins = stock_returns[stock_returns > 0]
    stock_losses = stock_returns[stock_returns <= 0]
    forex_wins = forex_returns[forex_returns > 0]
    forex_losses = forex_returns[forex_returns <= 0]

    stock_avg_win = float(stock_wins.mean()) if len(stock_wins) > 0 else 0.0
    stock_avg_loss = float(stock_losses.mean()) if len(stock_losses) > 0 else 0.0
    forex_avg_win = float(forex_wins.mean()) if len(forex_wins) > 0 else 0.0
    forex_avg_loss = float(forex_losses.mean()) if len(forex_losses) > 0 else 0.0

    stock_wl = abs(stock_avg_win / stock_avg_loss) if stock_avg_loss != 0 else float("inf")
    forex_wl = abs(forex_avg_win / forex_avg_loss) if forex_avg_loss != 0 else float("inf")

    # Top 10 concentration
    stock_pnls = np.array(stock_res.pnls)
    forex_pnls = np.array(best_res.pnls)
    stock_sorted = np.sort(stock_pnls)[::-1]
    forex_sorted = np.sort(forex_pnls)[::-1]
    stock_top10_pct = stock_sorted[:10].sum() / stock_pnls.sum() * 100 if stock_pnls.sum() != 0 else 0
    forex_top10_pct = forex_sorted[:10].sum() / forex_pnls.sum() * 100 if forex_pnls.sum() != 0 else 0

    print()
    print(f"  {'':20s} {best_pair:>12s} {STOCK_COMPARE:>12s}")
    print("  " + "-" * 46)
    print(f"  {'Trades':<20s} {best_res.n_trades:>12d} {stock_res.n_trades:>12d}")
    print(f"  {'WR':<20s} {best_res.win_rate:>11.0%} {stock_res.win_rate:>11.0%}")
    print(f"  {'PF':<20s} {best_res.profit_factor:>12.2f} {stock_res.profit_factor:>12.2f}")
    print(f"  {'Avg Win':<20s} {forex_avg_win:>+11.4f}% {stock_avg_win:>+11.4f}%")
    print(f"  {'Avg Loss':<20s} {forex_avg_loss:>+11.4f}% {stock_avg_loss:>+11.4f}%")
    print(f"  {'Win/Loss ratio':<20s} {forex_wl:>12.2f} {stock_wl:>12.2f}")
    print(f"  {'Skew':<20s} {float(sp_stats.skew(forex_returns)):>+12.2f} "
          f"{float(sp_stats.skew(stock_returns)):>+12.2f}")
    print(f"  {'Kurtosis':<20s} {float(sp_stats.kurtosis(forex_returns)):>12.2f} "
          f"{float(sp_stats.kurtosis(stock_returns)):>12.2f}")
    print(f"  {'Top 10 % profit':<20s} {forex_top10_pct:>11.1f}% {stock_top10_pct:>11.1f}%")
    print(f"  {'Median return':<20s} {np.median(forex_returns):>+11.4f}% "
          f"{np.median(stock_returns):>+11.4f}%")

    # Duration comparison
    forex_dur = np.array([t.holding_days for t in best_res.trades])
    stock_dur = np.array([t.holding_days for t in stock_res.trades])
    print(f"  {'Avg duration':<20s} {forex_dur.mean():>11.1f}d {stock_dur.mean():>11.1f}d")

    # ================================================================
    # SYNTHESE
    # ================================================================
    print_header("SYNTHESE")

    # Compute aggregate stats across all forex pairs
    all_returns = []
    all_skews = []
    all_wl_ratios = []
    for symbol in FOREX_PAIRS:
        if symbol not in forex_stats:
            continue
        s = forex_stats[symbol]
        all_skews.append(s["skew"])
        all_wl_ratios.append(s["wl_ratio"])
        res = forex_results[symbol][0]
        all_returns.extend([t.return_pct for t in res.trades])

    avg_skew = np.mean(all_skews)
    avg_wl = np.mean(all_wl_ratios)

    # Check if profit is concentrated
    all_pnls = []
    for symbol in FOREX_PAIRS:
        if symbol not in forex_results:
            continue
        all_pnls.extend(forex_results[symbol][0].pnls)
    all_pnls = np.array(all_pnls)
    total = all_pnls.sum()
    sorted_all = np.sort(all_pnls)[::-1]
    top20_pct = sorted_all[:20].sum() / total * 100 if total != 0 else 0

    # Check temporal stability
    years_below_1 = 0
    total_years = 0
    for symbol in FOREX_PAIRS:
        if symbol not in forex_results:
            continue
        res, _, meta = forex_results[symbol]
        dates = meta["dates"]
        by_year: dict[int, list] = {}
        for t in res.trades:
            y = pd.Timestamp(dates[t.entry_candle]).year
            if y not in by_year:
                by_year[y] = []
            by_year[y].append(t.pnl)
        for y, pnls_list in by_year.items():
            pnls_arr = np.array(pnls_list)
            gp = pnls_arr[pnls_arr > 0].sum()
            gl = abs(pnls_arr[pnls_arr <= 0].sum())
            pf = gp / gl if gl > 0 else float("inf")
            total_years += 1
            if pf < 1.0:
                years_below_1 += 1

    pct_years_ok = (total_years - years_below_1) / total_years * 100 if total_years > 0 else 0

    print()
    print("  Diagnostics :")
    print(f"    Skew moyen:             {avg_skew:+.2f} "
          f"{'(positif = queue droite = momentum)' if avg_skew > 0.5 else '(neutre = MR)'}")
    print(f"    Win/Loss ratio moyen:   {avg_wl:.2f} "
          f"{'(gains >> pertes = momentum)' if avg_wl > 2.0 else '(equilibre = MR)'}")
    print(f"    Top 20 trades:          {top20_pct:.1f}% du profit total "
          f"{'(concentre = fragile)' if top20_pct > 50 else '(distribue = robuste)'}")
    print(f"    Annees PF >= 1.0:       {pct_years_ok:.0f}% ({total_years - years_below_1}/{total_years})")
    print(f"    Median return:          {np.median(np.array(all_returns) * 100):+.4f}% "
          f"{'(negatif = majorite des trades perdent)' if np.median(all_returns) < 0 else ''}")

    # Verdict
    is_momentum = avg_skew > 0.5 and avg_wl > 2.0
    is_concentrated = top20_pct > 50
    is_stable = pct_years_ok > 70

    print()
    if is_momentum:
        print("  Pattern identifie : MOMENTUM DEGUISE EN MEAN REVERSION")
        print("    -> IBS < 0.2 = journee baissiere dans un trend haussier (SMA200)")
        print("    -> Le 'rebond' capture en fait une continuation de tendance macro")
        print("    -> Les gros gains viennent des trades ou le trend macro accelere")
    else:
        print("  Pattern identifie : MEAN REVERSION (classique)")

    print()
    if is_concentrated and not is_stable:
        print("  Recommandation : NE PAS TRADER")
        print("    -> Profit concentre dans quelques outliers")
        print("    -> Instabilite temporelle")
    elif is_concentrated:
        print("  Recommandation : PRUDENCE -- INVESTIGUER PLUS")
        print("    -> Edge reel mais dependant d'evenements rares")
        print("    -> Sizing conservateur si trade (50% position normale)")
    elif is_stable:
        print("  Recommandation : TRADER AVEC PRUDENCE")
        print("    -> Edge stable et distribue")
        print("    -> Mais profil momentum != MR classique, risque de regime change")
        print("    -> Fees swap overnight ignores (pourrait eroder l'edge)")
    else:
        print("  Recommandation : INVESTIGUER PLUS")
        print("    -> Pattern ambigu, besoin de plus de donnees")

    print()


if __name__ == "__main__":
    main()
