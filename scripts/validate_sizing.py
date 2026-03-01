# DEPRECATED -- Remplace par: python -m cli.validate rsi2_stocks / rsi2_etfs
# Conserve comme reference historique Phase 2.
"""RSI(2) Sizing Impact -- $100k vs $10k, fractional vs whole shares.

Quantifie l'impact réel du sizing sur l'edge OOS (2014-2025) :
  1. Commission fixe ($1) pèse 10x plus sur petit capital
  2. Arrondi à l'entier inférieur → trades skippés et cash idle

Scénarios :
  1. $100k fractional  — baseline Phase 1
  2. $100k whole        — isoler l'impact du rounding seul
  3. $10k  fractional  — isoler l'impact du capital seul
  4. $10k  whole        — SCÉNARIO RÉEL (Jack sur Saxo)

Ne modifie aucun fichier existant.
Méthodologie identique à validate_rsi2_final.py (même split, même params).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.base_loader import to_cache_arrays
from data.yahoo_loader import YahooLoader
from engine.backtest_config import BacktestConfig
from engine.fast_backtest import _close_trend_position
from engine.fee_model import FEE_MODEL_US_ETFS_USD
from engine.indicator_cache import IndicatorCache, build_cache

# --- Configuration -----------------------------------------------------------

UNIVERSE  = ["SPY", "QQQ", "IWM", "DIA", "EFA"]
START     = "2005-01-01"
END       = "2025-01-01"
OOS_SPLIT = "2014-01-01"

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

SCENARIOS = [
    {"capital": 100_000.0, "whole": False, "label": "$100k fractional (baseline)   "},
    {"capital": 100_000.0, "whole": True,  "label": "$100k whole shares             "},
    {"capital":  10_000.0, "whole": False, "label": "$10k  fractional               "},
    {"capital":  10_000.0, "whole": True,  "label": "$10k  whole shares  [REEL]     "},
]


# --- Moteur local avec support whole_shares ----------------------------------

def _simulate_mr_sizing(
    cache: IndicatorCache,
    params: dict[str, Any],
    config: BacktestConfig,
    whole_shares: bool = False,
) -> tuple[list[float], list[float], float, int, list[float]]:
    """Copie de _simulate_mean_reversion avec paramètre whole_shares.

    Parameters
    ----------
    whole_shares : bool
        Si True : arrondi à l'entier inférieur, skip si quantity < 1.

    Returns
    -------
    (trade_pnls, trade_returns, final_capital, n_skipped, trade_sizes)
        trade_sizes : notionnel réel par trade (pour avg trade size).
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

    trade_pnls:   list[float] = []
    trade_returns: list[float] = []
    trade_sizes:  list[float] = []

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
            # Phase 1 : Gap SL
            if sl_pct > 0 and opens[i] <= sl_price:
                _exit(opens[i], i)
                continue
            # Phase 2 : Intraday SL
            if sl_pct > 0 and lows[i] <= sl_price:
                _exit(sl_price * (1 - slippage_pct), i)
                continue
            close_i = closes[i]
            # Phase 3 : SMA exit
            sma_ev = sma_exit[i]
            if not math.isnan(sma_ev) and close_i > sma_ev:
                _exit(close_i, i)
                continue
            # Phase 4 : RSI exit
            if rsi_exit_thr > 0:
                rv = rsi_arr[i]
                if not math.isnan(rv) and rv > rsi_exit_thr:
                    _exit(close_i, i)
                    continue
            # Phase 5 : Trend break
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

        if whole_shares:
            qty = math.floor(available / ep)
            if qty < 1:
                n_skipped += 1
                continue
            cap_alloc = qty * ep      # Capital réellement dépensé
        else:
            qty       = available / ep
            cap_alloc = available     # Fractional : tout le budget utilisé

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

    # Force-close fin de données (pas dans trade_pnls, convention)
    if in_position:
        pnl = _close_trend_position(
            1, entry_price, closes[n - 1], quantity,
            fee_model, entry_fee, (n - 1) - entry_candle,
        )
        capital += capital_allocated + pnl

    return trade_pnls, trade_returns, capital, n_skipped, trade_sizes


# --- Métriques ---------------------------------------------------------------

def _metrics(
    pnls:   list[float],
    rets:   list[float],
    sizes:  list[float],
    initial_capital: float,
    total_days: float,
    n_skipped: int,
) -> dict:
    """Calcule les métriques poolées pour un scénario."""
    nt  = len(pnls)
    nw  = sum(1 for p in pnls if p > 0)
    wr  = nw / nt * 100 if nt else 0.0
    pf_num = sum(p for p in pnls if p > 0)
    pf_den = abs(sum(p for p in pnls if p < 0))
    pf  = pf_num / pf_den if pf_den > 0 else float("inf")
    net = sum(pnls) / initial_capital * 100

    sharpe = 0.0
    if nt >= 3 and len(rets) >= 2:
        arr = np.array(rets)
        std = float(np.std(arr))
        if std > 1e-10:
            tpy = nt / max(total_days, 1) * 365 if total_days > 0 else nt
            sharpe = float(np.mean(arr) / std * np.sqrt(tpy))

    avg_pnl   = float(np.mean(pnls))  if pnls  else 0.0
    avg_size  = float(np.mean(sizes)) if sizes else 0.0

    return {
        "n_trades": nt, "win_rate": wr, "sharpe": sharpe,
        "profit_factor": pf, "net_return_pct": net,
        "avg_pnl": avg_pnl, "avg_size": avg_size, "n_skipped": n_skipped,
    }


