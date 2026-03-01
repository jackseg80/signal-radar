"""RSI(2) Mean Reversion -- PORTFOLIO FINAL -- 5 ETFs.

Params production (Connors canonical + buffer 1.01 anti-whipsaw).
Split IS (2005-2014) / OOS (2014-2025).
Monte Carlo block bootstrap sur le pool OOS.
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
from optimization.overfit_detection import OverfitDetector

# --- Configuration -----------------------------------------------------------

UNIVERSE = ["SPY", "QQQ", "IWM", "DIA", "EFA"]

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
    "sma_trend_buffer":    1.01,   # anti-whipsaw, valide en Step 7
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


def _sharpe_from_rets(rets: list[float]) -> float:
    if len(rets) < 2:
        return 0.0
    arr = np.array(rets)
    std = float(np.std(arr))
    return float(np.mean(arr) / std) if std > 1e-10 else 0.0


# --- Main --------------------------------------------------------------------

def main() -> None:
    """Point d'entree : portfolio final 5 ETFs RSI(2)."""
    import pandas as pd  # noqa: PLC0415

    loader     = YahooLoader()
    split_date = pd.Timestamp(IS_SPLIT)

    # Accumulateurs pools
    pool_full_pnls: list[float] = []
    pool_full_rets:  list[float] = []
    pool_full_hold:  list[int]   = []
    pool_is_pnls:   list[float] = []
    pool_is_rets:    list[float] = []
    pool_is_hold:    list[int]   = []
    pool_oos_pnls:  list[float] = []
    pool_oos_rets:   list[float] = []
    pool_oos_hold:   list[int]   = []

    td_full_total = 0.0
    td_is_total   = 0.0
    td_oos_total  = 0.0

    per_asset: dict[str, dict] = {}

    for sym in UNIVERSE:
        print(f"  {sym} ...")
        df = loader.get_daily_candles(sym, START, END)
        n  = len(df)

        td_full = n * 365 / 252
        pnls_f, rets_f, hold_f = _run_one(df)
        per_asset[sym] = _metrics(pnls_f, rets_f, hold_f, td_full)

        pool_full_pnls.extend(pnls_f)
        pool_full_rets.extend(rets_f)
        pool_full_hold.extend(hold_f)
        td_full_total += td_full

        df_is  = df[df.index <  split_date]
        df_oos = df[df.index >= split_date]

        if len(df_is) > 200:
            p, r, h = _run_one(df_is)
            pool_is_pnls.extend(p)
            pool_is_rets.extend(r)
            pool_is_hold.extend(h)
            td_is_total += len(df_is) * 365 / 252

        if len(df_oos) > 200:
            p, r, h = _run_one(df_oos)
            pool_oos_pnls.extend(p)
            pool_oos_rets.extend(r)
            pool_oos_hold.extend(h)
            td_oos_total += len(df_oos) * 365 / 252

    n_assets = len(UNIVERSE)
    m_full = _metrics(pool_full_pnls, pool_full_rets, pool_full_hold,
                      td_full_total / n_assets)
    m_is   = _metrics(pool_is_pnls,  pool_is_rets,  pool_is_hold,
                      td_is_total   / n_assets)
    m_oos  = _metrics(pool_oos_pnls, pool_oos_rets, pool_oos_hold,
                      td_oos_total  / n_assets)

    # --- Monte Carlo sur OOS -------------------------------------------------
    obs_sharpe = _sharpe_from_rets(pool_oos_rets)
    detector   = OverfitDetector()
    mc = detector.monte_carlo_block_bootstrap(
        trade_pnls=pool_oos_pnls,
        trade_returns=pool_oos_rets,
        n_sims=5000,
        block_size=5,
        seed=42,
        observed_sharpe=obs_sharpe,
    )
    dist   = np.array(mc.distribution)
    ci_lo  = float(np.percentile(dist, 5))  if len(dist) > 0 else 0.0
    ci_hi  = float(np.percentile(dist, 95)) if len(dist) > 0 else 0.0
    sig    = "significatif" if mc.significant else "non-significatif"

    # --- Rapport -------------------------------------------------------------
    print()
    print("==============================================================")
    print("  RSI(2) Mean Reversion -- PORTFOLIO FINAL -- 5 ETFs")
    print("  Params: RSI<10, SMA(200)x1.01, SMA(5) exit, no SL")
    print("  Fees: USD account ($1 commission + 0.03% spread)")
    print("==============================================================")
    print("  Per-asset (full 2005-2025) :")
    for sym in UNIVERSE:
        if sym in per_asset:
            print(f"  {sym:4s} : {_fmt(per_asset[sym])}")
    print("--------------------------------------------------------------")
    print("  Portfolio poole :")
    print(f"  Full : {_fmt(m_full)}")
    print(f"  IS   : {_fmt(m_is)}")
    print(f"  OOS  : {_fmt(m_oos)}")
    print("--------------------------------------------------------------")
    print(f"  Monte Carlo OOS : p-value = {mc.p_value:.3f} ({sig})")
    print(f"  Sharpe observe  : {mc.real_sharpe:.2f}")
    print(f"  90%% CI Sharpe  : [{ci_lo:.2f}, {ci_hi:.2f}]")
    print(f"  Trades OOS      : {m_oos['n_trades']}")
    print("==============================================================")
    print()

    # Sanity checks
    pf_oos = m_oos["profit_factor"]
    sh_oos = m_oos["sharpe"]
    wr_oos = m_oos["win_rate"]
    nt_oos = m_oos["n_trades"]

    checks = [
        (pf_oos >= 1.2,  f"PF OOS = {pf_oos:.2f} (seuil 1.2)"),
        (sh_oos >= 0.25, f"Sharpe OOS = {sh_oos:.2f} (seuil 0.25)"),
        (wr_oos >= 65,   f"WR OOS = {wr_oos:.0f}% (seuil 65%)"),
        (nt_oos >= 250,  f"{nt_oos} trades OOS (seuil 250)"),
        (mc.significant, f"Monte Carlo p={mc.p_value:.3f} (seuil 0.05)"),
    ]
    for ok, label in checks:
        tag = "[OK]" if ok else "[!] "
        print(f"  {tag} {label}")
    print()

    # Retourner les metriques OOS pour la config
    return m_oos, mc


if __name__ == "__main__":
    main()
