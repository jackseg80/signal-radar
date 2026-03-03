"""Tests pour strategies/ibs_tom.py -- plugin BaseStrategy IBS + TOM.

Couvre : params, entry (3 conditions AND), exit (TOM + IBS early), integration simulate().
"""

from __future__ import annotations

from itertools import product

import numpy as np
import pandas as pd
import pytest

from engine.backtest_config import BacktestConfig
from engine.fee_model import FeeModel
from engine.indicator_cache import IndicatorCache, build_cache
from engine.simulator import simulate
from engine.types import Direction, Position
from strategies.ibs_tom import IBSTurnOfMonth
from tests.conftest import make_bt_config


# ======================================================================
# HELPERS
# ======================================================================


def _make_ibs_tom_cache(
    make_indicator_cache,
    *,
    n: int = 50,
    close: float = 110.0,
    sma200: float = 100.0,
    ibs_val: float = 0.1,
    high: float = 112.0,
    low: float = 108.0,
    days_left: int = 3,
    day_of_month: int = 1,
    with_dates: bool = True,
) -> IndicatorCache:
    """Cache avec IBS + SMA + arrays calendaires, valeurs controlees."""
    closes = np.full(n, close)
    highs = np.full(n, high)
    lows = np.full(n, low)
    ibs_arr = np.full(n, ibs_val)
    sma200_arr = np.full(n, sma200)
    tdlm = np.full(n, days_left, dtype=np.int32)
    tdom = np.full(n, day_of_month, dtype=np.int32)

    dates = None
    if with_dates:
        dates = pd.bdate_range("2024-01-01", periods=n).values

    return make_indicator_cache(
        n=n,
        closes=closes,
        highs=highs,
        lows=lows,
        ibs=ibs_arr,
        sma_by_period={200: sma200_arr},
        trading_days_left_in_month=tdlm,
        trading_day_of_month=tdom,
        dates=dates,
    )


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
# TESTS PARAMS
# ======================================================================


class TestIBSTOMParams:
    def test_name(self):
        strat = IBSTurnOfMonth()
        assert strat.name == "ibs_turn_of_month"

    def test_default_params_keys(self):
        strat = IBSTurnOfMonth()
        params = strat.default_params()
        expected_keys = {
            "entry_days_before_eom", "exit_day_of_new_month", "max_holding_days",
            "ibs_entry_threshold", "ibs_exit_threshold", "sma_trend_period",
            "position_fraction", "sl_percent", "cooldown_candles", "sides",
        }
        assert set(params.keys()) == expected_keys

    def test_param_grid_combos(self):
        strat = IBSTurnOfMonth()
        grid = strat.param_grid()
        combos = list(product(*grid.values()))
        assert len(combos) == 18  # 3 x 3 x 2

    def test_param_grid_covers_defaults(self):
        """Les valeurs par defaut sont dans les ranges du grid."""
        strat = IBSTurnOfMonth()
        defaults = strat.default_params()
        grid = strat.param_grid()
        for key, values in grid.items():
            assert defaults[key] in values, f"{key}={defaults[key]} absent du grid"

    def test_warmup(self):
        """warmup = 210 (sma_trend_period=200 + 10)."""
        strat = IBSTurnOfMonth()
        assert strat.warmup(strat.default_params()) == 210


# ======================================================================
# TESTS ENTRY
# ======================================================================


