"""Validation RSI(2) Mean Reversion (Connors) sur SPY — 2000->2025.

Compare les résultats du moteur mean reversion aux benchmarks publiés de Connors :
  - Trades : 200-400 sur 25 ans (~10-15/an)
  - Win Rate : 70-80%
  - Profit Factor : 1.5-2.5
  - Avg gain per trade : 0.5-0.7%
  - Holding period : 2-5 jours

Si les résultats divergent fortement, il y a probablement un bug dans le moteur.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.base_loader import to_cache_arrays
from data.yahoo_loader import YahooLoader
from engine.backtest_config import BacktestConfig
from engine.fee_model import FEE_MODEL_US_ETFS_USD, FEE_MODEL_US_STOCKS, FeeModel
from engine.indicator_cache import build_cache
from engine.indicators import rsi, sma
from engine.mean_reversion_backtest import (
    _simulate_mean_reversion,
    run_mr_backtest_from_cache,
)

# ─── Configuration ───────────────────────────────────────────────────────────

SYMBOL = "SPY"
START = "2000-01-01"
END = "2025-01-01"
IS_SPLIT = "2014-01-01"  # IS: 2000-2014, OOS: 2014-2025

CACHE_GRID = {
    "sma_trend_period": [200],
    "sma_exit_period": [5],
    "rsi_period": [2],
    "adx_period": [14],
    "atr_period": [14],
}

PARAMS = {
    "strategy_type": "mean_reversion",
    "rsi_period": 2,
    "rsi_entry_threshold": 5.0,
    "sma_trend_period": 200,
    "sma_exit_period": 5,
    "rsi_exit_threshold": 0.0,   # désactivé — exit SMA uniquement
    "sl_percent": 0.0,            # pas de SL (Connors classique)
    "position_fraction": 0.2,
    "cooldown_candles": 0,
    "sma_trend_buffer": 1.0,      # pas de buffer
}

CONFIG = BacktestConfig(
    symbol=SYMBOL,
    initial_capital=100_000.0,
    slippage_pct=0.0003,
    fee_model=FEE_MODEL_US_STOCKS,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

INITIAL_CAPITAL = 100_000.0


def _metrics_from_sim(
    pnls: list[float],
    rets: list[float],
    holding: list[int],
) -> dict:
    """Calcule les metriques detaillees depuis les outputs bruts de la simulation."""
    nt = len(pnls)
    nw = sum(1 for p in pnls if p > 0)
    wr = nw / nt * 100 if nt else 0.0
    pf_num = sum(p for p in pnls if p > 0)
    pf_den = abs(sum(p for p in pnls if p < 0))
    pf = pf_num / pf_den if pf_den > 0 else float("inf")
    net_ret = sum(pnls) / INITIAL_CAPITAL * 100
    winners = [r * 100 for r in rets if r > 0]
    losers = [r * 100 for r in rets if r <= 0]
    avg_w = float(np.mean(winners)) if winners else 0.0
    avg_l = float(np.mean(losers)) if losers else 0.0
    avg_h = float(np.mean(holding)) if holding else 0.0
    return {
        "n_trades": nt, "win_rate": wr, "profit_factor": pf,
        "net_return_pct": net_ret, "avg_winner": avg_w, "avg_loser": avg_l,
        "avg_hold_days": avg_h,
    }


def _run_sim(
    cache: "IndicatorCache",
    params: dict,
    config: BacktestConfig,
) -> dict:
    """Run simulation MR et retourne les metriques."""
    holding: list[int] = []
    pnls, rets, _ = _simulate_mean_reversion(cache, params, config, holding)
    m = _metrics_from_sim(pnls, rets, holding)
    # Ajouter Sharpe via _compute_fast_metrics
    result = run_mr_backtest_from_cache(params, cache, config)
    m["sharpe"] = result[1]
    return m


def _run_period(
    df_period: "pd.DataFrame",
    label: str,
) -> dict:
    """Run le backtest MR sur une période et retourne les métriques détaillées."""
    arrays = to_cache_arrays(df_period)
    cache = build_cache(arrays, CACHE_GRID)

    holding_days: list[int] = []
    trade_pnls, trade_returns, final_capital = _simulate_mean_reversion(
        cache, PARAMS, CONFIG, holding_days_out=holding_days,
    )

    result = run_mr_backtest_from_cache(PARAMS, cache, CONFIG)
    _, sharpe, net_return_pct, profit_factor, n_trades = result

    n_winners = sum(1 for p in trade_pnls if p > 0)
    win_rate = n_winners / n_trades * 100 if n_trades > 0 else 0.0

    winners = [r * 100 for r in trade_returns if r > 0]
    losers = [r * 100 for r in trade_returns if r <= 0]
    avg_winner = np.mean(winners) if winners else 0.0
    avg_loser = np.mean(losers) if losers else 0.0

    avg_hold = np.mean(holding_days) if holding_days else 0.0

    return {
        "label": label,
        "n_trades": n_trades,
        "win_rate": win_rate,
        "sharpe": sharpe,
        "net_return_pct": net_return_pct,
        "profit_factor": profit_factor,
        "avg_winner": avg_winner,
        "avg_loser": avg_loser,
        "avg_hold_days": avg_hold,
        "final_capital": final_capital,
    }


def _print_full_report(full: dict, is_m: dict, oos_m: dict) -> None:
    """Affiche le rapport de validation."""
    fee = CONFIG.fee_model
    print()
    print("==============================================================")
    print(f"  {SYMBOL} — RSI(2) Mean Reversion (Connors) — {START[:4]}->{END[:4]}")
    print("==============================================================")
    print(f"  Trades        : {full['n_trades']}")
    print(f"  Win Rate      : {full['win_rate']:.1f}%")
    print(f"  Sharpe        : {full['sharpe']:.3f}")
    print(f"  Net Return    : {full['net_return_pct']:+.2f}%")
    print(f"  Profit Factor : {full['profit_factor']:.2f}")
    print(f"  Avg Winner    : {full['avg_winner']:+.2f}%")
    print(f"  Avg Loser     : {full['avg_loser']:+.2f}%")
    print(f"  Avg Hold Days : {full['avg_hold_days']:.1f}")
    print(f"  Fee Model     : {fee.name} (commission=${fee.commission_per_trade:.0f},"
          f" spread={fee.spread_pct*100:.2f}%, fx={fee.fx_conversion_pct*100:.2f}%)")
    print("--------------------------------------------------------------")
    print(f"  IS  ({START[:4]}-{IS_SPLIT[:4]}) : {is_m['n_trades']} trades,"
          f" WR {is_m['win_rate']:.0f}%,"
          f" Sharpe {is_m['sharpe']:.2f},"
          f" PF {is_m['profit_factor']:.2f}")
    print(f"  OOS ({IS_SPLIT[:4]}-{END[:4]}) : {oos_m['n_trades']} trades,"
          f" WR {oos_m['win_rate']:.0f}%,"
          f" Sharpe {oos_m['sharpe']:.2f},"
          f" PF {oos_m['profit_factor']:.2f}")
    print("==============================================================")

    # Sanity checks
    print()
    warnings = []
    if full["win_rate"] < 60:
        warnings.append(f"  [!] Win rate {full['win_rate']:.1f}% < 60% (attendu 70-80%)")
    if full["profit_factor"] < 1.2:
        warnings.append(f"  [!] Profit Factor {full['profit_factor']:.2f} < 1.2 (attendu 1.5-2.5)")
    if full["n_trades"] < 100:
        warnings.append(f"  [!] Seulement {full['n_trades']} trades (attendu 200-400)")
    if full["avg_hold_days"] > 10:
        warnings.append(f"  [!] Avg Hold {full['avg_hold_days']:.1f}j > 10j (attendu 2-5)")

    if warnings:
        print("  ALERTES — resultats hors benchmarks Connors :")
        for w in warnings:
            print(w)
        print()
        print("  -> Investiguer le moteur avant de continuer.")
    else:
        print("  [OK] Resultats coherents avec la litterature Connors.")
    print()


# ─── Main --------------------------------------------------------------──────

def main() -> None:
    """Point d'entrée du script de validation."""
    import pandas as pd  # noqa: PLC0415

    print(f"Chargement {SYMBOL} {START} -> {END} ...")
    loader = YahooLoader()
    df = loader.get_daily_candles(SYMBOL, START, END)
    print(f"  {len(df)} candles chargées ({df.index[0].date()} -> {df.index[-1].date()})")

    # Full period
    print("\nBacktest période complète ...")
    full = _run_period(df, "Full")

    # IS / OOS split
    split_date = pd.Timestamp(IS_SPLIT)
    df_is = df[df.index < split_date]
    df_oos = df[df.index >= split_date]
    print(f"IS  : {len(df_is)} candles ({df_is.index[0].date()} -> {df_is.index[-1].date()})")
    print(f"OOS : {len(df_oos)} candles ({df_oos.index[0].date()} -> {df_oos.index[-1].date()})")

    print("Backtest IS ...")
    is_m = _run_period(df_is, "IS")
    print("Backtest OOS ...")
    oos_m = _run_period(df_oos, "OOS")

    _print_full_report(full, is_m, oos_m)

    # ── Diagnostic : signal counts + fee comparison ──
    _print_diagnostics(df)

    # ── Compte USD (sans FX) : sensibilite RSI + IS/OOS ──
    _print_usd_validation(df, df_is, df_oos)


