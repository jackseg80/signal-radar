"""Phase 1 validation -- Step 7 -- run 2026-03-01
Results : 48/48 combos PF>1.0 (100%%), 42/48 PF>1.2 (88%%). Buffer 1.01 optimal.
Note : MC p-value artificielle (Sharpe annualise vs distribution non-annualisee).
See docs/PHASE1_RESULTS.md and validate_rsi2_final.py pour la correction.

Robustesse RSI(2) Mean Reversion -- OOS 2014-2025 -- 4 ETFs.

1. Monte Carlo block bootstrap (significativite statistique)
2. Sensibilite parametrique (48 combos sur OOS)
3. SMA buffer (whipsaw protection)
"""

from __future__ import annotations

import sys
from pathlib import Path
from itertools import product

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.base_loader import to_cache_arrays
from data.yahoo_loader import YahooLoader
from engine.backtest_config import BacktestConfig
from engine.fee_model import FEE_MODEL_US_ETFS_USD
from engine.indicator_cache import build_cache
from engine.mean_reversion_backtest import _simulate_mean_reversion
from optimization.overfit_detection import OverfitDetector

# ─── Configuration ───────────────────────────────────────────────────────────

SYMBOLS = ["SPY", "QQQ", "IWM", "DIA"]
START = "2000-01-01"
END = "2025-01-01"
OOS_START = "2014-01-01"

INITIAL_CAPITAL = 100_000.0

