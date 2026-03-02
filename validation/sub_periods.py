"""Test de stabilité sous-périodes OOS."""

from __future__ import annotations

from dataclasses import dataclass

from engine.backtest_config import BacktestConfig
from engine.indicator_cache import IndicatorCache
from engine.simulator import simulate
from strategies.base import BaseStrategy


@dataclass
class SubPeriodResult:
    """Résultat du test de stabilité pour un asset."""

    symbol: str
    # Période A (première moitié OOS)
    n_trades_a: int
    pf_a: float
    sharpe_a: float
    # Période B (deuxième moitié OOS)
    n_trades_b: int
    pf_b: float
    sharpe_b: float
    # Verdict
    stable: bool  # PF > 1.0 dans les deux sous-périodes


def run_sub_periods(
    strategy: BaseStrategy,
    cache: IndicatorCache,
    config: BacktestConfig,
    *,
    oos_start_idx: int,
    oos_mid_idx: int,
    oos_end_idx: int,
    symbol: str = "",
) -> SubPeriodResult:
    """Run backtest avec params canoniques sur deux sous-périodes OOS.

    Le cache est construit sur toute la période — les indicateurs (SMA 200)
    disposent de tout l'historique. Plus correct que de reconstruire le cache
    par sous-période (ancien pattern des scripts).

    Args:
        strategy: Stratégie à tester
        cache: Cache indicateurs (full dataset)
        config: Configuration backtest
        oos_start_idx: Début OOS
        oos_mid_idx: Milieu OOS (split)
        oos_end_idx: Fin OOS
        symbol: Nom du symbole

    Returns:
        SubPeriodResult avec PF et Sharpe par sous-période
    """
    params = strategy.default_params()

    # Période A
    result_a = simulate(
        strategy, cache, params, config,
        start_idx=oos_start_idx, end_idx=oos_mid_idx,
    )

    # Période B
    result_b = simulate(
        strategy, cache, params, config,
        start_idx=oos_mid_idx, end_idx=oos_end_idx,
    )

    pf_a = result_a.profit_factor
    pf_b = result_b.profit_factor

    return SubPeriodResult(
        symbol=symbol,
        n_trades_a=result_a.n_trades,
        pf_a=pf_a,
        sharpe_a=result_a.sharpe,
        n_trades_b=result_b.n_trades,
        pf_b=pf_b,
        sharpe_b=result_b.sharpe,
        stable=bool(pf_a > 1.0 and pf_b > 1.0),
    )
