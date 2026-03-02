"""Pipeline de validation orchestrant toutes les étapes.

Pour chaque asset dans un univers :
1. Charger données (YahooLoader)
2. Build cache avec strategy.param_grid() + defaults
3. Backtest OOS (params canoniques)
4. Robustesse paramétrique (cartésien param_grid)
5. Sous-périodes OOS
6. T-test
7. Verdict
8. T-test poolé
"""

from __future__ import annotations

import pandas as pd

from data.base_loader import to_cache_arrays
from data.yahoo_loader import YahooLoader
from engine.backtest_config import BacktestConfig
from engine.indicator_cache import build_cache
from engine.simulator import simulate
from strategies.base import BaseStrategy
from validation.config import ValidationConfig
from validation.report import (
    AssetValidation,
    ValidationReport,
    determine_verdict,
)
from validation.robustness import run_robustness
from validation.statistics import run_ttest
from validation.sub_periods import run_sub_periods


def _merge_grid_with_defaults(strategy: BaseStrategy) -> dict[str, list]:
    """Fusionne param_grid + default_params pour couverture cache complète.

    param_grid contient les clés swept (ex: sma_trend_period: [150, 200, 250]).
    default_params peut avoir des clés "period" supplémentaires non dans le grid
    (ex: adx_period=14, atr_period=14 pour Donchian). On les ajoute comme [valeur]
    pour que build_cache() pré-calcule les indicateurs correspondants.
    """
    grid = dict(strategy.param_grid())
    defaults = strategy.default_params()
    for key, value in defaults.items():
        if "period" in key and key not in grid and isinstance(value, (int, float)):
            grid[key] = [int(value)]
    return grid


def validate(
    strategy: BaseStrategy,
    config: ValidationConfig,
) -> ValidationReport:
    """Pipeline complet de validation d'une stratégie sur un univers.

    Args:
        strategy: Stratégie implémentant BaseStrategy
        config: Configuration de validation

    Returns:
        ValidationReport avec verdicts par asset et t-test poolé
    """
    loader = YahooLoader()
    cache_grid = _merge_grid_with_defaults(strategy)
    report = ValidationReport(strategy_name=strategy.name)

    all_oos_returns: list[float] = []

    for symbol, start_date in config.universe.items():
        print(f"  {symbol}...", end=" ", flush=True)

        # 1. Charger données
        df = loader.get_daily_candles(symbol, start_date, config.data_end)

        # 2. Trouver les indices OOS
        oos_start_idx = int(df.index.searchsorted(pd.Timestamp(config.is_end)))
        oos_end_idx = len(df)

        if config.oos_mid is not None:
            oos_mid_idx = int(df.index.searchsorted(pd.Timestamp(config.oos_mid)))
        else:
            oos_mid_idx = oos_start_idx + (oos_end_idx - oos_start_idx) // 2

        # 3. Build cache (full dataset, merged grid)
        arrays = to_cache_arrays(df)
        dates = df.index.values  # datetime64 array pour les stratégies calendaires
        cache = build_cache(arrays, cache_grid, dates=dates)

        # 4. BacktestConfig pour cet asset
        bt_config = BacktestConfig(
            symbol=symbol,
            initial_capital=config.initial_capital,
            slippage_pct=config.slippage_pct,
            fee_model=config.fee_model,
            whole_shares=config.whole_shares,
        )

        # 5. OOS backtest (params canoniques)
        oos_result = simulate(
            strategy, cache, strategy.default_params(), bt_config,
            start_idx=oos_start_idx, end_idx=oos_end_idx,
        )

        # 6. Robustesse paramétrique
        robustness = run_robustness(
            strategy, cache, bt_config,
            start_idx=oos_start_idx, end_idx=oos_end_idx,
            min_profitable_pct=config.min_profitable_pct,
            symbol=symbol,
        )

        # 7. Sous-périodes
        sub_periods = run_sub_periods(
            strategy, cache, bt_config,
            oos_start_idx=oos_start_idx,
            oos_mid_idx=oos_mid_idx,
            oos_end_idx=oos_end_idx,
            symbol=symbol,
        )

        # 8. T-test
        ttest = run_ttest(
            oos_result.returns,
            symbol=symbol,
            alpha=config.ttest_alpha,
        )

        # 9. Verdict
        verdict = determine_verdict(
            robustness, sub_periods, ttest,
            conditional_p_max=config.conditional_p_max,
        )

        report.assets.append(AssetValidation(
            symbol=symbol,
            oos_result=oos_result,
            robustness=robustness,
            sub_periods=sub_periods,
            ttest=ttest,
            verdict=verdict,
        ))

        all_oos_returns.extend(oos_result.returns)
        print(f"{oos_result.n_trades} trades, PF {oos_result.profit_factor:.2f}, "
              f"{verdict.value}")

    # 10. T-test poolé
    if all_oos_returns:
        report.pooled_ttest = run_ttest(
            all_oos_returns,
            symbol="POOLED",
            alpha=config.ttest_alpha,
        )

    return report
