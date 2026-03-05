"""Tests unitaires pour engine/types.py."""

from __future__ import annotations

import math

import pytest

from engine.types import BacktestResult, Direction, ExitSignal, Position, TradeResult


class TestDirection:
    def test_direction_arithmetic_long(self) -> None:
        """Direction.LONG * scalaire = scalaire positif."""
        assert Direction.LONG * 100 == 100
        assert Direction.LONG * -50 == -50

    def test_direction_arithmetic_short(self) -> None:
        """Direction.SHORT * scalaire = scalaire négatif."""
        assert Direction.SHORT * 100 == -100
        assert Direction.SHORT * -50 == 50

    def test_direction_flat_is_zero(self) -> None:
        """Direction.FLAT * anything = 0."""
        assert Direction.FLAT * 999 == 0

    def test_direction_int_values(self) -> None:
        """Vérifier les valeurs IntEnum."""
        assert int(Direction.SHORT) == -1
        assert int(Direction.FLAT) == 0
        assert int(Direction.LONG) == 1


class TestExitSignal:
    def test_exit_signal_fields(self) -> None:
        """ExitSignal stocke price et reason."""
        sig = ExitSignal(price=105.0, reason="sma_exit")
        assert sig.price == 105.0
        assert sig.reason == "sma_exit"
        assert sig.apply_slippage is False

    def test_exit_signal_with_slippage(self) -> None:
        """ExitSignal avec apply_slippage=True."""
        sig = ExitSignal(price=95.0, reason="trailing", apply_slippage=True)
        assert sig.apply_slippage is True


class TestPosition:
    def test_position_default_state(self) -> None:
        """Position.state est un dict vide par défaut."""
        pos = Position(
            entry_price=100.0,
            entry_candle=10,
            quantity=50.0,
            direction=Direction.LONG,
            capital_allocated=5000.0,
            entry_fee=1.5,
        )
        assert pos.state == {}
        assert pos.sl_price == 0.0

    def test_position_with_state(self) -> None:
        """Position.state peut stocker des données strategy-specific."""
        pos = Position(
            entry_price=100.0,
            entry_candle=10,
            quantity=50.0,
            direction=Direction.LONG,
            capital_allocated=5000.0,
            entry_fee=1.5,
            state={"hwm": 105.0, "trailing_level": 97.0},
        )
        assert pos.state["hwm"] == 105.0