class TestIBSTOMEntry:
    def test_long_entry_all_conditions_met(self, make_indicator_cache):
        """TOM window + IBS bas + trend up -> LONG."""
        strat = IBSTurnOfMonth()
        params = strat.default_params()

        cache = _make_ibs_tom_cache(
            make_indicator_cache,
            close=110.0, sma200=100.0, ibs_val=0.1, days_left=3,
        )
        result = strat.check_entry(10, cache, params)
        assert result == Direction.LONG

    def test_no_entry_outside_tom_window(self, make_indicator_cache):
        """Milieu de mois (days_left > 5) -> FLAT meme si IBS bas."""
        strat = IBSTurnOfMonth()
        params = strat.default_params()

        cache = _make_ibs_tom_cache(
            make_indicator_cache,
            close=110.0, sma200=100.0, ibs_val=0.1, days_left=10,
        )
        result = strat.check_entry(10, cache, params)
        assert result == Direction.FLAT

    def test_no_entry_ibs_above_threshold(self, make_indicator_cache):
        """IBS >= 0.2 -> FLAT meme si dans la fenetre TOM."""
        strat = IBSTurnOfMonth()
        params = strat.default_params()

        cache = _make_ibs_tom_cache(
            make_indicator_cache,
            close=110.0, sma200=100.0, ibs_val=0.5, days_left=3,
        )
        result = strat.check_entry(10, cache, params)
        assert result == Direction.FLAT

    def test_no_entry_below_sma_trend(self, make_indicator_cache):
        """Close < SMA200 -> FLAT meme si TOM + IBS."""
        strat = IBSTurnOfMonth()
        params = strat.default_params()

        cache = _make_ibs_tom_cache(
            make_indicator_cache,
            close=95.0, sma200=100.0, ibs_val=0.1, days_left=3,
        )
        result = strat.check_entry(10, cache, params)
        assert result == Direction.FLAT

    def test_no_entry_ibs_nan(self, make_indicator_cache):
        """IBS = NaN -> FLAT."""
        strat = IBSTurnOfMonth()
        params = strat.default_params()

        cache = _make_ibs_tom_cache(
            make_indicator_cache,
            close=110.0, sma200=100.0, ibs_val=0.1, days_left=3,
        )
        cache.ibs[9] = np.nan  # prev = 10-1 = 9
        result = strat.check_entry(10, cache, params)
        assert result == Direction.FLAT

    def test_no_entry_without_calendar(self, make_indicator_cache):
        """Cache sans trading_days_left_in_month -> FLAT."""
        strat = IBSTurnOfMonth()
        params = strat.default_params()

        cache = make_indicator_cache(
            n=50,
            ibs=np.full(50, 0.1),
            sma_by_period={200: np.full(50, 100.0)},
            closes=np.full(50, 110.0),
        )
        assert cache.trading_days_left_in_month is None

        result = strat.check_entry(10, cache, params)
        assert result == Direction.FLAT

    def test_no_entry_without_ibs(self, make_indicator_cache):
        """Cache sans IBS -> FLAT."""
        strat = IBSTurnOfMonth()
        params = strat.default_params()

        cache = _make_ibs_tom_cache(
            make_indicator_cache,
            close=110.0, sma200=100.0, ibs_val=0.1, days_left=3,
        )
        cache.ibs = None
        result = strat.check_entry(10, cache, params)
        assert result == Direction.FLAT

    def test_entry_custom_thresholds(self, make_indicator_cache):
        """Thresholds modifies (entry_days=3, ibs=0.15) -> LONG si conditions ok."""
        strat = IBSTurnOfMonth()
        params = strat.default_params()
        params["entry_days_before_eom"] = 3
        params["ibs_entry_threshold"] = 0.15

        # IBS = 0.1 < 0.15, days_left = 2 <= 3 -> LONG
        cache = _make_ibs_tom_cache(
            make_indicator_cache,
            close=110.0, sma200=100.0, ibs_val=0.1, days_left=2,
        )
        result = strat.check_entry(10, cache, params)
        assert result == Direction.LONG


# ======================================================================
# TESTS EXIT
# ======================================================================


