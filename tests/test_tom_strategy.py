"""Tests pour strategies/turn_of_month.py -- plugin BaseStrategy TOM.

Couvre : arrays calendaires, entry/exit, params, integration simulate().
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.backtest_config import BacktestConfig
from engine.fee_model import FeeModel
from engine.indicator_cache import IndicatorCache, build_cache
from engine.simulator import simulate
from engine.types import Direction, Position
from strategies.turn_of_month import TurnOfMonth
from tests.conftest import make_bt_config


# ======================================================================
# HELPERS
# ======================================================================


def _make_tom_cache_from_dates(
    dates: pd.DatetimeIndex,
    close: float = 100.0,
) -> IndicatorCache:
    """Construit un IndicatorCache avec arrays calendaires via build_cache()."""
    n = len(dates)
    arrays = {
        "opens": np.full(n, close),
        "highs": np.full(n, close + 1.0),
        "lows": np.full(n, close - 1.0),
        "closes": np.full(n, close),
        "volumes": np.full(n, 1_000_000.0),
    }
    return build_cache(arrays, {}, dates=dates.values)


def _make_position(entry_candle: int = 5, entry_price: float = 100.0) -> Position:
    return Position(
        entry_price=entry_price,
        entry_candle=entry_candle,
        quantity=10.0,
        direction=Direction.LONG,
        capital_allocated=1000.0,
        entry_fee=0.0,
    )


# ======================================================================
# TESTS ARRAYS CALENDAIRES
# ======================================================================


class TestCalendarArrays:
    """Verifie que build_cache() calcule correctement les arrays calendaires."""

    def test_trading_day_of_month_starts_at_1(self):
        """Le premier jour de trading du mois doit etre 1."""
        # Janvier 2024 : 2 jan (lundi) est le 1er jour de trading
        dates = pd.bdate_range("2024-01-01", "2024-01-31")
        cache = _make_tom_cache_from_dates(dates)

        assert cache.trading_day_of_month is not None
        assert cache.trading_day_of_month[0] == 1

    def test_trading_day_of_month_increments(self):
        """Les rangs sont consécutifs dans un mois."""
        dates = pd.bdate_range("2024-01-01", "2024-01-31")
        cache = _make_tom_cache_from_dates(dates)

        tdom = cache.trading_day_of_month
        assert tdom is not None
        # Janvier 2024 : 23 jours ouvrés
        expected = list(range(1, len(dates) + 1))
        np.testing.assert_array_equal(tdom, expected)

    def test_trading_day_of_month_resets_each_month(self):
        """Le 1er jour du nouveau mois reset a 1."""
        dates = pd.bdate_range("2024-01-29", "2024-02-05")
        cache = _make_tom_cache_from_dates(dates)

        tdom = cache.trading_day_of_month
        assert tdom is not None
        # Trouve le premier jour de fevrier
        feb_mask = pd.DatetimeIndex(cache.dates).month == 2
        feb_idx = np.where(feb_mask)[0]
        assert tdom[feb_idx[0]] == 1

    def test_trading_days_left_in_month_last_day_is_1(self):
        """Le dernier jour de trading du mois a trading_days_left = 1."""
        dates = pd.bdate_range("2024-01-01", "2024-01-31")
        cache = _make_tom_cache_from_dates(dates)

        tdlm = cache.trading_days_left_in_month
        assert tdlm is not None
        # Dernier jour de trading de janvier 2024 = mardi 31 jan
        assert tdlm[-1] == 1

    def test_trading_days_left_decrements(self):
        """Les jours restants decrementent de la fin vers le debut."""
        dates = pd.bdate_range("2024-01-01", "2024-01-31")
        cache = _make_tom_cache_from_dates(dates)

        tdlm = cache.trading_days_left_in_month
        assert tdlm is not None
        n = len(dates)
        assert tdlm[0] == n        # 1er jour : tous les jours restants
        assert tdlm[-1] == 1       # dernier jour : 1 restant

    def test_no_dates_gives_none_arrays(self):
        """Sans dates, les arrays calendaires sont None."""
        n = 50
        arrays = {
            "opens": np.full(n, 100.0),
            "highs": np.full(n, 101.0),
            "lows": np.full(n, 99.0),
            "closes": np.full(n, 100.0),
            "volumes": np.full(n, 1e6),
        }
        cache = build_cache(arrays, {})
        assert cache.dates is None
        assert cache.trading_day_of_month is None
        assert cache.trading_days_left_in_month is None


# ======================================================================
# TESTS ENTRY
# ======================================================================


class TestTOMEntry:
    """Verifie check_entry selon la position dans le mois."""

    def test_long_entry_last_5_days(self):
        """Dans les 5 derniers jours de trading -> LONG."""
        strat = TurnOfMonth()
        params = strat.default_params()  # entry_days_before_eom=5

        dates = pd.bdate_range("2024-01-01", "2024-01-31")
        cache = _make_tom_cache_from_dates(dates)

        # Le dernier jour de trading de janvier 2024 est index len-1
        # check_entry(i) evalue sur [i-1], donc on evalue sur i = len-1
        # pour que prev = len-2 soit aussi dans les 5 derniers
        last_5_start = len(dates) - 5  # premier des 5 derniers jours

        # Verifie que tous les jours dans les 5 derniers donnent LONG
        for i in range(last_5_start + 1, len(dates) + 1):
            if i < len(dates):  # i doit etre dans le cache
                result = strat.check_entry(i, cache, params)
                assert result == Direction.LONG, (
                    f"Attendu LONG sur i={i} (days_left={cache.trading_days_left_in_month[i-1]})"
                )

    def test_no_entry_mid_month(self):
        """En milieu de mois -> FLAT."""
        strat = TurnOfMonth()
        params = strat.default_params()  # entry_days_before_eom=5

        dates = pd.bdate_range("2024-01-01", "2024-01-31")
        cache = _make_tom_cache_from_dates(dates)

        # Index 5 : environ le 9 janvier, milieu de mois (>5 jours restants)
        result = strat.check_entry(5, cache, params)
        assert result == Direction.FLAT

    def test_no_entry_without_dates(self, make_indicator_cache):
        """Cache sans dates -> FLAT (degradation gracieuse)."""
        strat = TurnOfMonth()
        params = strat.default_params()

        cache = make_indicator_cache(n=50)  # pas de dates
        assert cache.trading_days_left_in_month is None

        result = strat.check_entry(10, cache, params)
        assert result == Direction.FLAT

    def test_entry_threshold_3_days(self):
        """entry_days_before_eom=3 : seuls les 3 derniers jours donnent LONG."""
        strat = TurnOfMonth()
        params = strat.default_params()
        params["entry_days_before_eom"] = 3

        dates = pd.bdate_range("2024-01-01", "2024-01-31")
        cache = _make_tom_cache_from_dates(dates)

        # index 6 jours avant la fin : days_left[prev] = 7 -> FLAT
        i_flat = len(dates) - 6
        result_flat = strat.check_entry(i_flat, cache, params)
        assert result_flat == Direction.FLAT

        # index dans les 3 derniers : days_left[prev] <= 3 -> LONG
        i_long = len(dates) - 1
        result_long = strat.check_entry(i_long, cache, params)
        assert result_long == Direction.LONG


# ======================================================================
# TESTS EXIT
# ======================================================================


class TestTOMExit:
    """Verifie check_exit selon le jour du nouveau mois."""

    def test_exit_3rd_day_new_month(self):
        """3eme jour du nouveau mois -> tom_exit."""
        strat = TurnOfMonth()
        params = strat.default_params()  # exit_day_of_new_month=3

        # Dates couvrant fin janvier + debut fevrier 2024
        dates = pd.bdate_range("2024-01-20", "2024-02-10")
        cache = _make_tom_cache_from_dates(dates)

        # Trouver le 3eme jour de trading de fevrier
        feb_mask = pd.DatetimeIndex(cache.dates).month == 2
        feb_indices = np.where(feb_mask)[0]
        i_exit = feb_indices[2]  # 3eme jour (index 2 = rang 1-indexed 3)

        # Entrer en janvier (dernier jour de janvier)
        jan_mask = pd.DatetimeIndex(cache.dates).month == 1
        jan_indices = np.where(jan_mask)[0]
        entry_i = jan_indices[-1]

        position = _make_position(entry_candle=entry_i)
        result = strat.check_exit(i_exit, cache, params, position)

        assert result is not None
        assert result.reason == "tom_exit"

    def test_no_exit_same_month(self):
        """Meme mois que l'entree -> pas d'exit (meme si trading_day >= exit_day)."""
        strat = TurnOfMonth()
        params = strat.default_params()

        dates = pd.bdate_range("2024-01-01", "2024-01-31")
        cache = _make_tom_cache_from_dates(dates)

        # Entrer et evaluer le meme mois
        position = _make_position(entry_candle=5)
        result = strat.check_exit(8, cache, params, position)

        assert result is None

    def test_no_exit_too_early_new_month(self):
        """1er ou 2eme jour du nouveau mois (exit_day=3) -> pas d'exit."""
        strat = TurnOfMonth()
        params = strat.default_params()  # exit_day_of_new_month=3

        dates = pd.bdate_range("2024-01-20", "2024-02-10")
        cache = _make_tom_cache_from_dates(dates)

        feb_mask = pd.DatetimeIndex(cache.dates).month == 2
        feb_indices = np.where(feb_mask)[0]
        i_2nd_feb = feb_indices[1]  # 2eme jour de fevrier

        jan_mask = pd.DatetimeIndex(cache.dates).month == 1
        jan_indices = np.where(jan_mask)[0]
        position = _make_position(entry_candle=jan_indices[-1])

        result = strat.check_exit(i_2nd_feb, cache, params, position)
        assert result is None

    def test_safety_exit_max_holding(self, make_indicator_cache):
        """max_holding_days depasse -> max_holding_exit."""
        strat = TurnOfMonth()
        params = strat.default_params()
        params["max_holding_days"] = 5

        n = 50
        dates = pd.bdate_range("2024-01-01", periods=n)
        cache = make_indicator_cache(
            n=n,
            dates=dates.values,
            trading_day_of_month=np.arange(1, n + 1, dtype=np.int32),
            trading_days_left_in_month=np.arange(n, 0, -1, dtype=np.int32),
        )

        position = _make_position(entry_candle=10)
        result = strat.check_exit(15, cache, params, position)  # 15 - 10 = 5 >= 5

        assert result is not None
        assert result.reason == "max_holding_exit"

    def test_no_exit_without_dates(self, make_indicator_cache):
        """Cache sans dates -> pas d'exit (degradation gracieuse, sauf max_holding)."""
        strat = TurnOfMonth()
        params = strat.default_params()
        params["max_holding_days"] = 100  # desactiver le safety exit

        cache = make_indicator_cache(n=50)  # pas de dates
        position = _make_position(entry_candle=5)

        result = strat.check_exit(10, cache, params, position)
        assert result is None


