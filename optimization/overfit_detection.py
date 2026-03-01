"""Détection d'overfitting multi-méthodes pour signal-radar.

Méthodes :
1. Monte Carlo block bootstrap (corrélation temporelle)
2. Deflated Sharpe Ratio — Bailey & Lopez de Prado (2014)
3. Parameter stability (perturbation analysis)
4. Cross-asset convergence (coefficient de variation)

Adapté depuis scalp-radar — suppression du coupling crypto/DB/backtesting.
La stabilité paramétrique utilise run_backtest_from_cache() directement.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
from loguru import logger

from engine.backtest_config import BacktestConfig
from engine.fast_backtest import run_backtest_from_cache
from engine.indicator_cache import IndicatorCache


# ─── Dataclasses résultat ──────────────────────────────────────────────────


@dataclass
class MonteCarloResult:
    p_value: float
    real_sharpe: float
    distribution: list[float]
    significant: bool  # p_value < 0.05
    underpowered: bool = False  # True si < 30 trades


@dataclass
class DSRResult:
    dsr: float
    max_expected_sharpe: float
    observed_sharpe: float
    n_trials: int


@dataclass
class StabilityResult:
    stability_map: dict[str, float]  # param_name → score 0-1
    overall_stability: float
    cliff_params: list[str]


@dataclass
class ConvergenceResult:
    convergence_score: float
    param_scores: dict[str, float]
    divergent_params: list[str]


@dataclass
class OverfitReport:
    monte_carlo: MonteCarloResult
    dsr: DSRResult
    stability: StabilityResult
    convergence: ConvergenceResult | None  # None si un seul asset


# ─── OverfitDetector ───────────────────────────────────────────────────────


class OverfitDetector:
    """Détection d'overfitting multi-méthodes."""

    def full_analysis(
        self,
        trade_pnls: list[float],
        trade_returns: list[float],
        observed_sharpe: float,
        n_distinct_combos: int,
        optimal_params: dict[str, Any],
        cache: IndicatorCache,
        config: BacktestConfig,
        all_symbols_results: dict[str, dict[str, Any]] | None = None,
        seed: int | None = 42,
    ) -> OverfitReport:
        """Analyse complète : Monte Carlo + DSR + stabilité + convergence."""
        mc = self.monte_carlo_block_bootstrap(
            trade_pnls, trade_returns, seed=seed,
            observed_sharpe=observed_sharpe,
        )
        dsr = self.deflated_sharpe_ratio(
            observed_sharpe, n_distinct_combos, len(trade_pnls),
            trade_returns,
        )
        stability = self.parameter_stability(
            optimal_params, cache, config,
        )
        convergence = None
        if all_symbols_results and len(all_symbols_results) >= 2:
            convergence = self.cross_asset_convergence(all_symbols_results)

        return OverfitReport(
            monte_carlo=mc,
            dsr=dsr,
            stability=stability,
            convergence=convergence,
        )

    def monte_carlo_block_bootstrap(
        self,
        trade_pnls: list[float],
        trade_returns: list[float],
        n_sims: int = 1000,
        block_size: int = 10,
        seed: int | None = 42,
        observed_sharpe: float | None = None,
    ) -> MonteCarloResult:
        """Circular block bootstrap avec resample (tirage avec remplacement).

        Block size = 10 jours (2 semaines de trading) pour préserver
        l'autocorrélation entre trades Donchian (durée 2-6 semaines).

        - < 5 trades : pas de test (p=1.0, underpowered)
        - < 30 trades : underpowered (p=0.50, score neutre)
        - >= 30 trades : test MC complet
        """
        if len(trade_returns) < 5:
            return MonteCarloResult(
                p_value=1.0,
                real_sharpe=observed_sharpe if observed_sharpe is not None else 0.0,
                distribution=[], significant=False,
                underpowered=True,
            )

        n_trades = len(trade_returns)

        if n_trades < 30:
            real_sharpe = observed_sharpe if observed_sharpe is not None else self._sharpe_from_returns(trade_returns)
            return MonteCarloResult(
                p_value=0.50, real_sharpe=real_sharpe, distribution=[],
                significant=False, underpowered=True,
            )

        trades_sharpe = self._sharpe_from_returns(trade_returns)
        real_sharpe = observed_sharpe if observed_sharpe is not None else trades_sharpe

        blocks = []
        for i in range(0, len(trade_returns), block_size):
            blocks.append(trade_returns[i:i + block_size])

        n_blocks = len(blocks)
        rng = np.random.default_rng(seed)
        distribution = []

        for _ in range(n_sims):
            sampled_indices = rng.integers(0, n_blocks, size=n_blocks)
            bootstrapped_returns = []
            for idx in sampled_indices:
                bootstrapped_returns.extend(blocks[idx])
            sim_sharpe = self._sharpe_from_returns(bootstrapped_returns)
            distribution.append(sim_sharpe)

        p_value = sum(1 for s in distribution if s >= real_sharpe) / max(len(distribution), 1)

        return MonteCarloResult(
            p_value=p_value,
            real_sharpe=real_sharpe,
            distribution=distribution,
            significant=p_value < 0.05,
        )

    def deflated_sharpe_ratio(
        self,
        observed_sharpe: float,
        n_trials: int,
        n_trades: int,
        trade_returns: list[float],
    ) -> DSRResult:
        """Bailey & Lopez de Prado (2014).

        Corrige le Sharpe pour le data mining (multiple testing).
        n_trials = nombre de combinaisons DISTINCTES testées.
        """
        if n_trades < 5 or n_trials < 2:
            return DSRResult(
                dsr=0.0, max_expected_sharpe=0.0,
                observed_sharpe=observed_sharpe, n_trials=n_trials,
            )

        returns = np.array(trade_returns)
        skewness = float(self._skewness(returns))
        kurtosis = float(self._kurtosis(returns))

        e_max_sr = self._expected_max_sharpe(n_trials)

        excess_kurtosis = kurtosis - 3.0
        denom_sq = (
            1
            - skewness * observed_sharpe
            + (excess_kurtosis - 1) / 4 * observed_sharpe ** 2
        )
        if denom_sq <= 0:
            denom_sq = 1e-6

        z = (
            (observed_sharpe - e_max_sr)
            * np.sqrt(n_trades - 1)
            / np.sqrt(denom_sq)
        )
        dsr = float(_norm_cdf(z))

        return DSRResult(
            dsr=dsr,
            max_expected_sharpe=e_max_sr,
            observed_sharpe=observed_sharpe,
            n_trials=n_trials,
        )

    def parameter_stability(
        self,
        optimal_params: dict[str, Any],
        cache: IndicatorCache,
        config: BacktestConfig,
        perturbation_pcts: list[float] | None = None,
    ) -> StabilityResult:
        """Perturbe chaque paramètre de ±pct et mesure l'impact sur le Sharpe."""
        if perturbation_pcts is None:
            perturbation_pcts = [0.10, 0.20]

        # Sharpe de référence
        try:
            _, ref_sharpe, _, _, _ = run_backtest_from_cache(
                optimal_params, cache, config,
            )
        except Exception:
            return StabilityResult(
                stability_map={p: 0.5 for p in optimal_params},
                overall_stability=0.5,
                cliff_params=[],
            )

        stability_map: dict[str, float] = {}

        for param_name, param_value in optimal_params.items():
            if not isinstance(param_value, (int, float)):
                stability_map[param_name] = 1.0
                continue
            if param_value == 0:
                stability_map[param_name] = 1.0
                continue

            max_drop = 0.0
            for pct in perturbation_pcts:
                for direction in [-1, 1]:
                    perturbed_value = param_value * (1 + direction * pct)
                    if isinstance(param_value, int):
                        perturbed_value = max(1, round(perturbed_value))
                    else:
                        perturbed_value = max(0.01, perturbed_value)

                    perturbed_params = dict(optimal_params)
                    perturbed_params[param_name] = perturbed_value

                    try:
                        _, p_sharpe, _, _, _ = run_backtest_from_cache(
                            perturbed_params, cache, config,
                        )
                        ref_abs = max(abs(ref_sharpe), 0.1)
                        drop = max(0, (ref_sharpe - p_sharpe) / ref_abs)
                        max_drop = max(max_drop, drop)
                    except Exception:
                        max_drop = max(max_drop, 0.5)

            stability_map[param_name] = max(0.0, min(1.0, 1.0 - max_drop))

        scores = list(stability_map.values())
        overall = float(np.mean(scores)) if scores else 0.0
        cliff_params = [p for p, s in stability_map.items() if s < 0.5]

        return StabilityResult(
            stability_map=stability_map,
            overall_stability=overall,
            cliff_params=cliff_params,
        )

    def cross_asset_convergence(
        self,
        optimal_params_by_symbol: dict[str, dict[str, Any]],
    ) -> ConvergenceResult:
        """Compare les paramètres optimaux entre assets."""
        if len(optimal_params_by_symbol) < 2:
            return ConvergenceResult(
                convergence_score=1.0, param_scores={}, divergent_params=[],
            )

        all_keys: set[str] = set()
        for params in optimal_params_by_symbol.values():
            for k, v in params.items():
                if isinstance(v, (int, float)):
                    all_keys.add(k)

        param_scores: dict[str, float] = {}
        for key in sorted(all_keys):
            values = []
            for params in optimal_params_by_symbol.values():
                if key in params and isinstance(params[key], (int, float)):
                    values.append(float(params[key]))

            if len(values) < 2:
                param_scores[key] = 1.0
                continue

            mean_val = np.mean(values)
            if mean_val == 0:
                param_scores[key] = 1.0 if np.std(values) == 0 else 0.0
                continue

            cv = float(np.std(values) / abs(mean_val))
            param_scores[key] = max(0.0, min(1.0, 1.0 - cv))

        scores = list(param_scores.values())
        overall = float(np.mean(scores)) if scores else 1.0
        divergent = [p for p, s in param_scores.items() if s < 0.5]

        return ConvergenceResult(
            convergence_score=overall,
            param_scores=param_scores,
            divergent_params=divergent,
        )

    # ─── Helpers internes ──────────────────────────────────────────────

    @staticmethod
    def _sharpe_from_returns(returns: list[float]) -> float:
        if len(returns) < 2:
            return 0.0
        arr = np.array(returns)
        std = float(np.std(arr))
        if std < 1e-10:
            return 0.0
        result = float(np.mean(arr) / std)
        return min(100.0, result)

    @staticmethod
    def _skewness(arr: np.ndarray) -> float:
        if len(arr) < 3:
            return 0.0
        mean = np.mean(arr)
        std = np.std(arr)
        if std == 0:
            return 0.0
        return float(np.mean(((arr - mean) / std) ** 3))

    @staticmethod
    def _kurtosis(arr: np.ndarray) -> float:
        """Kurtosis (4e moment centré normalisé — raw, pas excess)."""
        if len(arr) < 4:
            return 3.0
        mean = np.mean(arr)
        std = np.std(arr)
        if std == 0:
            return 3.0
        return float(np.mean(((arr - mean) / std) ** 4))

    @staticmethod
    def _expected_max_sharpe(n_trials: int) -> float:
        """E[max(SR)] sous H0 (approximation Euler-Mascheroni)."""
        if n_trials <= 1:
            return 0.0
        gamma = 0.5772156649
        return float(
            np.sqrt(2 * np.log(n_trials))
            - (np.log(np.pi) + gamma) / (2 * np.sqrt(2 * np.log(n_trials)))
        )


def _norm_cdf(x: float) -> float:
    """CDF de la loi normale standard. Remplace scipy.stats.norm.cdf."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