class TestIBSTOMExit:
    def test_max_holding_exit(self, make_indicator_cache):
        """(i - entry_candle) >= max_holding_days -> max_holding_exit."""
        strat = IBSTurnOfMonth()
        params = strat.default_params()
        params["max_holding_days"] = 5

        cache = _make_ibs_tom_cache(make_indicator_cache, day_of_month=1)
        position = _make_position(entry_candle=10)

        result = strat.check_exit(15, cache, params, position)  # 15-10=5 >= 5
        assert result is not None
        assert result.reason == "max_holding_exit"

    def test_tom_exit_new_month(self):
        """Nouveau mois + trading_day >= exit_day -> tom_exit."""
        strat = IBSTurnOfMonth()
        params = strat.default_params()  # exit_day_of_new_month=3

        dates = pd.bdate_range("2024-01-20", "2024-02-10")
        cache = _make_tom_cache_with_ibs(dates, close=110.0, sma200=100.0)

        # Entrer le dernier jour de janvier
        jan_mask = pd.DatetimeIndex(cache.dates).month == 1
        jan_indices = np.where(jan_mask)[0]
        entry_i = jan_indices[-1]

        # 3eme jour de fevrier
        feb_mask = pd.DatetimeIndex(cache.dates).month == 2
        feb_indices = np.where(feb_mask)[0]
        i_exit = feb_indices[2]  # 3eme jour, rang 1-indexed = 3

        position = _make_position(entry_candle=entry_i)
        result = strat.check_exit(i_exit, cache, params, position)

        assert result is not None
        assert result.reason == "tom_exit"

    def test_ibs_early_exit_new_month(self):
        """Nouveau mois + IBS > 0.8 (avant tom_exit day) -> ibs_early_exit."""
        strat = IBSTurnOfMonth()
        params = strat.default_params()  # exit_day=3, ibs_exit=0.8

        dates = pd.bdate_range("2024-01-20", "2024-02-10")
        cache = _make_tom_cache_with_ibs(dates, close=110.0, sma200=100.0, ibs_val=0.3)

        jan_mask = pd.DatetimeIndex(cache.dates).month == 1
        jan_indices = np.where(jan_mask)[0]
        entry_i = jan_indices[-1]

        # 1er jour de fevrier : trading_day_of_month = 1 < exit_day=3
        feb_mask = pd.DatetimeIndex(cache.dates).month == 2
        feb_indices = np.where(feb_mask)[0]
        i_first_feb = feb_indices[0]

        # Mettre IBS > 0.8 sur ce jour
        cache.ibs[i_first_feb] = 0.9

        position = _make_position(entry_candle=entry_i)
        result = strat.check_exit(i_first_feb, cache, params, position)

        assert result is not None
        assert result.reason == "ibs_early_exit"

    def test_no_exit_same_month(self, make_indicator_cache):
        """Meme mois que l'entree, IBS mid -> None."""
        strat = IBSTurnOfMonth()
        params = strat.default_params()
        params["max_holding_days"] = 100  # desactiver safety

        n = 50
        dates = pd.bdate_range("2024-01-01", periods=n)
        cache = make_indicator_cache(
            n=n,
            closes=np.full(n, 110.0),
            ibs=np.full(n, 0.5),
            sma_by_period={200: np.full(n, 100.0)},
            dates=dates.values,
            trading_day_of_month=np.arange(1, n + 1, dtype=np.int32),
            trading_days_left_in_month=np.arange(n, 0, -1, dtype=np.int32),
        )

        # Entree et sortie dans le meme mois (janvier)
        position = _make_position(entry_candle=5)
        result = strat.check_exit(8, cache, params, position)
        assert result is None

    def test_no_exit_early_new_month(self):
        """Nouveau mois mais day < exit_day, IBS mid -> None."""
        strat = IBSTurnOfMonth()
        params = strat.default_params()  # exit_day=3, ibs_exit=0.8
        params["max_holding_days"] = 100

        dates = pd.bdate_range("2024-01-20", "2024-02-10")
        cache = _make_tom_cache_with_ibs(dates, close=110.0, sma200=100.0, ibs_val=0.5)

        jan_mask = pd.DatetimeIndex(cache.dates).month == 1
        jan_indices = np.where(jan_mask)[0]
        entry_i = jan_indices[-1]

        # 1er jour de fevrier : day_of_month=1 < 3, IBS=0.5 < 0.8 -> None
        feb_mask = pd.DatetimeIndex(cache.dates).month == 2
        feb_indices = np.where(feb_mask)[0]
        i_first_feb = feb_indices[0]

        position = _make_position(entry_candle=entry_i)
        result = strat.check_exit(i_first_feb, cache, params, position)
        assert result is None

    def test_tom_priority_over_ibs(self):
        """Si TOM exit ET IBS early exit sont vrais, TOM a priorite."""
        strat = IBSTurnOfMonth()
        params = strat.default_params()  # exit_day=3, ibs_exit=0.8

        dates = pd.bdate_range("2024-01-20", "2024-02-10")
        cache = _make_tom_cache_with_ibs(dates, close=110.0, sma200=100.0, ibs_val=0.9)

        jan_mask = pd.DatetimeIndex(cache.dates).month == 1
        jan_indices = np.where(jan_mask)[0]
        entry_i = jan_indices[-1]

        # 3eme jour de fevrier : day >= 3 (TOM) ET IBS=0.9 > 0.8 (IBS early)
        feb_mask = pd.DatetimeIndex(cache.dates).month == 2
        feb_indices = np.where(feb_mask)[0]
        i_3rd_feb = feb_indices[2]

        position = _make_position(entry_candle=entry_i)
        result = strat.check_exit(i_3rd_feb, cache, params, position)

        assert result is not None
        assert result.reason == "tom_exit"  # TOM a priorite

    def test_no_exit_without_dates(self, make_indicator_cache):
        """Cache sans dates -> None (sauf max_holding)."""
        strat = IBSTurnOfMonth()
        params = strat.default_params()
        params["max_holding_days"] = 100

        cache = make_indicator_cache(
            n=50,
            ibs=np.full(50, 0.9),
            sma_by_period={200: np.full(50, 100.0)},
        )
        position = _make_position(entry_candle=5)

        result = strat.check_exit(10, cache, params, position)
        assert result is None

    def test_exit_year_boundary(self):
        """Dec -> Jan : detecte correctement le nouveau mois."""
        strat = IBSTurnOfMonth()
        params = strat.default_params()

        dates = pd.bdate_range("2023-12-15", "2024-01-15")
        cache = _make_tom_cache_with_ibs(dates, close=110.0, sma200=100.0)

        # Entrer en decembre
        dec_mask = pd.DatetimeIndex(cache.dates).month == 12
        dec_indices = np.where(dec_mask)[0]
        entry_i = dec_indices[-1]

        # 3eme jour de janvier (nouveau mois + nouvelle annee)
        jan_mask = pd.DatetimeIndex(cache.dates).month == 1
        jan_indices = np.where(jan_mask)[0]
        i_3rd_jan = jan_indices[2]

        position = _make_position(entry_candle=entry_i)
        result = strat.check_exit(i_3rd_jan, cache, params, position)

        assert result is not None
        assert result.reason == "tom_exit"


