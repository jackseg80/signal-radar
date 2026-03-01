# DEPRECATED -- Remplace par: python -m cli.validate rsi2_stocks
# Conserve comme reference historique Phase 2.
"""RSI(2) Robustesse -- 6 stocks candidats (PF > 1.3 en OOS).

3 vérifications avant intégration au scanner :
  1. Robustesse paramétrique (48 combos RSI/SMA_trend/SMA_exit)
  2. Stabilité sous-périodes (OOS-A 2014-2019 / OOS-B 2019-2025)
  3. Significativité statistique (t-test par stock)

Méthodologie identique aux validations Phase 1.
Capital $10k, whole shares, FEE_MODEL_US_STOCKS_USD.
"""

from __future__ import annotations

import math
import sys
from itertools import product
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.base_loader import to_cache_arrays
from data.yahoo_loader import YahooLoader
from engine.backtest_config import BacktestConfig
from engine.fast_backtest import _close_trend_position
from engine.fee_model import FEE_MODEL_US_STOCKS_USD
from engine.indicator_cache import IndicatorCache, build_cache

# --- Configuration -----------------------------------------------------------

CANDIDATES: dict[str, str] = {
    "META":  "2012-06-01",
    "MSFT":  "2005-01-01",
    "GOOGL": "2005-01-01",
    "AMZN":  "2005-01-01",
    "NVDA":  "2005-01-01",
    "GS":    "2005-01-01",
}

END       = "2025-01-01"
IS_SPLIT  = "2014-01-01"
OOS_A_END = "2019-07-01"

INITIAL_CAPITAL = 10_000.0

# Grille de robustesse (4 × 3 × 4 = 48 combos)
RSI_THRESHOLDS     = [5, 10, 15, 20]
SMA_TREND_PERIODS  = [150, 200, 250]
SMA_EXIT_PERIODS   = [3, 5, 7, 10]

# Cache grid couvrant toutes les variantes
CACHE_GRID = {
    "sma_trend_period": SMA_TREND_PERIODS,
    "sma_exit_period":  SMA_EXIT_PERIODS,
    "rsi_period":       [2],
    "adx_period":       [14],
    "atr_period":       [14],
}