class TestBacktestResult:
    def test_empty_trades_no_crash(self) -> None:
        """BacktestResult avec 0 trades → metrics = 0, pas de crash."""
        result = BacktestResult(
            trades=[], final_capital=100_000.0, initial_capital=100_000.0,
        )
        assert result.n_trades == 0
        assert result.win_rate == 0.0
        assert result.profit_factor == 0.0
        assert result.net_return_pct == 0.0
        assert result.sharpe == 0.0
        assert result.pnls == []
        assert result.returns == []

    def test_backtest_result_properties(self) -> None:
        """Vérifier PF, WR, net_return sur des trades connus."""
        trades = [
            TradeResult(
                direction=Direction.LONG, entry_price=100.0, exit_price=110.0,
                entry_candle=10, exit_candle=15, quantity=10.0,
                pnl=100.0, return_pct=0.02, holding_days=5,
                exit_reason="sma_exit", entry_fee=1.0, exit_fee=1.0,
            ),
            TradeResult(
                direction=Direction.LONG, entry_price=100.0, exit_price=95.0,
                entry_candle=20, exit_candle=25, quantity=10.0,
                pnl=-50.0, return_pct=-0.01, holding_days=5,
                exit_reason="intraday_sl", entry_fee=1.0, exit_fee=1.0,
            ),
            TradeResult(
                direction=Direction.LONG, entry_price=100.0, exit_price=108.0,
                entry_candle=30, exit_candle=35, quantity=10.0,
                pnl=80.0, return_pct=0.016, holding_days=5,
                exit_reason="sma_exit", entry_fee=1.0, exit_fee=1.0,
            ),
        ]
        result = BacktestResult(
            trades=trades,
            final_capital=100_130.0,
            initial_capital=100_000.0,
        )
        assert result.n_trades == 3
        # WR: 2 wins / 3 trades = 0.6667
        assert result.win_rate == pytest.approx(2 / 3, abs=0.001)
        # PF: (100 + 80) / 50 = 3.6
        assert result.profit_factor == pytest.approx(3.6, abs=0.01)
        # Net return: (100_130 - 100_000) / 100_000 * 100 = 0.13%
        assert result.net_return_pct == pytest.approx(0.13, abs=0.01)

    def test_profit_factor_no_losses(self) -> None:
        """PF = inf si que des gains."""
        trades = [
            TradeResult(
                direction=Direction.LONG, entry_price=100.0, exit_price=110.0,
                entry_candle=10, exit_candle=15, quantity=10.0,
                pnl=100.0, return_pct=0.02, holding_days=5,
                exit_reason="sma_exit", entry_fee=0.0, exit_fee=0.0,
            ),
        ]
        result = BacktestResult(
            trades=trades, final_capital=100_100.0, initial_capital=100_000.0,
        )
        assert result.profit_factor == float("inf")

    def test_sharpe_calculation(self) -> None:
        """Sharpe > 0 si tous les returns sont positifs."""
        trades = [
            TradeResult(
                direction=Direction.LONG, entry_price=100.0, exit_price=110.0,
                entry_candle=i * 10, exit_candle=i * 10 + 5, quantity=10.0,
                pnl=100.0, return_pct=0.02, holding_days=5,
                exit_reason="sma_exit", entry_fee=0.0, exit_fee=0.0,
            )
            for i in range(5)
        ]
        result = BacktestResult(
            trades=trades, final_capital=100_500.0, initial_capital=100_000.0,
        )
        # Tous les returns identiques → std = 0 → sharpe = 0
        # (variance nulle, pas de ratio de Sharpe calculable)
        assert result.sharpe == 0.0

    def test_sharpe_with_variance(self) -> None:
        """Sharpe calculé correctement avec variance non nulle."""
        trades = [
            TradeResult(
                direction=Direction.LONG, entry_price=100.0, exit_price=110.0,
                entry_candle=0, exit_candle=5, quantity=10.0,
                pnl=100.0, return_pct=0.02, holding_days=5,
                exit_reason="sma_exit", entry_fee=0.0, exit_fee=0.0,
            ),
            TradeResult(
                direction=Direction.LONG, entry_price=100.0, exit_price=105.0,
                entry_candle=10, exit_candle=15, quantity=10.0,
                pnl=50.0, return_pct=0.01, holding_days=5,
                exit_reason="sma_exit", entry_fee=0.0, exit_fee=0.0,
            ),
            TradeResult(
                direction=Direction.LONG, entry_price=100.0, exit_price=95.0,
                entry_candle=20, exit_candle=25, quantity=10.0,
                pnl=-50.0, return_pct=-0.01, holding_days=5,
                exit_reason="intraday_sl", entry_fee=0.0, exit_fee=0.0,
            ),
        ]
        result = BacktestResult(
            trades=trades, final_capital=100_100.0, initial_capital=100_000.0,
        )
        # mean = (0.02 + 0.01 - 0.01) / 3 ≈ 0.00667
        # std ≈ 0.01247
        # span = 25 - 0 = 25 trading days
        # span_years = 25 / 252 ≈ 0.0992
        # trades_per_year = 3 / 0.0992 ≈ 30.24
        # sharpe = 0.00667 / 0.01247 * sqrt(30.24) ≈ 2.94
        assert result.sharpe > 0
        assert not math.isinf(result.sharpe)
        assert result.sharpe == pytest.approx(2.94, abs=0.05)

    def test_sharpe_annualization_exact(self) -> None:
        """Vérifie l'annualisation du Sharpe sur exactement 1 an."""
        import numpy as np
        # 10 trades répartis sur 252 jours (ex: un trade tous les 25 jours)
        # Returns: 1% and 3% alternating
        rets = [0.01, 0.03] * 5
        trades = []
        for i, ret in enumerate(rets):
            trades.append(
                TradeResult(
                    direction=Direction.LONG, entry_price=100.0, exit_price=100.0 * (1 + ret),
                    entry_candle=i * 25, exit_candle=i * 25 + 2, quantity=1.0,
                    pnl=ret * 100, return_pct=ret, holding_days=2,
                    exit_reason="signal", entry_fee=0.0, exit_fee=0.0,
                )
            )
        
        # Duration: last_exit - first_entry = (9 * 25 + 2) - 0 = 227 days
        # span_years = 227 / 252 ≈ 0.9008
        # trades_per_year = 10 / 0.9008 ≈ 11.10
        # mean = 0.02, std = 0.01
        # sharpe_theoretical = (0.02 / 0.01) * sqrt(11.10) ≈ 6.66
        
        result = BacktestResult(trades=trades, final_capital=1000.0, initial_capital=900.0)
        assert result.sharpe == pytest.approx(6.66, abs=0.05)
