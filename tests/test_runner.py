"""Tests for cli/runner.py -- extracted run_screen/run_validate functions."""

from __future__ import annotations

import pytest

from cli.runner import (
    FEE_MODELS,
    MARKET_DEFAULTS,
    STRATEGIES,
    ScreenResult,
    ValidateResult,
    _merge_grid_with_defaults,
    resolve_market_params,
    run_screen,
    run_validate,
)
from config.universe_loader import load_universe


class TestConstants:
    """Test that centralized constants are correct."""

    def test_strategies_keys(self) -> None:
        assert "rsi2" in STRATEGIES
        assert "ibs" in STRATEGIES
        assert "tom" in STRATEGIES
        assert "ibs_tom" in STRATEGIES
        assert "donchian" in STRATEGIES

    def test_strategies_count(self) -> None:
        assert len(STRATEGIES) == 5

    def test_fee_models_keys(self) -> None:
        assert "us_stocks_usd_account" in FEE_MODELS
        assert "us_etfs_usd_account" in FEE_MODELS
        assert "forex_saxo" in FEE_MODELS
        assert "default" in FEE_MODELS

    def test_market_defaults_keys(self) -> None:
        assert "us_stocks" in MARKET_DEFAULTS
        assert "us_etfs" in MARKET_DEFAULTS
        assert "forex" in MARKET_DEFAULTS

    def test_market_defaults_values(self) -> None:
        assert MARKET_DEFAULTS["us_stocks"]["capital"] == 10_000.0
        assert MARKET_DEFAULTS["us_stocks"]["whole_shares"] is True
        assert MARKET_DEFAULTS["us_etfs"]["capital"] == 100_000.0
        assert MARKET_DEFAULTS["us_etfs"]["whole_shares"] is False


class TestResolveMarketParams:
    """Test resolve_market_params()."""

    def test_stocks_defaults(self) -> None:
        uc = load_universe("us_stocks_large")
        cap, ws, fm, name = resolve_market_params(uc)
        assert cap == 10_000.0
        assert ws is True
        assert name == "us_stocks_usd_account"

    def test_etfs_defaults(self) -> None:
        uc = load_universe("us_etfs_broad")
        cap, ws, fm, name = resolve_market_params(uc)
        assert cap == 100_000.0
        assert ws is False
        assert name == "us_etfs_usd_account"

    def test_capital_override(self) -> None:
        uc = load_universe("us_stocks_large")
        cap, ws, fm, name = resolve_market_params(uc, capital=50_000.0)
        assert cap == 50_000.0
        assert ws is True  # unchanged

    def test_whole_shares_override(self) -> None:
        uc = load_universe("us_stocks_large")
        cap, ws, fm, name = resolve_market_params(uc, whole_shares=False)
        assert ws is False
        assert cap == 10_000.0  # unchanged

    def test_fee_model_override(self) -> None:
        uc = load_universe("us_stocks_large")
        cap, ws, fm, name = resolve_market_params(uc, fee_model_name="forex_saxo")
        assert name == "forex_saxo"
        assert fm.commission_per_trade == 0.0


class TestMergeGridWithDefaults:
    """Test _merge_grid_with_defaults()."""

    def test_rsi2_includes_periods(self) -> None:
        strategy = STRATEGIES["rsi2"]()
        grid = _merge_grid_with_defaults(strategy)
        assert "rsi_period" in grid
        assert "sma_trend_period" in grid
        assert "sma_exit_period" in grid

    def test_tom_minimal(self) -> None:
        strategy = STRATEGIES["tom"]()
        grid = _merge_grid_with_defaults(strategy)
        # TOM has no period keys in param_grid, but default_params has none either
        assert isinstance(grid, dict)

    def test_returns_lists(self) -> None:
        strategy = STRATEGIES["ibs"]()
        grid = _merge_grid_with_defaults(strategy)
        for key, val in grid.items():
            assert isinstance(val, list), f"{key} should be a list"


class TestRunScreenValidation:
    """Test run_screen/run_validate are importable and raise on bad input."""

    def test_run_screen_importable(self) -> None:
        assert callable(run_screen)

    def test_run_validate_importable(self) -> None:
        assert callable(run_validate)

    def test_unknown_strategy_screen(self) -> None:
        with pytest.raises(ValueError, match="Unknown strategy"):
            run_screen("nonexistent", "us_stocks_large")

    def test_unknown_strategy_validate(self) -> None:
        with pytest.raises(ValueError, match="Unknown strategy"):
            run_validate("nonexistent", "us_stocks_large")

    def test_unknown_universe_screen(self) -> None:
        with pytest.raises(FileNotFoundError):
            run_screen("rsi2", "nonexistent_universe_xyz")

    def test_unknown_universe_validate(self) -> None:
        with pytest.raises(FileNotFoundError):
            run_validate("rsi2", "nonexistent_universe_xyz")

    def test_screen_result_dataclass(self) -> None:
        r = ScreenResult(
            strategy_key="rsi2",
            strategy_name="rsi2_mean_reversion",
            universe_name="test",
            assets=[{"symbol": "META", "profit_factor": 2.0}],
            n_profitable=1,
        )
        assert r.strategy_key == "rsi2"
        assert r.n_profitable == 1

    def test_validate_result_dataclass(self) -> None:
        r = ValidateResult(
            strategy_key="ibs",
            strategy_name="ibs_mean_reversion",
            universe_name="test",
        )
        assert r.strategy_key == "ibs"
