"""RSI(2) Mean Reversion — Actions individuelles US large cap.

Teste si RSI(2) Connors fonctionne mieux sur actions individuelles
que sur ETFs, grâce aux pullbacks plus profonds (5-10% vs 1.5%).

Méthodologie identique à validate_rsi2_final.py :
- Params Connors canoniques (production_params.yaml)
- Split IS 2005-2014 / OOS 2014-2025
- Fee model : us_stocks_usd (compte USD, spread 0.05%)
- Capital : $10,000, whole shares (floor), position_fraction=0.2

Comparaison poolée avec ETFs ($10k whole shares, fee ETFs USD).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.base_loader import to_cache_arrays
from data.yahoo_loader import YahooLoader
from engine.backtest_config import BacktestConfig
from engine.fast_backtest import _close_trend_position
from engine.fee_model import FEE_MODEL_US_ETFS_USD, FEE_MODEL_US_STOCKS_USD
from engine.indicator_cache import IndicatorCache, build_cache

# --- Configuration -----------------------------------------------------------

UNIVERSE: dict[str, str] = {
    # Tech (high beta, deep pullbacks)
    "AAPL":  "2005-01-01",
    "MSFT":  "2005-01-01",
    "GOOGL": "2005-01-01",
    "NVDA":  "2005-01-01",
    "META":  "2012-06-01",
    "AMD":   "2005-01-01",
    "TSLA":  "2010-07-01",
    # Finance
    "JPM":   "2005-01-01",
    "GS":    "2005-01-01",
    # Consumer / Defensive
    "KO":    "2005-01-01",
    "JNJ":   "2005-01-01",
    # Industrial / Energy
    "XOM":   "2005-01-01",
    "CAT":   "2005-01-01",
    # Retail
    "AMZN":  "2005-01-01",
    "WMT":   "2005-01-01",
}

ETF_UNIVERSE = ["SPY", "QQQ", "IWM", "DIA", "EFA"]

END       = "2025-01-01"
IS_SPLIT  = "2014-01-01"

INITIAL_CAPITAL = 10_000.0

CACHE_GRID = {
    "sma_trend_period": [200],
    "sma_exit_period":  [5],
    "rsi_period":       [2],
    "adx_period":       [14],
    "atr_period":       [14],
}

PARAMS = {
    "strategy_type":       "mean_reversion",
    "rsi_period":           2,
    "rsi_entry_threshold":  10.0,
    "sma_trend_period":     200,
    "sma_exit_period":      5,
    "rsi_exit_threshold":   0.0,
    "sl_percent":           0.0,
    "position_fraction":    0.2,
    "cooldown_candles":     0,
    "sma_trend_buffer":     1.01,
}


# --- Moteur local avec whole shares ------------------------------------------

def _simulate_mr_whole(
    cache: IndicatorCache,
    params: dict[str, Any],
    config: BacktestConfig,
) -> tuple[list[float], list[float], int, list[float]]:
    """Copie de _simulate_mean_reversion avec whole shares (floor).

    Returns
    -------
    (trade_pnls, trade_returns, n_skipped, trade_sizes)
    """
    rsi_period: int       = params.get("rsi_period", 2)
    rsi_entry: float      = params.get("rsi_entry_threshold", 5.0)
    sma_trend_p: int      = params.get("sma_trend_period", 200)
    sma_exit_p: int       = params.get("sma_exit_period", 5)
    rsi_exit_thr: float   = params.get("rsi_exit_threshold", 0.0)
    sl_pct: float         = params.get("sl_percent", 0.0) / 100.0
    pos_frac: float       = params.get("position_fraction", 0.2)
    cooldown: int         = params.get("cooldown_candles", 0)
    sma_buf: float        = params.get("sma_trend_buffer", 1.0)

    n         = cache.n_candles
    opens     = cache.opens
    closes    = cache.closes
    lows      = cache.lows
    sma_trend = cache.sma_by_period[sma_trend_p]
    sma_exit  = cache.sma_by_period[sma_exit_p]
    rsi_arr   = cache.rsi_by_period[rsi_period]

    capital          = config.initial_capital
    fee_model        = config.fee_model
    slippage_pct     = config.slippage_pct
    max_dd_pct       = config.max_wfo_drawdown_pct / 100.0

    trade_pnls:    list[float] = []
    trade_returns: list[float] = []
    trade_sizes:   list[float] = []

    in_position      = False
    entry_price      = 0.0
    quantity         = 0.0
    entry_fee        = 0.0
    capital_allocated = 0.0
    sl_price         = 0.0
    entry_candle     = -1
    cooldown_rem     = 0
    peak_capital     = capital
    n_skipped        = 0

    warmup = max(sma_trend_p, sma_exit_p, rsi_period + 1) + 2

    def _exit(exit_price: float, candle_idx: int) -> None:
        nonlocal capital, in_position, cooldown_rem, peak_capital
        n_days = candle_idx - entry_candle
        pnl = _close_trend_position(
            1, entry_price, exit_price, quantity,
            fee_model, entry_fee, n_days,
        )
        capital += capital_allocated + pnl
        if capital > 0:
            trade_pnls.append(pnl)
            trade_returns.append(pnl / capital)
        peak_capital = max(peak_capital, capital)
        in_position = False
        cooldown_rem = cooldown

    for i in range(warmup, n):
        equity = capital + (capital_allocated if in_position else 0.0)
        if equity < peak_capital * (1 - max_dd_pct):
            break

        if in_position:
            if sl_pct > 0 and opens[i] <= sl_price:
                _exit(opens[i], i)
                continue
            if sl_pct > 0 and lows[i] <= sl_price:
                _exit(sl_price * (1 - slippage_pct), i)
                continue
            close_i = closes[i]
            sma_ev = sma_exit[i]
            if not math.isnan(sma_ev) and close_i > sma_ev:
                _exit(close_i, i)
                continue
            if rsi_exit_thr > 0:
                rv = rsi_arr[i]
                if not math.isnan(rv) and rv > rsi_exit_thr:
                    _exit(close_i, i)
                    continue
            stv = sma_trend[i]
            if not math.isnan(stv) and close_i < stv:
                _exit(close_i, i)
                continue
            continue

        # NOT IN POSITION
        if cooldown_rem > 0:
            cooldown_rem -= 1
            continue

        prev = i - 1
        sma_tp = sma_trend[prev]
        if math.isnan(sma_tp):
            continue
        if closes[prev] <= sma_tp * sma_buf:
            continue
        rp = rsi_arr[prev]
        if math.isnan(rp):
            continue
        if rp >= rsi_entry:
            continue

        # === ENTRY ===
        ep        = opens[i] * (1 + slippage_pct)
        available = capital * pos_frac
        qty       = math.floor(available / ep)
        if qty < 1:
            n_skipped += 1
            continue
        cap_alloc = qty * ep

        entry_price       = ep
        quantity          = qty
        capital_allocated = cap_alloc
        entry_notional    = qty * ep
        entry_fee         = fee_model.total_entry_cost(entry_notional)
        capital          -= cap_alloc
        trade_sizes.append(entry_notional)

        sl_price     = ep * (1 - sl_pct) if sl_pct > 0 else 0.0
        in_position  = True
        entry_candle = i

        # Exit checks on entry day
        if sl_pct > 0 and lows[i] <= sl_price:
            _exit(sl_price * (1 - slippage_pct), i)
            continue
        close_i = closes[i]
        sma_ev = sma_exit[i]
        if not math.isnan(sma_ev) and close_i > sma_ev:
            _exit(close_i, i)
            continue
        if rsi_exit_thr > 0:
            rv = rsi_arr[i]
            if not math.isnan(rv) and rv > rsi_exit_thr:
                _exit(close_i, i)
                continue
        stv = sma_trend[i]
        if not math.isnan(stv) and close_i < stv:
            _exit(close_i, i)
            continue

    # Force-close fin de données (pas dans trade_pnls)
    if in_position:
        pnl = _close_trend_position(
            1, entry_price, closes[n - 1], quantity,
            fee_model, entry_fee, (n - 1) - entry_candle,
        )
        capital += capital_allocated + pnl

    return trade_pnls, trade_returns, n_skipped, trade_sizes


# --- Métriques ---------------------------------------------------------------

def _metrics_per_asset(
    pnls: list[float],
    rets: list[float],
    sizes: list[float],
    n_skipped: int,
    total_days: float,
) -> dict:
    """Métriques par action individuelle."""
    nt  = len(pnls)
    nw  = sum(1 for p in pnls if p > 0)
    wr  = nw / nt * 100 if nt else 0.0
    pf_num = sum(p for p in pnls if p > 0)
    pf_den = abs(sum(p for p in pnls if p < 0))
    pf  = pf_num / pf_den if pf_den > 0 else float("inf")
    net = sum(pnls) / INITIAL_CAPITAL * 100

    sharpe = 0.0
    if nt >= 3 and len(rets) >= 2:
        arr = np.array(rets)
        std = float(np.std(arr))
        if std > 1e-10:
            tpy = nt / max(total_days, 1) * 365 if total_days > 0 else nt
            sharpe = float(np.mean(arr) / std * np.sqrt(tpy))

    avg_ret = float(np.mean(rets) * 100) if rets else 0.0
    avg_pnl = float(np.mean(pnls)) if pnls else 0.0

    return {
        "n_trades": nt, "win_rate": wr, "sharpe": sharpe,
        "profit_factor": pf, "net_return_pct": net,
        "avg_ret_pct": avg_ret, "avg_pnl": avg_pnl,
        "n_skipped": n_skipped,
    }


def _metrics_pooled(
    pnls: list[float],
    rets: list[float],
    total_days: float,
    n_assets: int,
) -> dict:
    """Métriques poolées multi-actifs."""
    nt  = len(pnls)
    nw  = sum(1 for p in pnls if p > 0)
    wr  = nw / nt * 100 if nt else 0.0
    pf_num = sum(p for p in pnls if p > 0)
    pf_den = abs(sum(p for p in pnls if p < 0))
    pf  = pf_num / pf_den if pf_den > 0 else float("inf")

    sharpe = 0.0
    if nt >= 3 and len(rets) >= 2:
        arr = np.array(rets)
        std = float(np.std(arr))
        if std > 1e-10:
            tpy = nt / max(total_days / n_assets, 1) * 365
            sharpe = float(np.mean(arr) / std * np.sqrt(tpy))

    avg_ret = float(np.mean(rets) * 100) if rets else 0.0
    avg_pnl = float(np.mean(pnls)) if pnls else 0.0

    return {
        "n_trades": nt, "win_rate": wr, "sharpe": sharpe,
        "profit_factor": pf, "avg_ret_pct": avg_ret, "avg_pnl": avg_pnl,
    }


# --- Main --------------------------------------------------------------------

def main() -> None:
    """Point d'entrée : RSI(2) sur 15 actions individuelles US."""
    import pandas as pd  # noqa: PLC0415

    loader     = YahooLoader()
    split_date = pd.Timestamp(IS_SPLIT)

    config_stocks = BacktestConfig(
        symbol="",
        initial_capital=INITIAL_CAPITAL,
        slippage_pct=0.0003,
        fee_model=FEE_MODEL_US_STOCKS_USD,
    )

    config_etfs = BacktestConfig(
        symbol="",
        initial_capital=INITIAL_CAPITAL,
        slippage_pct=0.0003,
        fee_model=FEE_MODEL_US_ETFS_USD,
    )

    # ─── 1. Actions individuelles OOS ──────────────────────────────────────
    print("=" * 72)
    print("  RSI(2) Individual Stocks — OOS 2014-2025 — $10k whole shares")
    print("  Params: RSI<10, SMA(200)x1.01, SMA(5) exit, no SL")
    print("  Fees: USD account ($1 commission + 0.05% spread)")
    print("=" * 72)

    per_stock: dict[str, dict] = {}
    pool_pnls:  list[float] = []
    pool_rets:  list[float] = []
    pool_days = 0.0

    for sym, start in UNIVERSE.items():
        print(f"  {sym} ...", end="", flush=True)
        try:
            df = loader.get_daily_candles(sym, start, END)
        except Exception as e:
            print(f" SKIP ({e})")
            continue

        df_oos = df[df.index >= split_date]
        if len(df_oos) < 210:
            print(f" SKIP ({len(df_oos)} barres OOS < 210)")
            continue

        arrays = to_cache_arrays(df_oos)
        cache  = build_cache(arrays, CACHE_GRID)

        pnls, rets, skipped, sizes = _simulate_mr_whole(
            cache, PARAMS, config_stocks,
        )
        td = len(df_oos) * 365 / 252
        m  = _metrics_per_asset(pnls, rets, sizes, skipped, td)
        per_stock[sym] = m

        pool_pnls.extend(pnls)
        pool_rets.extend(rets)
        pool_days += td

        print(f" {m['n_trades']:3d} trades, WR {m['win_rate']:.0f}%,"
              f" PF {m['profit_factor']:.2f}")

    # Tableau trié par PF
    sorted_stocks = sorted(
        per_stock.items(), key=lambda x: x[1]["profit_factor"], reverse=True,
    )

    print()
    print("=" * 85)
    hdr = (f"  {'Ticker':<8} {'Trades':>6} {'WR':>5} {'PF':>6} {'Sharpe':>7}"
           f" {'Net%':>7} {'AvgRet%':>8} {'AvgPnL$':>8} {'Skipped':>8}")
    print(hdr)
    print("  " + "-" * 82)
    for sym, m in sorted_stocks:
        print(
            f"  {sym:<8}"
            f" {m['n_trades']:>6}"
            f" {m['win_rate']:>4.0f}%"
            f" {m['profit_factor']:>6.2f}"
            f" {m['sharpe']:>7.2f}"
            f" {m['net_return_pct']:>+6.1f}%"
            f" {m['avg_ret_pct']:>+7.3f}%"
            f" {m['avg_pnl']:>8.2f}"
            f" {m['n_skipped']:>8}"
        )
    print("=" * 85)

    # ─── 2. Poolé stocks ──────────────────────────────────────────────────
    n_stocks = len(per_stock)
    m_stocks = _metrics_pooled(pool_pnls, pool_rets, pool_days, n_stocks)

    print()
    print(f"  POOLED ({n_stocks} stocks) : {m_stocks['n_trades']} trades,"
          f" WR {m_stocks['win_rate']:.0f}%,"
          f" PF {m_stocks['profit_factor']:.2f},"
          f" Sharpe {m_stocks['sharpe']:.2f}")

    # ─── 3. ETFs comparaison ($10k whole shares) ──────────────────────────
    print()
    print("  Chargement ETFs pour comparaison...")
    etf_pnls: list[float] = []
    etf_rets: list[float] = []
    etf_days = 0.0

    for sym in ETF_UNIVERSE:
        df = loader.get_daily_candles(sym, "2005-01-01", END)
        df_oos = df[df.index >= split_date]
        arrays = to_cache_arrays(df_oos)
        cache  = build_cache(arrays, CACHE_GRID)
        pnls, rets, _, _ = _simulate_mr_whole(cache, PARAMS, config_etfs)
        etf_pnls.extend(pnls)
        etf_rets.extend(rets)
        etf_days += len(df_oos) * 365 / 252

    m_etfs = _metrics_pooled(etf_pnls, etf_rets, etf_days, len(ETF_UNIVERSE))

    print()
    print("  Comparaison avec ETFs ($10k whole shares) :")
    print(f"  ETFs ({len(ETF_UNIVERSE):>2})   :"
          f" {m_etfs['n_trades']:>4} trades,"
          f" PF {m_etfs['profit_factor']:.2f},"
          f" Sharpe {m_etfs['sharpe']:.2f},"
          f" AvgRet {m_etfs['avg_ret_pct']:+.3f}%,"
          f" AvgPnL ${m_etfs['avg_pnl']:.2f}")
    print(f"  Stocks ({n_stocks:>2})  :"
          f" {m_stocks['n_trades']:>4} trades,"
          f" PF {m_stocks['profit_factor']:.2f},"
          f" Sharpe {m_stocks['sharpe']:.2f},"
          f" AvgRet {m_stocks['avg_ret_pct']:+.3f}%,"
          f" AvgPnL ${m_stocks['avg_pnl']:.2f}")

    # ─── 4. T-test OOS ────────────────────────────────────────────────────
    print()
    if len(pool_rets) >= 3:
        oos_arr = np.array(pool_rets)
        t_stat, p_two = stats.ttest_1samp(oos_arr, 0.0)
        p_ttest = float(p_two / 2) if t_stat > 0 else 1.0
        sig = "[significatif]" if p_ttest < 0.05 else "[non-significatif]"
        print(f"  t-test OOS (mean > 0) : t={t_stat:.2f},"
              f" p={p_ttest:.4f}  {sig}")
    else:
        p_ttest = 1.0
        print("  t-test OOS : pas assez de trades")

    # ─── 5. Recommandation ────────────────────────────────────────────────
    print()
    print("-" * 72)
    print("  RECOMMANDATION — Candidats scanner (PF OOS > 1.3) :")
    candidates = [
        (sym, m) for sym, m in sorted_stocks
        if m["profit_factor"] > 1.3 and m["n_trades"] >= 10
    ]
    if candidates:
        for sym, m in candidates:
            print(f"    {sym:<6} : PF {m['profit_factor']:.2f},"
                  f" WR {m['win_rate']:.0f}%,"
                  f" {m['n_trades']} trades,"
                  f" AvgPnL ${m['avg_pnl']:.2f}")
    else:
        print("    Aucun candidat avec PF > 1.3 et >= 10 trades.")

    # Actions avec PF < 1.0
    rejects = [
        (sym, m) for sym, m in sorted_stocks
        if m["profit_factor"] < 1.0 and m["n_trades"] >= 5
    ]
    if rejects:
        print()
        print("  REJETS (PF OOS < 1.0) :")
        for sym, m in rejects:
            print(f"    {sym:<6} : PF {m['profit_factor']:.2f},"
                  f" WR {m['win_rate']:.0f}%,"
                  f" {m['n_trades']} trades")

    print("-" * 72)
    print()

    return per_stock, m_stocks, m_etfs, p_ttest


if __name__ == "__main__":
    main()