def _print_diagnostics(df: "pd.DataFrame") -> None:
    """Diagnostic : frequence des signaux et impact des frais."""
    arrays = to_cache_arrays(df)
    closes = arrays["closes"]
    n = len(closes)

    rsi_arr = rsi(closes, 2)
    sma200 = sma(closes, 200)

    warmup = 202
    n_rsi_below_5 = 0
    n_rsi_below_10 = 0
    n_rsi_below_25 = 0
    n_trend_ok = 0
    n_both_5 = 0
    n_both_10 = 0
    n_both_25 = 0

    for i in range(warmup, n):
        prev = i - 1
        if np.isnan(rsi_arr[prev]) or np.isnan(sma200[prev]):
            continue
        trend_ok = closes[prev] > sma200[prev]
        if trend_ok:
            n_trend_ok += 1
        if rsi_arr[prev] < 5:
            n_rsi_below_5 += 1
            if trend_ok:
                n_both_5 += 1
        if rsi_arr[prev] < 10:
            n_rsi_below_10 += 1
            if trend_ok:
                n_both_10 += 1
        if rsi_arr[prev] < 25:
            n_rsi_below_25 += 1
            if trend_ok:
                n_both_25 += 1

    print("--------------------------------------------------------------")
    print("  DIAGNOSTIC -- frequence des signaux")
    print("--------------------------------------------------------------")
    print(f"  Candles apres warmup  : {n - warmup}")
    print(f"  Close > SMA(200)      : {n_trend_ok} ({n_trend_ok/(n-warmup)*100:.1f}%)")
    print(f"  RSI(2) < 5            : {n_rsi_below_5} ({n_rsi_below_5/(n-warmup)*100:.1f}%)")
    print(f"  RSI(2) < 10           : {n_rsi_below_10} ({n_rsi_below_10/(n-warmup)*100:.1f}%)")
    print(f"  RSI(2) < 25           : {n_rsi_below_25} ({n_rsi_below_25/(n-warmup)*100:.1f}%)")
    print(f"  RSI<5 + trend OK      : {n_both_5}")
    print(f"  RSI<10 + trend OK     : {n_both_10}")
    print(f"  RSI<25 + trend OK     : {n_both_25}")

    # Comparaison fee models
    print()
    print("--------------------------------------------------------------")
    print("  COMPARAISON : Saxo EUR vs USD vs zero-fee")
    print("--------------------------------------------------------------")

    cache = build_cache(arrays, CACHE_GRID)

    for label, fee_model, slip in [
        ("Saxo EUR (FX 0.25%)", FEE_MODEL_US_STOCKS, 0.0003),
        ("Compte USD (no FX) ", FEE_MODEL_US_ETFS_USD, 0.0003),
        ("Sans frais         ", FeeModel(name="zero"), 0.0),
    ]:
        cfg = BacktestConfig(
            symbol=SYMBOL, initial_capital=INITIAL_CAPITAL,
            slippage_pct=slip, fee_model=fee_model,
        )
        m = _run_sim(cache, PARAMS, cfg)
        print(f"  {label}: {m['n_trades']} trades, WR {m['win_rate']:.0f}%,"
              f" PF {m['profit_factor']:.2f}, ret {m['net_return_pct']:+.2f}%,"
              f" hold {m['avg_hold_days']:.1f}j")

    print()