# ======================================================================
# TESTS PARAMS
# ======================================================================


class TestTOMParams:
    def test_default_params_valid(self):
        """default_params retourne les cles attendues."""
        strat = TurnOfMonth()
        params = strat.default_params()

        assert "entry_days_before_eom" in params
        assert "exit_day_of_new_month" in params
        assert "max_holding_days" in params
        assert "position_fraction" in params
        assert params["entry_days_before_eom"] == 5
        assert params["exit_day_of_new_month"] == 3
        assert params["max_holding_days"] == 10
        assert params["position_fraction"] == 1.0

    def test_param_grid_valid(self):
        """param_grid retourne les cles et combinaisons attendues."""
        strat = TurnOfMonth()
        grid = strat.param_grid()

        assert "entry_days_before_eom" in grid
        assert "exit_day_of_new_month" in grid

        from itertools import product
        combos = list(product(*grid.values()))
        assert len(combos) == 12  # 4 x 3

    def test_warmup_override(self):
        """warmup retourne 30 (pas d'indicateur technique)."""
        strat = TurnOfMonth()
        assert strat.warmup(strat.default_params()) == 30

    def test_name(self):
        strat = TurnOfMonth()
        assert strat.name == "turn_of_month"


# ======================================================================
# TESTS INTEGRATION
# ======================================================================


