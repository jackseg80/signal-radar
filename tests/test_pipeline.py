"""Tests pour le pipeline de validation (Steps 20-21).

Couvre :
- simulate() avec start_idx/end_idx
- _merge_grid_with_defaults
- run_robustness, run_sub_periods, run_ttest
- determine_verdict
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from engine.backtest_config import BacktestConfig
from engine.fee_model import FeeModel
from engine.indicator_cache import IndicatorCache
from engine.simulator import simulate
from engine.types import BacktestResult, Direction, ExitSignal, Position
from strategies.base import BaseStrategy
from tests.conftest import make_bt_config
from validation.report import Verdict, determine_verdict
from validation.robustness import RobustnessResult, run_robustness
from validation.statistics import run_ttest
from validation.sub_periods import run_sub_periods


# ══════════════════════════════════════════════════════════════════════
# DUMMY STRATEGY (réutilisable pour les tests pipeline)
# ══════════════════════════════════════════════════════════════════════


class PipelineDummy(BaseStrategy):
    """Stratégie factice pour tests pipeline.

    Entre LONG sur les candles dans entry_at, sort sur celles dans exit_at.
    param_grid avec 2 valeurs sur un paramètre pour tester la robustesse.
    """

    name = "pipeline_dummy"

    def __init__(
        self,
        *,
        entry_at: set[int] | None = None,
        exit_at: set[int] | None = None,
        warmup_val: int = 5,
    ) -> None:
        self._entry_at = entry_at or set()
        self._exit_at = exit_at or set()
        self._warmup_val = warmup_val

    def default_params(self) -> dict[str, Any]:
        return {
            "position_fraction": 0.2,
            "sl_percent": 0.0,
            "cooldown_candles": 0,
            "dummy_period": 10,
            "extra_period": 5,
        }

    def param_grid(self) -> dict[str, list]:
        return {"dummy_period": [10, 20]}

    def check_entry(self, i: int, cache: IndicatorCache, params: dict) -> Direction:
        if i in self._entry_at:
            return Direction.LONG
        return Direction.FLAT

    def check_exit(
        self, i: int, cache: IndicatorCache, params: dict, position: Position,
    ) -> ExitSignal | None:
        if i in self._exit_at:
            return ExitSignal(price=cache.closes[i], reason="test_exit")
        return None

    def warmup(self, params: dict) -> int:
        return self._warmup_val


# ══════════════════════════════════════════════════════════════════════
# TESTS simulate() start_idx / end_idx
# ══════════════════════════════════════════════════════════════════════


class TestSimulateStartEnd:
    def test_start_end_idx_restricts_trades(self, make_indicator_cache):
        """Les trades ne se produisent que dans [start_idx, end_idx)."""
        strat = PipelineDummy(entry_at={10, 30}, exit_at={12, 32}, warmup_val=5)
        cache = make_indicator_cache(n=50)
        config = make_bt_config()

        # Sans restriction : 2 trades (10→12, 30→32)
        result_full = simulate(strat, cache, strat.default_params(), config)
        assert result_full.n_trades == 2

        # Avec restriction [25, 40) : seul le trade 30→32
        result_partial = simulate(
            strat, cache, strat.default_params(), config,
            start_idx=25, end_idx=40,
        )
        assert result_partial.n_trades == 1
        assert result_partial.trades[0].entry_candle == 30

    def test_default_unchanged(self, make_indicator_cache):
        """Sans start/end → même résultat qu'avant."""
        strat = PipelineDummy(entry_at={10}, exit_at={15}, warmup_val=5)
        cache = make_indicator_cache(n=50)
        config = make_bt_config()

        r1 = simulate(strat, cache, strat.default_params(), config)
        r2 = simulate(strat, cache, strat.default_params(), config,
                      start_idx=None, end_idx=None)

        assert r1.n_trades == r2.n_trades
        assert r1.final_capital == r2.final_capital

    def test_start_below_warmup_raises(self, make_indicator_cache):
        """start_idx < warmup → ValueError."""
        strat = PipelineDummy(warmup_val=10)
        cache = make_indicator_cache(n=50)
        config = make_bt_config()

        with pytest.raises(ValueError, match="start_idx.*warmup"):
            simulate(strat, cache, strat.default_params(), config,
                     start_idx=5)


# ══════════════════════════════════════════════════════════════════════
# TESTS _merge_grid_with_defaults
# ══════════════════════════════════════════════════════════════════════


class TestMergeGrid:
    def test_adds_missing_periods(self):
        """default_params a extra_period non dans param_grid → ajouté."""
        from validation.pipeline import _merge_grid_with_defaults
        strat = PipelineDummy()
        grid = _merge_grid_with_defaults(strat)

        # param_grid a dummy_period, default_params a aussi extra_period
        assert "dummy_period" in grid
        assert "extra_period" in grid
        assert grid["extra_period"] == [5]

    def test_no_override_existing(self):
        """Les clés existantes dans param_grid ne sont pas écrasées."""
        from validation.pipeline import _merge_grid_with_defaults
        strat = PipelineDummy()
        grid = _merge_grid_with_defaults(strat)

        assert grid["dummy_period"] == [10, 20]  # Pas écrasé par default=10


# ══════════════════════════════════════════════════════════════════════
# TESTS robustness
# ══════════════════════════════════════════════════════════════════════


