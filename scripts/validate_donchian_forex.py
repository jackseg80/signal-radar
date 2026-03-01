"""Validation Donchian 50/20 Trend Following sur 7 paires forex majeures.

Params fixes (Turtle Traders style), long+short, ADX filter.
Split IS (2003-2015) / OOS (2015-2025).
Fee model : forex_majors (spread ~1 pip, pas de commission).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.base_loader import to_cache_arrays
from data.yahoo_loader import YahooLoader
from engine.backtest_config import BacktestConfig
from engine.fast_backtest import _simulate_trend_follow, _compute_fast_metrics
from engine.fee_model import FEE_MODEL_FOREX
from engine.indicator_cache import build_cache

# ─── Configuration ───────────────────────────────────────────────────────────

SYMBOLS = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X",
    "AUDUSD=X", "NZDUSD=X", "USDCAD=X",
]
# Short labels for display
SHORT_NAMES = {
    "EURUSD=X": "EURUSD", "GBPUSD=X": "GBPUSD", "USDJPY=X": "USDJPY",
    "USDCHF=X": "USDCHF", "AUDUSD=X": "AUDUSD", "NZDUSD=X": "NZDUSD",
    "USDCAD=X": "USDCAD",
}

START = "2003-01-01"
END = "2025-01-01"
IS_SPLIT = "2015-01-01"

INITIAL_CAPITAL = 100_000.0

CACHE_GRID = {
    "donchian_entry_period": [50],
    "donchian_exit_period": [20],
    "adx_period": [14],
    "atr_period": [14],
}

PARAMS = {
    "entry_mode": "donchian",
    "donchian_entry_period": 50,
    "donchian_exit_period": 20,
    "adx_period": 14,
    "adx_threshold": 25.0,
    "atr_period": 14,
    "trailing_atr_mult": 3.0,
    "exit_mode": "trailing",
    "sl_percent": 10.0,
    "position_fraction": 0.2,
    "cooldown_candles": 3,
    "sides": ["long", "short"],
}

CONFIG = BacktestConfig(
    symbol="",
    initial_capital=INITIAL_CAPITAL,
    slippage_pct=0.0003,
    fee_model=FEE_MODEL_FOREX,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _run_one(df: "pd.DataFrame") -> tuple[list[float], list[float]]:
    """Run trend-follow sur un DataFrame, retourne (pnls, returns)."""
    arrays = to_cache_arrays(df)
    cache = build_cache(arrays, CACHE_GRID)
    pnls, rets, _ = _simulate_trend_follow(cache, PARAMS, CONFIG)
    return pnls, rets


def _metrics(
    pnls: list[float],
    rets: list[float],
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

    return {
        "n_trades": nt, "win_rate": wr, "sharpe": sharpe,
        "profit_factor": pf, "net_return_pct": net_ret,
    }


def _fmt(m: dict) -> str:
    """Formate une ligne de metriques."""
    return (f"{m['n_trades']:3d} trades, WR {m['win_rate']:.0f}%,"
            f" Sharpe {m['sharpe']:.2f}, PF {m['profit_factor']:.2f},"
            f" Net {m['net_return_pct']:+.1f}%")


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    """Point d'entree du script de validation Donchian forex."""
    import pandas as pd  # noqa: PLC0415

    loader = YahooLoader()
    split_date = pd.Timestamp(IS_SPLIT)

    per_pair_full: dict[str, dict] = {}
    pool_full_pnls: list[float] = []
    pool_full_rets: list[float] = []
    pool_is_pnls: list[float] = []
    pool_is_rets: list[float] = []
    pool_oos_pnls: list[float] = []
    pool_oos_rets: list[float] = []

    total_days_full = 0.0
    total_days_is = 0.0
    total_days_oos = 0.0

    for sym in SYMBOLS:
        short = SHORT_NAMES.get(sym, sym)
        print(f"Chargement {short} ...")
        try:
            df = loader.get_daily_candles(sym, START, END)
        except Exception as e:
            print(f"  [!] Erreur chargement {short}: {e}")
            continue

        n_candles = len(df)
        print(f"  {n_candles} candles ({df.index[0].date()} -> {df.index[-1].date()})")

        # Full period
        pnls, rets = _run_one(df)
        td = n_candles * 365 / 252
        m_full = _metrics(pnls, rets, td)
        per_pair_full[short] = m_full
        pool_full_pnls.extend(pnls)
        pool_full_rets.extend(rets)
        total_days_full += td

        # IS
        df_is = df[df.index < split_date]
        if len(df_is) > 200:
            p_is, r_is = _run_one(df_is)
            pool_is_pnls.extend(p_is)
            pool_is_rets.extend(r_is)
            total_days_is += len(df_is) * 365 / 252

        # OOS
        df_oos = df[df.index >= split_date]
        if len(df_oos) > 200:
            p_oos, r_oos = _run_one(df_oos)
            pool_oos_pnls.extend(p_oos)
            pool_oos_rets.extend(r_oos)
            total_days_oos += len(df_oos) * 365 / 252

    n_pairs = len(per_pair_full)
    if n_pairs == 0:
        print("\n  [!] Aucune paire chargee. Abandon.")
        return

    avg_days_full = total_days_full / n_pairs
    avg_days_is = total_days_is / n_pairs if total_days_is > 0 else 1
    avg_days_oos = total_days_oos / n_pairs if total_days_oos > 0 else 1

    m_pool_full = _metrics(pool_full_pnls, pool_full_rets, avg_days_full)
    m_pool_is = _metrics(pool_is_pnls, pool_is_rets, avg_days_is)
    m_pool_oos = _metrics(pool_oos_pnls, pool_oos_rets, avg_days_oos)

    # ── Rapport ──
    print()
    print("==============================================================")
    print(f"  Donchian 50/20 -- Forex {n_pairs} paires -- Long+Short")
    print("==============================================================")
    print("  Per-pair (full period 2003-2025) :")
    for sym in SYMBOLS:
        short = SHORT_NAMES.get(sym, sym)
        if short in per_pair_full:
            m = per_pair_full[short]
            print(f"  {short:6s} : {_fmt(m)}")
    print("--------------------------------------------------------------")
    print(f"  Portfolio poole :")
    print(f"  Full          : {_fmt(m_pool_full)}")
    print(f"  IS  ({START[:4]}-{IS_SPLIT[:4]}) : {_fmt(m_pool_is)}")
    print(f"  OOS ({IS_SPLIT[:4]}-{END[:4]}) : {_fmt(m_pool_oos)}")
    print("==============================================================")

    # Sanity checks
    print()
    n_oos = m_pool_oos["n_trades"]
    pf_oos = m_pool_oos["profit_factor"]
    wr_oos = m_pool_oos["win_rate"]

    # Trend following a un win rate bas (~35-45%) mais de gros winners
    if pf_oos >= 1.0:
        print(f"  [OK] PF OOS = {pf_oos:.2f} >= 1.0")
    else:
        print(f"  [!]  PF OOS = {pf_oos:.2f} < 1.0")
    if n_oos >= 50:
        print(f"  [OK] {n_oos} trades OOS (masse suffisante)")
    else:
        print(f"  [!]  {n_oos} trades OOS (masse faible)")

    # Paires divergentes
    for short, m in per_pair_full.items():
        if m["n_trades"] < 5:
            print(f"  [!]  {short}: seulement {m['n_trades']} trades (trop peu)")
    print()


if __name__ == "__main__":
    main()
