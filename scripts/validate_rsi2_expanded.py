"""Phase 1 validation -- Step 9 -- run 2026-03-01
Results OOS : EFA PF 1.18 [inclus], GLD 0.95 / TLT 1.04 / XLE 1.02 [rejetes].
See docs/PHASE1_RESULTS.md for full context.

RSI(2) Mean Reversion -- Univers elargi : GLD, TLT, XLE, EFA.

Question cle : l'edge MR court-terme s'etend-il hors equity US ?
Split IS (2005-2014) / OOS (2014-2025).
Pool expanded (4 nouveaux ETFs) + pool total (8 ETFs = equity + expanded).
Fee model : us_etfs_usd (compte USD, pas de FX).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.base_loader import to_cache_arrays
from data.yahoo_loader import YahooLoader
from engine.backtest_config import BacktestConfig
from engine.fee_model import FEE_MODEL_US_ETFS_USD
from engine.indicator_cache import build_cache
from engine.mean_reversion_backtest import _simulate_mean_reversion

# --- Configuration -----------------------------------------------------------

EXPANDED = ["GLD", "TLT", "XLE", "EFA"]
EQUITY   = ["SPY", "QQQ", "IWM", "DIA"]

START    = "2005-01-01"
END      = "2025-01-01"
IS_SPLIT = "2014-01-01"

INITIAL_CAPITAL = 100_000.0

CACHE_GRID = {
    "sma_trend_period": [200],
    "sma_exit_period":  [5],
    "rsi_period":       [2],
    "adx_period":       [14],
    "atr_period":       [14],
}

PARAMS = {
    "strategy_type":      "mean_reversion",
    "rsi_period":          2,
    "rsi_entry_threshold": 10.0,
    "sma_trend_period":    200,
    "sma_exit_period":     5,
    "rsi_exit_threshold":  0.0,
    "sl_percent":          0.0,
    "position_fraction":   0.2,
    "cooldown_candles":    0,
    "sma_trend_buffer":    1.0,
}

CONFIG = BacktestConfig(
    symbol="",
    initial_capital=INITIAL_CAPITAL,
    slippage_pct=0.0003,
    fee_model=FEE_MODEL_US_ETFS_USD,
)


# --- Helpers -----------------------------------------------------------------

def _run_one(
    df: "pd.DataFrame",
) -> tuple[list[float], list[float], list[int]]:
    """Run MR sur un DataFrame, retourne (pnls, returns, holding_days)."""
    arrays = to_cache_arrays(df)
    cache  = build_cache(arrays, CACHE_GRID)
    holding: list[int] = []
    pnls, rets, _ = _simulate_mean_reversion(cache, PARAMS, CONFIG, holding)
    return pnls, rets, holding


def _metrics(
    pnls:    list[float],
    rets:    list[float],
    holding: list[int],
    total_days: float = 0.0,
) -> dict:
    """Calcule les metriques depuis les outputs bruts."""
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

    avg_h = float(np.mean(holding)) if holding else 0.0
    return {
        "n_trades": nt, "win_rate": wr, "sharpe": sharpe,
        "profit_factor": pf, "net_return_pct": net,
        "avg_hold_days": avg_h,
    }


def _fmt(m: dict) -> str:
    return (
        f"{m['n_trades']:3d} trades, WR {m['win_rate']:.0f}%,"
        f" Sharpe {m['sharpe']:.2f}, PF {m['profit_factor']:.2f},"
        f" Net {m['net_return_pct']:+.1f}%"
    )


def _sma_pct_above(df: "pd.DataFrame", period: int = 200) -> float:
    """Pct de jours ou le close est au-dessus de la SMA(period)."""
    closes = df["Close"].values
    if len(closes) <= period:
        return float("nan")
    sma_vals = np.convolve(closes, np.ones(period) / period, mode="valid")
    # sma_vals[i] correspond a closes[period-1+i]
    closes_aligned = closes[period - 1:]
    above = np.sum(closes_aligned > sma_vals)
    return above / len(sma_vals) * 100


# --- Data loading ------------------------------------------------------------

def _load_data(
    symbols: list[str],
    loader: "YahooLoader",
) -> dict[str, "pd.DataFrame"]:
    """Charge les DataFrames pour chaque symbole."""
    data: dict[str, "pd.DataFrame"] = {}
    for sym in symbols:
        print(f"  Chargement {sym} ...")
        try:
            df = loader.get_daily_candles(sym, START, END)
            data[sym] = df
            print(f"    {len(df)} candles"
                  f" ({df.index[0].date()} -> {df.index[-1].date()})")
        except Exception as e:
            print(f"    [!] Erreur {sym}: {e}")
    return data


# --- Run per-asset -----------------------------------------------------------

def _run_asset(
    sym: str,
    df: "pd.DataFrame",
    split_date: "pd.Timestamp",
) -> dict:
    """Cree le dict de resultats full/IS/OOS pour un asset."""
    n = len(df)
    td_full = n * 365 / 252

    pnls_f, rets_f, hold_f = _run_one(df)
    m_full = _metrics(pnls_f, rets_f, hold_f, td_full)

    df_is  = df[df.index <  split_date]
    df_oos = df[df.index >= split_date]

    pnls_is,  rets_is,  hold_is  = _run_one(df_is)  if len(df_is)  > 200 else ([], [], [])
    pnls_oos, rets_oos, hold_oos = _run_one(df_oos) if len(df_oos) > 200 else ([], [], [])

    m_is  = _metrics(pnls_is,  rets_is,  hold_is,  len(df_is)  * 365 / 252)
    m_oos = _metrics(pnls_oos, rets_oos, hold_oos, len(df_oos) * 365 / 252)

    return {
        "full": m_full, "is": m_is, "oos": m_oos,
        "pnls_full": pnls_f,  "rets_full": rets_f,  "hold_full": hold_f,
        "pnls_is":   pnls_is, "rets_is":   rets_is, "hold_is":   hold_is,
        "pnls_oos":  pnls_oos,"rets_oos":  rets_oos,"hold_oos":  hold_oos,
        "td_full": td_full,
        "td_is":   len(df_is)  * 365 / 252,
        "td_oos":  len(df_oos) * 365 / 252,
    }


def _pool_metrics(
    results: dict[str, dict],
    period: str,
    td_key: str,
    n_assets: int,
) -> dict:
    """Pooling simple : concatenation de tous les trades de tous les assets."""
    all_pnls: list[float] = []
    all_rets:  list[float] = []
    all_hold:  list[int]   = []
    total_td = 0.0
    for r in results.values():
        all_pnls.extend(r[f"pnls_{period}"])
        all_rets.extend( r[f"rets_{period}"])
        all_hold.extend( r[f"hold_{period}"])
        total_td += r[td_key]
    avg_td = total_td / n_assets if n_assets > 0 else 1.0
    return _metrics(all_pnls, all_rets, all_hold, avg_td)


# --- Main --------------------------------------------------------------------

def main() -> None:
    """Point d'entree du script de validation univers elargi."""
    import pandas as pd  # noqa: PLC0415

    loader     = YahooLoader()
    split_date = pd.Timestamp(IS_SPLIT)

    # --- Charger les donnees -------------------------------------------------
    print("=== Chargement univers elargi ===")
    exp_data = _load_data(EXPANDED, loader)
    print()
    print("=== Chargement univers equity (reference, 2005-2025) ===")
    eq_data  = _load_data(EQUITY, loader)
    print()

    # --- Validation par asset (expanded) -------------------------------------
    exp_results: dict[str, dict] = {}
    for sym in EXPANDED:
        if sym not in exp_data:
            continue
        exp_results[sym] = _run_asset(sym, exp_data[sym], split_date)

    # --- Validation par asset (equity, periode 2005-2025 uniquement) ---------
    eq_results: dict[str, dict] = {}
    for sym in EQUITY:
        if sym not in eq_data:
            continue
        eq_results[sym] = _run_asset(sym, eq_data[sym], split_date)

    n_exp = len(exp_results)
    n_eq  = len(eq_results)

    # --- Metriques poolees ---------------------------------------------------
    m_exp_full = _pool_metrics(exp_results, "full", "td_full", n_exp)
    m_exp_is   = _pool_metrics(exp_results, "is",   "td_is",   n_exp)
    m_exp_oos  = _pool_metrics(exp_results, "oos",  "td_oos",  n_exp)

    all_results = {**exp_results, **eq_results}
    n_total = len(all_results)
    m_tot_full = _pool_metrics(all_results, "full", "td_full", n_total)
    m_tot_is   = _pool_metrics(all_results, "is",   "td_is",   n_total)
    m_tot_oos  = _pool_metrics(all_results, "oos",  "td_oos",  n_total)

    # --- Rapport -------------------------------------------------------------
    print("==============================================================")
    print("  RSI(2) -- Univers Elargi -- Compte USD")
    print("==============================================================")
    print("  Per-asset (full 2005-2025) :")
    for sym in EXPANDED:
        if sym in exp_results:
            m = exp_results[sym]["full"]
            print(f"  {sym:4s} : {_fmt(m)}")

    print("--------------------------------------------------------------")
    print("  Pool expanded (4 nouveaux ETFs) :")
    print(f"  Full : {_fmt(m_exp_full)}")
    print(f"  IS   : {_fmt(m_exp_is)}")
    print(f"  OOS  : {_fmt(m_exp_oos)}")

    print("--------------------------------------------------------------")
    print(f"  Pool TOTAL ({n_total} ETFs = equity + expanded) :")
    print(f"  Full : {_fmt(m_tot_full)}")
    print(f"  IS   : {_fmt(m_tot_is)}")
    print(f"  OOS  : {_fmt(m_tot_oos)}")

    print("==============================================================")
    print("  VERDICT par asset (PF OOS > 1.1 = inclusion portfolio) :")
    for sym in EXPANDED:
        if sym not in exp_results:
            print(f"  {sym:4s} : [ERREUR chargement]")
            continue
        m_oos = exp_results[sym]["oos"]
        pf    = m_oos["profit_factor"]
        nt    = m_oos["n_trades"]
        tag   = "[OK]" if pf >= 1.1 else "[!] "
        note  = "" if nt >= 30 else " (masse faible)"
        print(f"  {tag} {sym:4s} : PF OOS = {pf:.2f}, {nt} trades{note}")

    print("==============================================================")

    # --- Diagnostic TLT : jours au-dessus / en-dessous SMA(200) ------------
    if "TLT" in exp_data:
        df_tlt  = exp_data["TLT"]
        pct_up  = _sma_pct_above(df_tlt, 200)
        df_oos_tlt = df_tlt[df_tlt.index >= split_date]
        pct_up_oos = _sma_pct_above(df_oos_tlt, 200)
        nt_oos  = exp_results.get("TLT", {}).get("oos", {}).get("n_trades", 0)
        print()
        print("  [Diagnostic TLT]")
        print(f"  Full (2005-2025) : {pct_up:.0f}% des jours au-dessus SMA(200)")
        print(f"  OOS  (2014-2025) : {pct_up_oos:.0f}% des jours au-dessus SMA(200)")
        print(f"  Trades OOS       : {nt_oos}")
        if pct_up_oos < 40:
            print("  [!] TLT passe la majorite du temps sous SMA(200) en OOS")
            print("      -> le filtre trend bloque les entrees (bear market 2022-2023)")
        print()

    # --- Synthese equity reference -------------------------------------------
    print("  [Reference equity 2005-2025] :")
    for sym in EQUITY:
        if sym in eq_results:
            m = eq_results[sym]["full"]
            print(f"  {sym:4s} : {_fmt(m)}")
    print(f"  Pool equity OOS : {_fmt(_pool_metrics(eq_results, 'oos', 'td_oos', n_eq))}")
    print()


if __name__ == "__main__":
    main()