class TestRobustness:
    def test_counts_profitable(self, make_indicator_cache):
        """Vérifie le comptage des combos profitables."""
        # Stratégie qui gagne toujours (entry bas, exit haut)
        strat = PipelineDummy(entry_at={10}, exit_at={15}, warmup_val=5)

        n = 50
        closes = np.full(n, 100.0)
        opens = np.full(n, 100.0)
        closes[15] = 110.0  # Profit sur le trade

        cache = make_indicator_cache(n=n, closes=closes, opens=opens)
        config = make_bt_config()

        result = run_robustness(
            strat, cache, config,
            start_idx=5, end_idx=50,
            min_trades=1,  # 1 seul trade par combo
            symbol="TEST",
        )

        # 2 combos (dummy_period=[10,20]), les deux profitables
        assert result.n_combos == 2
        assert result.n_profitable == 2
        assert result.pct_profitable == 100.0
        assert result.robust is True


# ══════════════════════════════════════════════════════════════════════
# TESTS sub_periods
# ══════════════════════════════════════════════════════════════════════


class TestSubPeriods:
    def test_both_profitable_is_stable(self, make_indicator_cache):
        """Deux sous-périodes profitables → stable=True."""
        # Trades dans les deux moitiés
        strat = PipelineDummy(
            entry_at={10, 30}, exit_at={12, 32}, warmup_val=5,
        )

        n = 50
        closes = np.full(n, 100.0)
        opens = np.full(n, 100.0)
        closes[12] = 110.0  # Profit trade 1
        closes[32] = 110.0  # Profit trade 2

        cache = make_indicator_cache(n=n, closes=closes, opens=opens)
        config = make_bt_config()

        result = run_sub_periods(
            strat, cache, config,
            oos_start_idx=5, oos_mid_idx=25, oos_end_idx=50,
            symbol="TEST",
        )

        assert result.n_trades_a >= 1
        assert result.n_trades_b >= 1
        assert result.pf_a > 1.0
        assert result.pf_b > 1.0
        assert result.stable is True


# ══════════════════════════════════════════════════════════════════════
# TESTS t-test
# ══════════════════════════════════════════════════════════════════════


class TestTTest:
    def test_significant(self):
        """Returns positifs → p < alpha."""
        returns = [0.02, 0.03, 0.01, 0.04, 0.02, 0.03, 0.01, 0.05,
                   0.02, 0.03, 0.01, 0.04, 0.02, 0.03, 0.01, 0.05]
        result = run_ttest(returns, symbol="TEST", alpha=0.10)

        assert result.significant is True
        assert result.p_value < 0.05
        assert result.label == "OUI (p<0.05)"

    def test_not_significant(self):
        """Returns autour de zéro → p > alpha."""
        np.random.seed(42)
        returns = list(np.random.normal(0.0, 0.01, 20))
        result = run_ttest(returns, symbol="TEST", alpha=0.10)

        # Avec seed 42 et mean=0, p devrait être > 0.10
        assert result.p_value > 0.05

    def test_single_trade(self):
        """Un seul trade → non significatif."""
        result = run_ttest([0.05], symbol="TEST")
        assert result.significant is False
        assert result.p_value == 1.0


# ══════════════════════════════════════════════════════════════════════
# TESTS verdict
# ══════════════════════════════════════════════════════════════════════


class TestVerdict:
    def _make_robustness(self, robust: bool) -> RobustnessResult:
        return RobustnessResult(
            symbol="TEST", n_combos=48, n_profitable=40 if robust else 10,
            pct_profitable=83.3 if robust else 20.8,
            best_pf=2.0, worst_pf=0.5, median_pf=1.3,
            robust=robust,
        )

    def _make_sub_periods(self, stable: bool):
        from validation.sub_periods import SubPeriodResult
        return SubPeriodResult(
            symbol="TEST",
            n_trades_a=20, pf_a=1.5 if stable else 0.8, sharpe_a=0.5,
            n_trades_b=20, pf_b=1.3 if stable else 0.7, sharpe_b=0.4,
            stable=stable,
        )

    def _make_ttest(self, significant: bool):
        from validation.statistics import TTestResult
        return TTestResult(
            symbol="TEST", n_trades=40,
            mean_return_pct=0.5, t_stat=2.5 if significant else 0.5,
            p_value=0.01 if significant else 0.30,
            significant=significant,
            label="OUI (p<0.05)" if significant else "NON",
        )

    def test_validated(self):
        """robust AND stable AND significant → VALIDATED."""
        v = determine_verdict(
            self._make_robustness(True),
            self._make_sub_periods(True),
            self._make_ttest(True),
        )
        assert v == Verdict.VALIDATED

    def test_conditional_robust_stable_not_sig(self):
        """robust AND stable AND NOT significant → CONDITIONAL."""
        v = determine_verdict(
            self._make_robustness(True),
            self._make_sub_periods(True),
            self._make_ttest(False),
        )
        assert v == Verdict.CONDITIONAL

    def test_conditional_robust_sig_not_stable(self):
        """robust AND significant AND NOT stable → CONDITIONAL."""
        v = determine_verdict(
            self._make_robustness(True),
            self._make_sub_periods(False),
            self._make_ttest(True),
        )
        assert v == Verdict.CONDITIONAL

    def test_rejected_not_robust(self):
        """NOT robust → REJECTED (même si stable et significatif)."""
        v = determine_verdict(
            self._make_robustness(False),
            self._make_sub_periods(True),
            self._make_ttest(True),
        )
        assert v == Verdict.REJECTED

    def test_rejected_robust_only(self):
        """robust AND NOT stable AND NOT significant → REJECTED."""
        v = determine_verdict(
            self._make_robustness(True),
            self._make_sub_periods(False),
            self._make_ttest(False),
        )
        assert v == Verdict.REJECTED