# Params canoniques (base pour les 3 vérifications)
BASE_PARAMS: dict[str, Any] = {
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

CONFIG = BacktestConfig(
    symbol="",
    initial_capital=INITIAL_CAPITAL,
    slippage_pct=0.0003,
    fee_model=FEE_MODEL_US_STOCKS_USD,
)


# --- Moteur local avec whole shares ------------------------------------------

def _simulate_mr_whole(
    cache: IndicatorCache,
    params: dict[str, Any],
    config: BacktestConfig,
) -> tuple[list[float], list[float], int]:
    """Copie de _simulate_mean_reversion avec whole shares (floor).

    Returns
    -------
    (trade_pnls, trade_returns, n_skipped)
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

        sl_price     = ep * (1 - sl_pct) if sl_pct > 0 else 0.0
        in_position  = True
        entry_candle = i

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

    return trade_pnls, trade_returns, n_skipped


# --- Helpers -----------------------------------------------------------------

def _profit_factor(pnls: list[float]) -> float:
    """Calcule le profit factor."""
    gains = sum(p for p in pnls if p > 0)
    losses = abs(sum(p for p in pnls if p < 0))
    return gains / losses if losses > 0 else float("inf")


def _sharpe(rets: list[float], total_days: float, n_trades: int) -> float:
    """Calcule le Sharpe annualisé."""
    if n_trades < 3 or len(rets) < 2:
        return 0.0
    arr = np.array(rets)
    std = float(np.std(arr))
    if std < 1e-10:
        return 0.0
    tpy = n_trades / max(total_days, 1) * 365
    return float(np.mean(arr) / std * np.sqrt(tpy))


# --- Main --------------------------------------------------------------------

def main() -> None:
    """Point d'entrée : robustesse 6 stocks candidats RSI(2)."""
    import pandas as pd  # noqa: PLC0415

    loader     = YahooLoader()
    split_date = pd.Timestamp(IS_SPLIT)
    oos_a_end  = pd.Timestamp(OOS_A_END)

    # Chargement données OOS complètes + build caches
    print("  Chargement données...")
    oos_data: dict[str, pd.DataFrame] = {}
    oos_caches: dict[str, IndicatorCache] = {}

    for sym, start in CANDIDATES.items():
        df = loader.get_daily_candles(sym, start, END)
        df_oos = df[df.index >= split_date]
        oos_data[sym] = df_oos
        arrays = to_cache_arrays(df_oos)
        oos_caches[sym] = build_cache(arrays, CACHE_GRID)
        print(f"    {sym}: {len(df_oos)} barres OOS")

    # ═══════════════════════════════════════════════════════════════════════
    # Vérification 1 — Robustesse paramétrique (48 combos)
    # ═══════════════════════════════════════════════════════════════════════
    print()
    print("=" * 72)
    print("  V1 — Robustesse parametrique — OOS 2014-2025 — $10k whole shares")
    print("  48 combos : RSI {5,10,15,20} x SMA_trend {150,200,250}"
          " x SMA_exit {3,5,7,10}")
    print("=" * 72)

    combos = list(product(RSI_THRESHOLDS, SMA_TREND_PERIODS, SMA_EXIT_PERIODS))
    robustness: dict[str, dict] = {}

    for sym in CANDIDATES:
        cache = oos_caches[sym]
        pfs: list[float] = []

        for rsi_thr, sma_tp, sma_ep in combos:
            params = dict(BASE_PARAMS)
            params["rsi_entry_threshold"] = float(rsi_thr)
            params["sma_trend_period"] = sma_tp
            params["sma_exit_period"] = sma_ep
            pnls, _, _ = _simulate_mr_whole(cache, params, CONFIG)
            pf = _profit_factor(pnls) if len(pnls) >= 3 else 0.0
            pfs.append(pf)

        n_profitable = sum(1 for pf in pfs if pf > 1.0)
        pct = n_profitable / len(combos) * 100
        pfs_arr = np.array(pfs)
        robustness[sym] = {
            "n_profitable": n_profitable,
            "pct": pct,
            "best": float(np.max(pfs_arr)),
            "worst": float(np.min(pfs_arr)),
            "median": float(np.median(pfs_arr)),
            "robust": pct >= 80.0,
        }

    hdr = (f"  {'Ticker':<8} {'Combos PF>1':>12} {'%Profitable':>12}"
           f" {'Best PF':>8} {'Worst PF':>9} {'Median PF':>10}")
    print(hdr)
    print("  " + "-" * 69)
    for sym, r in robustness.items():
        tag = "OK" if r["robust"] else "!!"
        print(
            f"  {sym:<8}"
            f" {r['n_profitable']:>3}/48      "
            f" {r['pct']:>10.0f}%"
            f" {r['best']:>8.2f}"
            f" {r['worst']:>9.2f}"
            f" {r['median']:>10.2f}"
            f"  [{tag}]"
        )
    print("=" * 72)
    print("  Seuil : >80% combos profitables = ROBUSTE")

    # ═══════════════════════════════════════════════════════════════════════
    # Vérification 2 — Stabilité sous-périodes
    # ═══════════════════════════════════════════════════════════════════════
    print()
    print("=" * 72)
    print("  V2 — Stabilite sous-periodes — Params canoniques — $10k whole")
    print("  OOS-A : 2014-01 -> 2019-06  |  OOS-B : 2019-07 -> 2025-01")
    print("=" * 72)

    stability: dict[str, dict] = {}

    for sym in CANDIDATES:
        df_oos = oos_data[sym]

        # OOS-A
        df_a = df_oos[df_oos.index < oos_a_end]
        if len(df_a) >= 210:
            arr_a = to_cache_arrays(df_a)
            cache_a = build_cache(arr_a, CACHE_GRID)
            pnls_a, rets_a, _ = _simulate_mr_whole(cache_a, BASE_PARAMS, CONFIG)
            td_a = len(df_a) * 365 / 252
            pf_a = _profit_factor(pnls_a) if len(pnls_a) >= 3 else 0.0
            sh_a = _sharpe(rets_a, td_a, len(pnls_a))
            nt_a = len(pnls_a)
        else:
            pf_a, sh_a, nt_a = 0.0, 0.0, 0

        # OOS-B
        df_b = df_oos[df_oos.index >= oos_a_end]
        if len(df_b) >= 210:
            arr_b = to_cache_arrays(df_b)
            cache_b = build_cache(arr_b, CACHE_GRID)
            pnls_b, rets_b, _ = _simulate_mr_whole(cache_b, BASE_PARAMS, CONFIG)
            td_b = len(df_b) * 365 / 252
            pf_b = _profit_factor(pnls_b) if len(pnls_b) >= 3 else 0.0
            sh_b = _sharpe(rets_b, td_b, len(pnls_b))
            nt_b = len(pnls_b)
        else:
            pf_b, sh_b, nt_b = 0.0, 0.0, 0

        stable = pf_a > 1.0 and pf_b > 1.0
        stability[sym] = {
            "nt_a": nt_a, "pf_a": pf_a, "sh_a": sh_a,
            "nt_b": nt_b, "pf_b": pf_b, "sh_b": sh_b,
            "stable": stable,
        }

    print(f"  {'Ticker':<8}"
          f" {'OOS-A (14-19)':^24} {'OOS-B (19-25)':^24} {'Stable?':>8}")
    print(f"  {'':8}"
          f" {'Trades':>7} {'PF':>6} {'Sharpe':>7}"
          f" {'Trades':>9} {'PF':>6} {'Sharpe':>7} {'':>8}")
    print("  " + "-" * 69)
    for sym, s in stability.items():
        tag = "OUI" if s["stable"] else "NON"
        icon = "v" if s["stable"] else "x"
        print(
            f"  {sym:<8}"
            f" {s['nt_a']:>7} {s['pf_a']:>6.2f} {s['sh_a']:>7.2f}"
            f" {s['nt_b']:>9} {s['pf_b']:>6.2f} {s['sh_b']:>7.2f}"
            f"   [{icon}] {tag}"
        )
    print("=" * 72)
    print("  Seuil : PF > 1.0 dans les DEUX sous-periodes = STABLE")

    # ═══════════════════════════════════════════════════════════════════════
    # Vérification 3 — T-test par stock
    # ═══════════════════════════════════════════════════════════════════════
    print()
    print("=" * 72)
    print("  V3 — T-test significativite — OOS 2014-2025 — $10k whole shares")
    print("=" * 72)

    ttest_results: dict[str, dict] = {}

    for sym in CANDIDATES:
        cache = oos_caches[sym]
        pnls, rets, _ = _simulate_mr_whole(cache, BASE_PARAMS, CONFIG)
        nt = len(rets)
        if nt >= 3:
            arr = np.array(rets)
            mean_ret = float(np.mean(arr) * 100)
            t_stat, p_two = stats.ttest_1samp(arr, 0.0)
            p_val = float(p_two / 2) if t_stat > 0 else 1.0
        else:
            mean_ret, t_stat, p_val = 0.0, 0.0, 1.0

        if p_val < 0.05:
            sig = "OUI (p<0.05)"
        elif p_val < 0.10:
            sig = "MARGINAL (p<0.10)"
        else:
            sig = "NON"

        ttest_results[sym] = {
            "n_trades": nt, "mean_ret": mean_ret,
            "t_stat": float(t_stat), "p_val": p_val,
            "sig_label": sig, "sig": p_val < 0.10,
        }

    hdr = (f"  {'Ticker':<8} {'Trades':>7} {'Mean Ret%':>10}"
           f" {'t-stat':>8} {'p-value':>9} {'Significatif?':>20}")
    print(hdr)
    print("  " + "-" * 69)
    for sym, t in ttest_results.items():
        print(
            f"  {sym:<8}"
            f" {t['n_trades']:>7}"
            f" {t['mean_ret']:>+9.3f}%"
            f" {t['t_stat']:>8.2f}"
            f" {t['p_val']:>9.4f}"
            f"   {t['sig_label']}"
        )
    print("=" * 72)
    print("  Seuil : p < 0.10 (peu de trades par stock -> puissance faible)")

    # ═══════════════════════════════════════════════════════════════════════
    # Matrice de décision
    # ═══════════════════════════════════════════════════════════════════════
    print()
    print("=" * 72)
    print("  MATRICE DE DECISION — Candidats scanner")
    print("=" * 72)
    hdr = (f"  {'Ticker':<8} {'Param Robust':>13} {'Stable':>8}"
           f" {'Signif':>8} {'VERDICT':>10}")
    print(hdr)
    print("  " + "-" * 52)

    validated: list[str] = []
    for sym in CANDIDATES:
        r = robustness[sym]
        s = stability[sym]
        t = ttest_results[sym]

        r_ok = r["robust"]
        s_ok = s["stable"]
        t_ok = t["sig"]

        r_tag = f"{r['pct']:.0f}% {'v' if r_ok else 'x'}"
        s_tag = "v" if s_ok else "x"
        t_tag = "v" if t_ok else "x"

        if r_ok and s_ok and t_ok:
            verdict = "VALIDE"
            validated.append(sym)
        elif r_ok and s_ok and t["p_val"] < 0.15:
            verdict = "CONDITIONNEL"
        else:
            verdict = "REJETE"

        print(
            f"  {sym:<8}"
            f" {r_tag:>13}"
            f" {s_tag:>8}"
            f" {t_tag:>8}"
            f"   {verdict}"
        )

    print("=" * 72)
    print("  Criteres VALIDE   : robust >80% ET stable ET p<0.10")
    print("  Criteres REJETE   : robust <80% OU instable OU p>0.10")
    print()
    if validated:
        print(f"  >> Actions validees pour le scanner : {', '.join(validated)}")
    else:
        print("  >> Aucune action validee pour le scanner.")
    print()

    return robustness, stability, ttest_results


if __name__ == "__main__":
    main()
