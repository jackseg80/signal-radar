"""Validation RSI(2) Mean Reversion -- Portfolio 4 ETFs equity US.

Params fixes RSI<10 (Connors standard), compte USD, pas d'optimisation.
Split IS (2000-2014) / OOS (2014-2025).
Trades pools par concat simple pour evaluer l'edge portfolio.
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

# ─── Configuration ───────────────────────────────────────────────────────────

SYMBOLS = ["SPY", "QQQ", "IWM", "DIA"]
START = "2000-01-01"
END = "2025-01-01"
IS_SPLIT = "2014-01-01"

INITIAL_CAPITAL = 100_000.0

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
    "rsi_entry_threshold": 10.0,
    "sma_trend_period": 200,
    "sma_exit_period": 5,
    "rsi_exit_threshold": 0.0,
    "sl_percent": 0.0,
    "position_fraction": 0.2,
    "cooldown_candles": 0,
    "sma_trend_buffer": 1.0,
}

CONFIG = BacktestConfig(
    symbol="",
    initial_capital=INITIAL_CAPITAL,
    slippage_pct=0.0003,
    fee_model=FEE_MODEL_US_ETFS_USD,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _run_one(
    df: "pd.DataFrame",
) -> tuple[list[float], list[float], list[int]]:
    """Run MR sur un DataFrame, retourne (pnls, returns, holding_days)."""
    arrays = to_cache_arrays(df)
    cache = build_cache(arrays, CACHE_GRID)
    holding: list[int] = []
    pnls, rets, _ = _simulate_mean_reversion(cache, PARAMS, CONFIG, holding)
    return pnls, rets, holding


def _metrics(
    pnls: list[float],
    rets: list[float],
    holding: list[int],
    total_days: float = 0.0,
) -> dict:
    """Calcule les metriques depuis les outputs bruts."""
    nt = len(pnls)
    nw = sum(1 for p in pnls if p > 0)
    wr = nw / nt * 100 if nt else 0.0
    pf_num = sum(p for p in pnls if p > 0)
    pf_den = abs(sum(p for p in pnls if p < 0))
    pf = pf_num / pf_den if pf_den > 0 else float("inf")
    net_ret = sum(pnls) / INITIAL_CAPITAL * 100

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
        "profit_factor": pf, "net_return_pct": net_ret,
        "avg_hold_days": avg_h,
    }


def _fmt(m: dict) -> str:
    """Formate une ligne de metriques."""
    return (f"{m['n_trades']:3d} trades, WR {m['win_rate']:.0f}%,"
            f" Sharpe {m['sharpe']:.2f}, PF {m['profit_factor']:.2f},"
            f" Net {m['net_return_pct']:+.1f}%")


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    """Point d'entree du script de validation portfolio."""
    import pandas as pd  # noqa: PLC0415

    loader = YahooLoader()
    split_date = pd.Timestamp(IS_SPLIT)

    # Collecter les resultats par asset et par periode
    per_asset_full: dict[str, dict] = {}
    pool_full_pnls: list[float] = []
    pool_full_rets: list[float] = []
    pool_full_hold: list[int] = []
    pool_is_pnls: list[float] = []
    pool_is_rets: list[float] = []
    pool_is_hold: list[int] = []
    pool_oos_pnls: list[float] = []
    pool_oos_rets: list[float] = []
    pool_oos_hold: list[int] = []

    total_days_full = 0.0
    total_days_is = 0.0
    total_days_oos = 0.0

    for sym in SYMBOLS:
        print(f"Chargement {sym} ...")
        df = loader.get_daily_candles(sym, START, END)
        n_candles = len(df)
        print(f"  {n_candles} candles ({df.index[0].date()} -> {df.index[-1].date()})")

        # Full period
        pnls, rets, hold = _run_one(df)
        td = n_candles * 365 / 252
        m_full = _metrics(pnls, rets, hold, td)
        per_asset_full[sym] = m_full
        pool_full_pnls.extend(pnls)
        pool_full_rets.extend(rets)
        pool_full_hold.extend(hold)
        total_days_full += td

        # IS
        df_is = df[df.index < split_date]
        if len(df_is) > 0:
            p_is, r_is, h_is = _run_one(df_is)
            pool_is_pnls.extend(p_is)
            pool_is_rets.extend(r_is)
            pool_is_hold.extend(h_is)
            total_days_is += len(df_is) * 365 / 252

        # OOS
        df_oos = df[df.index >= split_date]
        if len(df_oos) > 0:
            p_oos, r_oos, h_oos = _run_one(df_oos)
            pool_oos_pnls.extend(p_oos)
            pool_oos_rets.extend(r_oos)
            pool_oos_hold.extend(h_oos)
            total_days_oos += len(df_oos) * 365 / 252

    # Moyenner total_days sur le nombre d'assets (pool = concurrent trades)
    n_assets = len(SYMBOLS)
    avg_days_full = total_days_full / n_assets
    avg_days_is = total_days_is / n_assets
    avg_days_oos = total_days_oos / n_assets

    m_pool_full = _metrics(pool_full_pnls, pool_full_rets, pool_full_hold, avg_days_full)
    m_pool_is = _metrics(pool_is_pnls, pool_is_rets, pool_is_hold, avg_days_is)
    m_pool_oos = _metrics(pool_oos_pnls, pool_oos_rets, pool_oos_hold, avg_days_oos)

    # ── Rapport ──
    print()
    print("==============================================================")
    print(f"  RSI(2) Mean Reversion -- Portfolio {n_assets} ETFs -- Compte USD")
    print("==============================================================")
    print("  Per-asset (full period 2000-2025) :")
    for sym in SYMBOLS:
        m = per_asset_full[sym]
        print(f"  {sym:4s} : {_fmt(m)}")
    print("--------------------------------------------------------------")
    print(f"  Portfolio poole (full) : {_fmt(m_pool_full)}")
    print("--------------------------------------------------------------")
    print(f"  IS  ({START[:4]}-{IS_SPLIT[:4]}) : {_fmt(m_pool_is)}")
    print(f"  OOS ({IS_SPLIT[:4]}-{END[:4]}) : {_fmt(m_pool_oos)}")
    print("==============================================================")

    # Sanity checks
    print()
    n_oos = m_pool_oos["n_trades"]
    pf_oos = m_pool_oos["profit_factor"]
    sh_oos = m_pool_oos["sharpe"]
    wr_oos = m_pool_oos["win_rate"]

    checks = []
    if pf_oos >= 1.2:
        checks.append(f"  [OK] PF OOS = {pf_oos:.2f} >= 1.2")
    else:
        checks.append(f"  [!]  PF OOS = {pf_oos:.2f} < 1.2")
    if sh_oos >= 0.25:
        checks.append(f"  [OK] Sharpe OOS = {sh_oos:.2f} >= 0.25")
    else:
        checks.append(f"  [!]  Sharpe OOS = {sh_oos:.2f} < 0.25")
    if wr_oos >= 65:
        checks.append(f"  [OK] WR OOS = {wr_oos:.0f}% >= 65%")
    else:
        checks.append(f"  [!]  WR OOS = {wr_oos:.0f}% < 65%")
    if n_oos >= 250:
        checks.append(f"  [OK] {n_oos} trades OOS >= 250 (significatif)")
    else:
        checks.append(f"  [!]  {n_oos} trades OOS < 250 (masse insuffisante)")

    # Divergence per-asset
    wrs = [per_asset_full[s]["win_rate"] for s in SYMBOLS]
    worst_sym = SYMBOLS[int(np.argmin(wrs))]
    worst_wr = min(wrs)
    if worst_wr < 60:
        checks.append(f"  [!]  {worst_sym} WR = {worst_wr:.0f}% < 60% -- divergence")
    else:
        checks.append(f"  [OK] Tous les ETFs WR >= 60% (min: {worst_sym} {worst_wr:.0f}%)")

    for c in checks:
        print(c)
    print()


if __name__ == "__main__":
    main()