BASE_PARAMS = {
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

SENSITIVITY_GRID = {
    "rsi_entry_threshold": [5, 10, 15, 20],
    "sma_trend_period": [150, 200, 250],
    "sma_exit_period": [3, 5, 7, 10],
}

BUFFER_VALUES = [1.00, 1.01, 1.02]


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _load_oos_data() -> dict[str, "pd.DataFrame"]:
    """Charge les DataFrames OOS pour chaque symbole."""
    import pandas as pd  # noqa: PLC0415

    loader = YahooLoader()
    oos_start = pd.Timestamp(OOS_START)
    data = {}
    for sym in SYMBOLS:
        df = loader.get_daily_candles(sym, START, END)
        data[sym] = df[df.index >= oos_start]
        print(f"  {sym}: {len(data[sym])} candles OOS"
              f" ({data[sym].index[0].date()} -> {data[sym].index[-1].date()})")
    return data


def _build_sensitivity_cache_grid() -> dict[str, list]:
    """Construit le CACHE_GRID pour couvrir toutes les periodes de la grille."""
    return {
        "sma_trend_period": sorted(set(SENSITIVITY_GRID["sma_trend_period"])),
        "sma_exit_period": sorted(set(SENSITIVITY_GRID["sma_exit_period"])),
        "rsi_period": [2],
        "adx_period": [14],
        "atr_period": [14],
    }


def _pool_trades(
    oos_data: dict[str, "pd.DataFrame"],
    params: dict,
    cache_grid: dict | None = None,
) -> tuple[list[float], list[float], list[int]]:
    """Run MR sur chaque ETF et pool les trades."""
    if cache_grid is None:
        cache_grid = {
            "sma_trend_period": [params["sma_trend_period"]],
            "sma_exit_period": [params["sma_exit_period"]],
            "rsi_period": [2],
            "adx_period": [14],
            "atr_period": [14],
        }

    all_pnls: list[float] = []
    all_rets: list[float] = []
    all_hold: list[int] = []

    for sym, df_oos in oos_data.items():
        arrays = to_cache_arrays(df_oos)
        cache = build_cache(arrays, cache_grid)
        holding: list[int] = []
        pnls, rets, _ = _simulate_mean_reversion(cache, params, CONFIG, holding)
        all_pnls.extend(pnls)
        all_rets.extend(rets)
        all_hold.extend(holding)

    return all_pnls, all_rets, all_hold


def _sharpe(rets: list[float]) -> float:
    """Sharpe annualise depuis trade returns."""
    if len(rets) < 3:
        return 0.0
    arr = np.array(rets)
    std = float(np.std(arr))
    if std < 1e-10:
        return 0.0
    return float(np.mean(arr) / std * np.sqrt(len(arr)))


def _pf(pnls: list[float]) -> float:
    """Profit factor depuis pnls."""
    wins = sum(p for p in pnls if p > 0)
    losses = abs(sum(p for p in pnls if p < 0))
    return wins / losses if losses > 0 else float("inf")


# ─── Sections du rapport ─────────────────────────────────────────────────────

def _section_monte_carlo(
    oos_data: dict[str, "pd.DataFrame"],
) -> None:
    """Monte Carlo block bootstrap sur les trades OOS pools."""
    pnls, rets, _ = _pool_trades(oos_data, BASE_PARAMS)
    observed_sharpe = _sharpe(rets)

    detector = OverfitDetector()
    mc = detector.monte_carlo_block_bootstrap(
        trade_pnls=pnls,
        trade_returns=rets,
        n_sims=5000,
        block_size=5,
        seed=42,
        observed_sharpe=observed_sharpe,
    )

    # CI 90% sur la distribution bootstrap
    dist = np.array(mc.distribution)
    ci_lo = float(np.percentile(dist, 5)) if len(dist) > 0 else 0.0
    ci_hi = float(np.percentile(dist, 95)) if len(dist) > 0 else 0.0

    sig_label = "significatif" if mc.significant else "non-significatif"

    print("==============================================================")
    print("  RSI(2) Robustesse -- OOS 2014-2025 -- 4 ETFs -- Compte USD")
    print("==============================================================")
    print(f"  Monte Carlo : p-value = {mc.p_value:.3f} ({sig_label})")
    print(f"  Sharpe obs   : {mc.real_sharpe:.2f}")
    print(f"  90%% CI Sharpe: [{ci_lo:.2f}, {ci_hi:.2f}]")
    print(f"  Trades OOS   : {len(pnls)}")


def _section_sensitivity(
    oos_data: dict[str, "pd.DataFrame"],
) -> None:
    """Test de sensibilite : 48 combinaisons sur OOS."""
    cache_grid = _build_sensitivity_cache_grid()

    rsi_vals = SENSITIVITY_GRID["rsi_entry_threshold"]
    sma_trend_vals = SENSITIVITY_GRID["sma_trend_period"]
    sma_exit_vals = SENSITIVITY_GRID["sma_exit_period"]

    n_combos = len(rsi_vals) * len(sma_trend_vals) * len(sma_exit_vals)
    n_pf_above_1 = 0
    n_pf_above_12 = 0
    best_pf = 0.0
    best_combo = ""
    worst_pf = float("inf")
    worst_combo = ""

    results = []

    for rsi_t, sma_t, sma_e in product(rsi_vals, sma_trend_vals, sma_exit_vals):
        p = dict(BASE_PARAMS)
        p["rsi_entry_threshold"] = rsi_t
        p["sma_trend_period"] = sma_t
        p["sma_exit_period"] = sma_e

        pnls, rets, _ = _pool_trades(oos_data, p, cache_grid)
        pf_val = _pf(pnls)
        nt = len(pnls)
        wr = sum(1 for x in pnls if x > 0) / nt * 100 if nt > 0 else 0

        results.append((rsi_t, sma_t, sma_e, nt, wr, pf_val))

        if pf_val > 1.0:
            n_pf_above_1 += 1
        if pf_val > 1.2:
            n_pf_above_12 += 1

        label = f"RSI<{rsi_t}, SMA_trend={sma_t}, SMA_exit={sma_e}"
        if pf_val > best_pf:
            best_pf = pf_val
            best_combo = label
        if pf_val < worst_pf:
            worst_pf = pf_val
            worst_combo = label

    pct_1 = n_pf_above_1 / n_combos * 100
    pct_12 = n_pf_above_12 / n_combos * 100

    print("--------------------------------------------------------------")
    print(f"  Sensibilite : {n_pf_above_1}/{n_combos} combinaisons PF > 1.0 ({pct_1:.0f}%)")
    print(f"                {n_pf_above_12}/{n_combos} combinaisons PF > 1.2 ({pct_12:.0f}%)")
    print(f"  Meilleure : {best_combo} -> PF {best_pf:.2f}")
    print(f"  Pire      : {worst_combo} -> PF {worst_pf:.2f}")

    # Robustesse par dimension
    print("  ---")
    for dim_name, dim_vals in SENSITIVITY_GRID.items():
        dim_pfs = {}
        for val in dim_vals:
            matching = [r for r in results if (
                (dim_name == "rsi_entry_threshold" and r[0] == val) or
                (dim_name == "sma_trend_period" and r[1] == val) or
                (dim_name == "sma_exit_period" and r[2] == val)
            )]
            avg_pf = np.mean([r[5] for r in matching]) if matching else 0
            dim_pfs[val] = avg_pf
        parts = [f"{v}={pf:.2f}" for v, pf in dim_pfs.items()]
        print(f"  {dim_name:25s}: {', '.join(parts)}")


def _section_buffer(
    oos_data: dict[str, "pd.DataFrame"],
) -> None:
    """Test du SMA buffer."""
    print("--------------------------------------------------------------")
    print("  SMA Buffer :")

    for buf in BUFFER_VALUES:
        p = dict(BASE_PARAMS)
        p["sma_trend_buffer"] = buf
        pnls, rets, hold = _pool_trades(oos_data, p)
        nt = len(pnls)
        wr = sum(1 for x in pnls if x > 0) / nt * 100 if nt > 0 else 0
        pf_val = _pf(pnls)
        avg_h = float(np.mean(hold)) if hold else 0
        print(f"  buffer={buf:.2f} : {nt:3d} trades, WR {wr:.0f}%,"
              f" PF {pf_val:.2f}, hold {avg_h:.1f}j")

    print("==============================================================")
    print()


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    """Point d'entree du script de robustesse."""
    print("Chargement des donnees OOS ...")
    oos_data = _load_oos_data()
    print()

    _section_monte_carlo(oos_data)
    _section_sensitivity(oos_data)
    _section_buffer(oos_data)


if __name__ == "__main__":
    main()