# --- Main --------------------------------------------------------------------

def main() -> None:
    """Point d'entrée : validation sizing impact RSI(2) OOS 2014-2025."""
    import pandas as pd  # noqa: PLC0415

    loader     = YahooLoader()
    split_date = pd.Timestamp(OOS_SPLIT)

    # Chargement et build caches OOS
    print("Chargement données OOS (2014-2025)...")
    caches: dict[str, IndicatorCache] = {}
    for sym in UNIVERSE:
        df = loader.get_daily_candles(sym, START, END)
        df_oos = df[df.index >= split_date]
        arrays = to_cache_arrays(df_oos)
        caches[sym] = build_cache(arrays, CACHE_GRID)
        print(f"  {sym}: {len(df_oos)} barres OOS")

    print()

    # Exécution des 4 scénarios
    all_results = []
    per_asset_real: dict[str, dict] = {}   # Détail $10k whole shares

    for sc in SCENARIOS:
        cap   = sc["capital"]
        whole = sc["whole"]
        label = sc["label"]

        config = BacktestConfig(
            symbol="",
            initial_capital=cap,
            slippage_pct=0.0003,
            fee_model=FEE_MODEL_US_ETFS_USD,
        )

        pool_pnls:  list[float] = []
        pool_rets:  list[float] = []
        pool_sizes: list[float] = []
        total_skipped = 0
        total_days    = 0.0

        for sym in UNIVERSE:
            cache = caches[sym]
            pnls, rets, _, skipped, sizes = _simulate_mr_sizing(
                cache, PARAMS, config, whole_shares=whole,
            )
            pool_pnls.extend(pnls)
            pool_rets.extend(rets)
            pool_sizes.extend(sizes)
            total_skipped += skipped
            total_days    += cache.total_days

            # Détail par ETF pour le scénario réel seulement
            if whole and cap == 10_000.0:
                per_asset_real[sym] = {
                    "n_trades":  len(pnls),
                    "n_skipped": skipped,
                    "avg_size":  float(np.mean(sizes)) if sizes else 0.0,
                }

        m = _metrics(
            pool_pnls, pool_rets, pool_sizes,
            cap,
            total_days / len(UNIVERSE),
            total_skipped,
        )
        m["label"] = label
        all_results.append(m)

    # --- Tableau comparatif --------------------------------------------------
    print("=" * 75)
    print("  RSI(2) Sizing Impact — OOS 2014-2025 — 5 ETFs poolés")
    print("  Params Connors (RSI<10, SMA200x1.01, SMA5 exit)")
    print("  Fees: USD account ($1 commission + 0.03% spread)")
    print("=" * 75)
    hdr = f"  {'Scénario':<34} {'Trades':>6} {'WR':>5} {'PF':>5} {'Sharpe':>7} {'Net%':>7} {'AvgPnL$':>8}"
    print(hdr)
    print("  " + "-" * 72)
    for m in all_results:
        print(
            f"  {m['label']:<34}"
            f" {m['n_trades']:>6}"
            f" {m['win_rate']:>4.0f}%"
            f" {m['profit_factor']:>5.2f}"
            f" {m['sharpe']:>7.2f}"
            f" {m['net_return_pct']:>+6.1f}%"
            f" {m['avg_pnl']:>8.2f}"
        )
    print("=" * 75)

    # --- Détail par ETF — $10k whole shares ----------------------------------
    print()
    print("  Détail par ETF — $10k whole shares [SCÉNARIO RÉEL] :")
    print(f"  {'ETF':>5}  {'Trades':>6}  {'Skippés':>8}  {'Taille moy $':>13}")
    print("  " + "-" * 38)
    for sym, d in per_asset_real.items():
        print(
            f"  {sym:>5}"
            f"  {d['n_trades']:>6}"
            f"  {d['n_skipped']:>8}"
            f"  {d['avg_size']:>13.0f}"
        )

    # Note de frais
    real = all_results[3]
    print()
    print("  Note frais :")
    print(f"    Taille moy trade $10k : ${real['avg_size']:.0f}")
    if real["avg_size"] > 0:
        fee_pct = (1.0 + real["avg_size"] * 0.00015) / real["avg_size"] * 100
        fee_pct_100k = (all_results[0]["avg_size"] * 0.00015 + 1.0) / all_results[0]["avg_size"] * 100
        print(f"    Round-trip fee% $10k  : ~{fee_pct * 2:.3f}%")
        print(f"    Round-trip fee% $100k : ~{fee_pct_100k * 2:.3f}%")
    print()


if __name__ == "__main__":
    main()