class TestTOMIntegration:
    def test_full_cycle_tom(self):
        """Cycle complet entry -> exit via simulate() sur 3 mois de donnees."""
        strat = TurnOfMonth()
        params = strat.default_params()

        # 4 mois de trading : novembre 2023 a fevrier 2024 (exit jan couvre feb)
        dates = pd.bdate_range("2023-11-01", "2024-02-20")
        n = len(dates)

        arrays = {
            "opens": np.full(n, 100.0),
            "highs": np.full(n, 101.0),
            "lows": np.full(n, 99.0),
            "closes": np.full(n, 100.0),
            "volumes": np.full(n, 1_000_000.0),
        }
        cache = build_cache(arrays, {}, dates=dates.values)

        bt_config = BacktestConfig(
            symbol="TEST",
            initial_capital=10_000.0,
            slippage_pct=0.0,
            fee_model=FeeModel(),
        )

        result = simulate(strat, cache, params, bt_config, start_idx=30, end_idx=n)

        # On doit avoir des trades (signal calendaire actif sur 3 mois)
        assert result.n_trades >= 2, f"Attendu >= 2 trades, obtenu {result.n_trades}"

        # Verifier que les exits sont "tom_exit" ou "max_holding_exit"
        valid_reasons = {"tom_exit", "max_holding_exit", "force_close"}
        for trade in result.trades:
            assert trade.exit_reason in valid_reasons, (
                f"Raison de sortie inattendue : {trade.exit_reason}"
            )

    def test_no_trades_when_dates_missing(self):
        """Sans dates dans le cache, aucun trade ne doit etre genere."""
        strat = TurnOfMonth()
        params = strat.default_params()

        n = 100
        arrays = {
            "opens": np.full(n, 100.0),
            "highs": np.full(n, 101.0),
            "lows": np.full(n, 99.0),
            "closes": np.full(n, 100.0),
            "volumes": np.full(n, 1_000_000.0),
        }
        # build_cache sans dates -> arrays calendaires None
        cache = build_cache(arrays, {})

        bt_config = BacktestConfig(
            symbol="TEST",
            initial_capital=10_000.0,
            slippage_pct=0.0,
            fee_model=FeeModel(),
        )

        result = simulate(strat, cache, params, bt_config, start_idx=30, end_idx=n)
        assert result.n_trades == 0