def _print_usd_validation(
    df: "pd.DataFrame",
    df_is: "pd.DataFrame",
    df_oos: "pd.DataFrame",
) -> None:
    """Validation compte USD : sensibilite RSI + split IS/OOS pour RSI<10."""
    import pandas as pd  # noqa: PLC0415

    cfg_usd = BacktestConfig(
        symbol=SYMBOL, initial_capital=INITIAL_CAPITAL,
        slippage_pct=0.0003, fee_model=FEE_MODEL_US_ETFS_USD,
    )

    # Full period : 3 seuils RSI
    arrays_full = to_cache_arrays(df)
    cache_full = build_cache(arrays_full, CACHE_GRID)

    print("==============================================================")
    print(f"  {SYMBOL} -- RSI(2) Connors -- Compte USD (sans FX)")
    print("==============================================================")

    for threshold in [5.0, 10.0, 25.0]:
        p = dict(PARAMS)
        p["rsi_entry_threshold"] = threshold
        m = _run_sim(cache_full, p, cfg_usd)
        print(f"  RSI < {threshold:<4.0f}: {m['n_trades']:3d} trades,"
              f" WR {m['win_rate']:.0f}%, Sharpe {m['sharpe']:.2f},"
              f" PF {m['profit_factor']:.2f}, Net {m['net_return_pct']:+.2f}%")

    # IS/OOS split pour RSI < 10
    params_10 = dict(PARAMS)
    params_10["rsi_entry_threshold"] = 10.0

    arrays_is = to_cache_arrays(df_is)
    cache_is = build_cache(arrays_is, CACHE_GRID)
    m_is = _run_sim(cache_is, params_10, cfg_usd)

    arrays_oos = to_cache_arrays(df_oos)
    cache_oos = build_cache(arrays_oos, CACHE_GRID)
    m_oos = _run_sim(cache_oos, params_10, cfg_usd)

    print("--------------------------------------------------------------")
    print("  Split IS/OOS pour RSI < 10 :")
    print(f"  IS  ({START[:4]}-{IS_SPLIT[:4]}) : {m_is['n_trades']} trades,"
          f" WR {m_is['win_rate']:.0f}%, Sharpe {m_is['sharpe']:.2f},"
          f" PF {m_is['profit_factor']:.2f}")
    print(f"  OOS ({IS_SPLIT[:4]}-{END[:4]}) : {m_oos['n_trades']} trades,"
          f" WR {m_oos['win_rate']:.0f}%, Sharpe {m_oos['sharpe']:.2f},"
          f" PF {m_oos['profit_factor']:.2f}")
    print("==============================================================")
    print()


if __name__ == "__main__":
    main()