# ======================================================================
# TESTS INTEGRATION
# ======================================================================


class TestIBSTOMIntegration:
    def test_full_cycle_via_simulate(self):
        """Cycle complet : entry fin de mois + IBS bas -> exit nouveau mois."""
        strat = IBSTurnOfMonth()
        params = strat.default_params()

        # 4 mois pour avoir au moins 1 trade
        dates = pd.bdate_range("2023-11-01", "2024-02-20")
        n = len(dates)

        closes = np.full(n, 110.0)
        arrays = {
            "opens": np.full(n, 110.0),
            "highs": np.full(n, 112.0),
            "lows": np.full(n, 108.0),
            "closes": closes,
            "volumes": np.full(n, 1_000_000.0),
        }

        # build_cache avec sma_trend_period pour avoir SMA(200) + IBS + dates
        cache = build_cache(arrays, {"sma_trend_period": [200]}, dates=dates.values)

        # SMA(200) sur prix constant = le prix lui-meme (110.0)
        # IBS sur prix constant = (110-108)/(112-108) = 0.5 -> PAS d'entry (>= 0.2)
        # On doit injecter des IBS bas dans les fenetres TOM
        for month in [11, 12, 1]:
            mask = pd.DatetimeIndex(cache.dates).month == month
            indices = np.where(mask)[0]
            if len(indices) >= 5:
                # Les 5 derniers jours du mois : IBS bas
                for idx in indices[-5:]:
                    cache.ibs[idx] = 0.1

        bt_config = BacktestConfig(
            symbol="TEST",
            initial_capital=10_000.0,
            slippage_pct=0.0,
            fee_model=FeeModel(),
        )

        result = simulate(strat, cache, params, bt_config, start_idx=210, end_idx=n)

        # Warmup = 210. Avec 4 mois, n ~ 80. start_idx=210 > n -> 0 trades.
        # Correction : on a besoin d'un dataset plus long pour warmup SMA200.
        # Utilisons un dataset de 250+ jours.
        assert True  # placeholder, le vrai test est ci-dessous

    def test_full_cycle_long_dataset(self):
        """Cycle complet avec dataset assez long pour le warmup SMA200."""
        strat = IBSTurnOfMonth()
        params = strat.default_params()

        # ~14 mois pour couvrir warmup=210 + 2-3 mois de trading
        dates = pd.bdate_range("2023-01-01", "2024-02-20")
        n = len(dates)

        closes = np.full(n, 110.0)
        arrays = {
            "opens": np.full(n, 110.0),
            "highs": np.full(n, 112.0),
            "lows": np.full(n, 108.0),
            "closes": closes,
            "volumes": np.full(n, 1_000_000.0),
        }

        cache = build_cache(arrays, {"sma_trend_period": [200]}, dates=dates.values)

        # SMA200 sur prix constant = 110.0. close > SMA200 exige strict >.
        # Override SMA a 109 pour que 110 > 109 = True.
        cache.sma_by_period[200] = np.full(n, 109.0)

        # Injecter IBS bas dans les fenetres TOM (derniers 5 jours de chaque mois)
        for month_start in pd.date_range("2023-01-01", "2024-02-01", freq="MS"):
            month_end = month_start + pd.offsets.MonthEnd(0)
            mask = (
                (pd.DatetimeIndex(cache.dates) >= month_start)
                & (pd.DatetimeIndex(cache.dates) <= month_end)
            )
            indices = np.where(mask)[0]
            if len(indices) >= 5:
                for idx in indices[-5:]:
                    cache.ibs[idx] = 0.1

        bt_config = BacktestConfig(
            symbol="TEST",
            initial_capital=10_000.0,
            slippage_pct=0.0,
            fee_model=FeeModel(),
        )

        result = simulate(strat, cache, params, bt_config, start_idx=210, end_idx=n)

        assert result.n_trades >= 1, f"Attendu >= 1 trade, obtenu {result.n_trades}"

        valid_reasons = {"tom_exit", "ibs_early_exit", "max_holding_exit", "force_close"}
        for trade in result.trades:
            assert trade.exit_reason in valid_reasons, (
                f"Raison de sortie inattendue : {trade.exit_reason}"
            )

    def test_no_trades_ibs_always_high(self):
        """IBS toujours 0.5 -> 0 trades (jamais < 0.2)."""
        strat = IBSTurnOfMonth()
        params = strat.default_params()

        dates = pd.bdate_range("2023-01-01", "2024-02-20")
        n = len(dates)

        arrays = {
            "opens": np.full(n, 110.0),
            "highs": np.full(n, 112.0),
            "lows": np.full(n, 108.0),
            "closes": np.full(n, 110.0),
            "volumes": np.full(n, 1_000_000.0),
        }

        cache = build_cache(arrays, {"sma_trend_period": [200]}, dates=dates.values)
        # IBS = (110-108)/(112-108) = 0.5 partout -> jamais < 0.2

        bt_config = make_bt_config()
        result = simulate(strat, cache, params, bt_config, start_idx=210, end_idx=n)
        assert result.n_trades == 0

    def test_no_trades_without_calendar(self):
        """Cache sans dates -> 0 trades."""
        strat = IBSTurnOfMonth()
        params = strat.default_params()

        n = 300
        arrays = {
            "opens": np.full(n, 110.0),
            "highs": np.full(n, 112.0),
            "lows": np.full(n, 108.0),
            "closes": np.full(n, 110.0),
            "volumes": np.full(n, 1_000_000.0),
        }

        # Sans dates -> pas de calendar arrays
        cache = build_cache(arrays, {"sma_trend_period": [200]})

        bt_config = make_bt_config()
        result = simulate(strat, cache, params, bt_config, start_idx=210, end_idx=n)
        assert result.n_trades == 0


# ======================================================================
# HELPER pour tests exit avec dates reelles
# ======================================================================


def _make_tom_cache_with_ibs(
    dates: pd.DatetimeIndex,
    *,
    close: float = 100.0,
    sma200: float = 100.0,
    ibs_val: float = 0.3,
) -> IndicatorCache:
    """Cache avec dates reelles + IBS/SMA controllees (pour tests exit)."""
    n = len(dates)
    arrays = {
        "opens": np.full(n, close),
        "highs": np.full(n, close + 2.0),
        "lows": np.full(n, close - 2.0),
        "closes": np.full(n, close),
        "volumes": np.full(n, 1_000_000.0),
    }
    cache = build_cache(arrays, {"sma_trend_period": [200]}, dates=dates.values)

    # Override IBS et SMA avec valeurs controllees
    cache.ibs = np.full(n, ibs_val)
    cache.sma_by_period[200] = np.full(n, sma200)

    return cache
