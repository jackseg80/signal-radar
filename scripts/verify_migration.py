"""Vérification migration — ancien moteur vs nouveau framework.

Prouve que simulate(RSI2MeanReversion(), ...) produit des PnL identiques
à _simulate_mean_reversion(cache, params, config).

Comparaison à $100k fractional (élimine les différences whole-share).
Compare trade par trade : PnL, nombre, WR, PF.

Écarts acceptables :
- return_pct différent (pnl/capital vs pnl/capital_allocated) → Sharpe diffère
- Arrondi float < $0.01

Écarts NON acceptables :
- PnL différent → bug dans le moteur ou la stratégie
- Nombre de trades différent → condition entry/exit différente
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ajouter le projet au path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import Any

from data.base_loader import to_cache_arrays
from data.yahoo_loader import YahooLoader
from engine.backtest_config import BacktestConfig
from engine.fee_model import FEE_MODEL_US_STOCKS_USD
from engine.indicator_cache import build_cache
from engine.mean_reversion_backtest import _simulate_mean_reversion
from engine.simulator import simulate
from strategies.rsi2_mean_reversion import RSI2MeanReversion


class _RSI2AlignedWarmup(RSI2MeanReversion):
    """RSI2 avec warmup aligné sur l'ancien moteur pour comparaison exacte.

    Ancien moteur : max(sma_trend, sma_exit, rsi+1) + 2 = 202
    Nouveau (BaseStrategy default) : max(periods) + 10 = 210

    Les indicateurs sont valides dès ~200. Le +2 vs +10 est juste un buffer.
    Pour la migration, on aligne sur 202 pour produire les mêmes trades.
    """

    def warmup(self, params: dict[str, Any]) -> int:
        return max(
            params.get("sma_trend_period", 200),
            params.get("sma_exit_period", 5),
            params.get("rsi_period", 2) + 1,
        ) + 2

# ── Configuration ──

SYMBOLS = {
    "META": "2012-06-01",
    "MSFT": "2005-01-01",
    "GOOGL": "2005-01-01",
    "NVDA": "2005-01-01",
}

END = "2025-01-01"
CAPITAL = 100_000.0
PNL_TOLERANCE = 0.02  # $0.02

# Params identiques entre ancien et nouveau
OLD_PARAMS = {
    "strategy_type": "mean_reversion",
    "rsi_period": 2,
    "rsi_entry_threshold": 10.0,
    "sma_trend_period": 200,
    "sma_exit_period": 5,
    "rsi_exit_threshold": 0.0,
    "sl_percent": 0.0,
    "position_fraction": 0.2,
    "cooldown_candles": 0,
    "sma_trend_buffer": 1.01,
}

CACHE_GRID = {
    "sma_trend_period": [200],
    "sma_exit_period": [5],
    "rsi_period": [2],
    "adx_period": [14],
    "atr_period": [14],
}


def main() -> None:
    """Compare ancien et nouveau moteur pour chaque symbole."""
    loader = YahooLoader()
    strategy = _RSI2AlignedWarmup()
    new_params = strategy.default_params()

    config = BacktestConfig(
        symbol="",
        initial_capital=CAPITAL,
        slippage_pct=0.0003,
        fee_model=FEE_MODEL_US_STOCKS_USD,
        whole_shares=False,  # Fractional pour comparaison exacte
    )

    sep = "=" * 64
    print(f"\n{sep}")
    print("  Migration Verification — RSI(2) OOS $100k fractional")
    print(sep)

    all_pass = True

    for sym, start in SYMBOLS.items():
        df = loader.get_daily_candles(sym, start, END)
        arrays = to_cache_arrays(df)
        cache = build_cache(arrays, CACHE_GRID)

        # ── Ancien moteur ──
        old_pnls, old_rets, old_final = _simulate_mean_reversion(
            cache, OLD_PARAMS, config,
        )

        # ── Nouveau moteur (warmup aligné via _RSI2AlignedWarmup) ──
        new_result = simulate(strategy, cache, new_params, config)
        new_pnls = new_result.pnls

        # ── Comparaison ──
        n_old = len(old_pnls)
        n_new = len(new_pnls)
        count_match = n_old == n_new

        max_diff = 0.0
        pnl_match = True
        first_mismatch = -1

        if count_match:
            for j, (op, np_) in enumerate(zip(old_pnls, new_pnls)):
                diff = abs(op - np_)
                max_diff = max(max_diff, diff)
                if diff > PNL_TOLERANCE:
                    pnl_match = False
                    first_mismatch = j
                    break

        passed = count_match and pnl_match
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False

        print(f"  {sym:<6} [{status}]  "
              f"old={n_old} trades, new={n_new} trades  "
              f"max_pnl_diff=${max_diff:.4f}")

        if not count_match:
            print(f"         !! Trade count mismatch: {n_old} vs {n_new}")
        elif not pnl_match:
            print(f"         !! PnL mismatch at trade {first_mismatch}: "
                  f"old=${old_pnls[first_mismatch]:.4f} "
                  f"new=${new_pnls[first_mismatch]:.4f}")

    print(sep)
    if all_pass:
        print("  MIGRATION VERIFIED [OK]")
    else:
        print("  MIGRATION FAILED [X] --- voir details ci-dessus")
    print(sep)

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
