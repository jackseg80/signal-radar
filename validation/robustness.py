"""Test de robustesse paramétrique (cartésien sur param_grid)."""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from statistics import median

from engine.backtest_config import BacktestConfig
from engine.indicator_cache import IndicatorCache
from engine.simulator import simulate
from strategies.base import BaseStrategy


@dataclass
class RobustnessResult:
    """Résultat du test de robustesse pour un asset."""

    symbol: str
    n_combos: int
    n_profitable: int           # combos avec PF > 1.0
    pct_profitable: float       # n_profitable / n_combos * 100
    best_pf: float
    worst_pf: float
    median_pf: float
    robust: bool                # pct_profitable >= threshold
    profit_factors: list[float] = field(default_factory=list)


def run_robustness(
    strategy: BaseStrategy,
    cache: IndicatorCache,
    config: BacktestConfig,
    *,
    start_idx: int,
    end_idx: int,
    min_profitable_pct: float = 80.0,
    min_trades: int = 3,
    symbol: str = "",
) -> RobustnessResult:
    """Teste toutes les combinaisons du param_grid sur une période.

    Génère le produit cartésien de strategy.param_grid(),
    merge chaque combo avec default_params(), run simulate().

    Args:
        strategy: Stratégie à tester
        cache: Cache indicateurs (doit couvrir toutes les périodes du grid)
        config: Configuration backtest
        start_idx: Début de la période (ex: OOS start)
        end_idx: Fin de la période
        min_profitable_pct: Seuil % combos profitables pour "robust"
        min_trades: Minimum de trades pour qu'une combo compte (sinon PF=0)
        symbol: Nom du symbole (pour le rapport)

    Returns:
        RobustnessResult avec distribution des PF
    """
    grid = strategy.param_grid()
    defaults = strategy.default_params()

    if not grid:
        return RobustnessResult(
            symbol=symbol, n_combos=0, n_profitable=0,
            pct_profitable=0.0, best_pf=0.0, worst_pf=0.0,
            median_pf=0.0, robust=False,
        )

    keys = list(grid.keys())
    values = [grid[k] for k in keys]

    profit_factors: list[float] = []

    for combo in product(*values):
        params = dict(defaults)
        params.update(zip(keys, combo))

        result = simulate(
            strategy, cache, params, config,
            start_idx=start_idx, end_idx=end_idx,
        )

        if result.n_trades >= min_trades:
            profit_factors.append(result.profit_factor)
        else:
            profit_factors.append(0.0)

    n_combos = len(profit_factors)
    n_profitable = sum(1 for pf in profit_factors if pf > 1.0)
    pct = n_profitable / n_combos * 100 if n_combos > 0 else 0.0

    return RobustnessResult(
        symbol=symbol,
        n_combos=n_combos,
        n_profitable=n_profitable,
        pct_profitable=pct,
        best_pf=max(profit_factors) if profit_factors else 0.0,
        worst_pf=min(profit_factors) if profit_factors else 0.0,
        median_pf=median(profit_factors) if profit_factors else 0.0,
        robust=pct >= min_profitable_pct,
        profit_factors=profit_factors,
    )
