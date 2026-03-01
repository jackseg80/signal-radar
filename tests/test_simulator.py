"""Tests unitaires pour engine/simulator.py — moteur de simulation unifié.

Utilise une DummyStrategy contrôlable pour isoler le comportement du moteur.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pytest

from engine.backtest_config import BacktestConfig
from engine.fee_model import FeeModel, FEE_MODEL_US_STOCKS_USD
from engine.indicator_cache import IndicatorCache
from engine.simulator import simulate, _close_position
from engine.types import (
    BacktestResult,
    Direction,
    ExitSignal,
    Position,
    TradeResult,
)
from strategies.base import BaseStrategy
from tests.conftest import make_bt_config


# ══════════════════════════════════════════════════════════════════════════════
# DUMMY STRATEGY — stratégie factice contrôlable pour les tests
# ══════════════════════════════════════════════════════════════════════════════


class DummyStrategy(BaseStrategy):
    """Stratégie factice pour tests.

    entry_at : set d'index i où check_entry retourne entry_direction.
    exit_at  : set d'index i où check_exit retourne un ExitSignal.
    """

    name = "dummy"

    def __init__(
        self,
        *,
        entry_at: set[int] | None = None,
        exit_at: set[int] | None = None,
        entry_direction: Direction = Direction.LONG,
        exit_price_fn: Any = None,  # callable(i, cache) → float
        exit_reason: str = "test_exit",
        exit_apply_slippage: bool = False,
        warmup_override: int = 5,
    ) -> None:
        self._entry_at = entry_at or set()
        self._exit_at = exit_at or set()
        self._entry_direction = entry_direction
        self._exit_price_fn = exit_price_fn
        self._exit_reason = exit_reason
        self._exit_apply_slippage = exit_apply_slippage
        self._warmup_override = warmup_override

    def default_params(self) -> dict[str, Any]:
        return {"position_fraction": 0.2, "sl_percent": 0.0, "cooldown_candles": 0}

    def param_grid(self) -> dict[str, list]:
        return {}

    def check_entry(self, i: int, cache: IndicatorCache, params: dict) -> Direction:
        if i in self._entry_at:
            return self._entry_direction
        return Direction.FLAT

    def check_exit(
        self, i: int, cache: IndicatorCache, params: dict, position: Position,
    ) -> ExitSignal | None:
        if i in self._exit_at:
            if self._exit_price_fn is not None:
                price = self._exit_price_fn(i, cache)
            else:
                price = cache.closes[i]
            return ExitSignal(
                price=price,
                reason=self._exit_reason,
                apply_slippage=self._exit_apply_slippage,
            )
        return None

    def warmup(self, params: dict) -> int:
        return self._warmup_override


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════


def _make_cache(
    n: int = 100,
    *,
    closes: np.ndarray | None = None,
    opens: np.ndarray | None = None,
    highs: np.ndarray | None = None,
    lows: np.ndarray | None = None,
) -> IndicatorCache:
    """Crée un IndicatorCache simple pour les tests."""
    if closes is None:
        closes = np.full(n, 100.0)
    if opens is None:
        opens = closes.copy()
    if highs is None:
        highs = closes + 1.0
    if lows is None:
        lows = closes - 1.0
    return IndicatorCache(
        n_candles=n,
        opens=opens,
        highs=highs,
        lows=lows,
        closes=closes,
        volumes=np.full(n, 1_000_000.0),
        total_days=n * 365.0 / 252.0,
    )


def _zero_fee_config(**overrides: Any) -> BacktestConfig:
    """Config sans frais ni slippage."""
    defaults: dict[str, Any] = {
        "symbol": "TEST",
        "initial_capital": 100_000.0,
        "slippage_pct": 0.0,
        "max_wfo_drawdown_pct": 80.0,
        "fee_model": FeeModel(),
        "whole_shares": False,
    }
    defaults.update(overrides)
    return BacktestConfig(**defaults)


# ══════════════════════════════════════════════════════════════════════════════
# TESTS GAP-AWARE
# ══════════════════════════════════════════════════════════════════════════════


class TestGapAware:
    def test_gap_down_exits_at_open_not_sl(self) -> None:
        """Gap DOWN overnight LONG : exit à l'open, PAS au SL."""
        n = 50
        entry_i = 10
        gap_i = 11

        opens = np.full(n, 100.0)
        closes = np.full(n, 100.0)
        highs = np.full(n, 101.0)
        lows = np.full(n, 99.0)

        # Entry au open[10] = 100
        opens[entry_i] = 100.0
        closes[entry_i] = 101.0

        # Gap DOWN : open[11] = 80, bien sous SL (= 100 * (1 - 0.10) = 90)
        opens[gap_i] = 80.0
        highs[gap_i] = 82.0
        lows[gap_i] = 78.0
        closes[gap_i] = 81.0

        cache = _make_cache(n, opens=opens, closes=closes, highs=highs, lows=lows)
        strategy = DummyStrategy(entry_at={entry_i})
        params = {"position_fraction": 0.2, "sl_percent": 10.0, "cooldown_candles": 0}
        config = _zero_fee_config()

        result = simulate(strategy, cache, params, config)
        assert result.n_trades == 1
        # Exit à l'open (80), pas au SL (90)
        assert result.trades[0].exit_price == pytest.approx(80.0)
        assert result.trades[0].exit_reason == "gap_sl"
        assert result.trades[0].pnl < 0

    def test_gap_up_short_exits_at_open(self) -> None:
        """Gap UP overnight SHORT : exit à l'open."""
        n = 50
        entry_i = 10
        gap_i = 11

        opens = np.full(n, 100.0)
        closes = np.full(n, 100.0)
        highs = np.full(n, 101.0)
        lows = np.full(n, 99.0)

        # SHORT entry au open[10] = 100
        opens[entry_i] = 100.0
        closes[entry_i] = 99.0

        # Gap UP : open[11] = 120, au-dessus SL (= 100 * (1 + 0.10) = 110)
        opens[gap_i] = 120.0
        highs[gap_i] = 122.0
        lows[gap_i] = 118.0
        closes[gap_i] = 121.0

        cache = _make_cache(n, opens=opens, closes=closes, highs=highs, lows=lows)
        strategy = DummyStrategy(entry_at={entry_i}, entry_direction=Direction.SHORT)
        params = {"position_fraction": 0.2, "sl_percent": 10.0, "cooldown_candles": 0}
        config = _zero_fee_config()

        result = simulate(strategy, cache, params, config)
        assert result.n_trades == 1
        assert result.trades[0].exit_price == pytest.approx(120.0)
        assert result.trades[0].exit_reason == "gap_sl"

    def test_intraday_sl_exits_at_sl_price(self) -> None:
        """Intraday SL : low touche SL → exit au SL exact (+ slippage)."""
        n = 50
        entry_i = 10
        sl_i = 11

        opens = np.full(n, 100.0)
        closes = np.full(n, 100.0)
        highs = np.full(n, 101.0)
        lows = np.full(n, 99.0)

        opens[entry_i] = 100.0
        closes[entry_i] = 101.0

        # Open au-dessus du SL, mais low traverse le SL
        # SL = 100 * (1 - 0.10) = 90
        opens[sl_i] = 95.0
        highs[sl_i] = 96.0
        lows[sl_i] = 85.0  # Traverse SL
        closes[sl_i] = 88.0

        cache = _make_cache(n, opens=opens, closes=closes, highs=highs, lows=lows)
        strategy = DummyStrategy(entry_at={entry_i})
        params = {"position_fraction": 0.2, "sl_percent": 10.0, "cooldown_candles": 0}
        config = _zero_fee_config(slippage_pct=0.001)

        result = simulate(strategy, cache, params, config)
        assert result.n_trades == 1
        # Entry price = 100 * (1 + 0.001) = 100.1
        # SL = 100.1 * 0.9 = 90.09
        # Exit = 90.09 * (1 - 0.001) = 89.99991
        expected_entry = 100.0 * (1 + 0.001)
        expected_sl = expected_entry * 0.9
        expected_exit = expected_sl * (1 - 0.001)
        assert result.trades[0].exit_price == pytest.approx(expected_exit, rel=1e-4)
        assert result.trades[0].exit_reason == "intraday_sl"

    def test_no_sl_skips_sl_checks(self) -> None:
        """sl_percent=0 → pas de SL check, position survit au gap."""
        n = 50
        entry_i = 10
        exit_i = 15

        opens = np.full(n, 100.0)
        closes = np.full(n, 100.0)
        highs = np.full(n, 101.0)
        lows = np.full(n, 99.0)

        # "Gap" qui traverserait un SL hypothétique
        opens[11] = 80.0
        lows[11] = 78.0
        closes[11] = 82.0

        # Remonté et exit via stratégie
        closes[exit_i] = 105.0

        cache = _make_cache(n, opens=opens, closes=closes, highs=highs, lows=lows)
        strategy = DummyStrategy(entry_at={entry_i}, exit_at={exit_i})
        params = {"position_fraction": 0.2, "sl_percent": 0.0, "cooldown_candles": 0}
        config = _zero_fee_config()

        result = simulate(strategy, cache, params, config)
        assert result.n_trades == 1
        # Exit à 105 via stratégie, pas de SL
        assert result.trades[0].exit_price == pytest.approx(105.0)
        assert result.trades[0].exit_reason == "test_exit"


# ══════════════════════════════════════════════════════════════════════════════
# TESTS SIZING
# ══════════════════════════════════════════════════════════════════════════════


class TestSizing:
    def test_whole_shares_floor(self) -> None:
        """whole_shares=True → floor(qty), quantity entière."""
        n = 50
        entry_i = 10
        exit_i = 15

        opens = np.full(n, 100.0)
        closes = np.full(n, 110.0)

        cache = _make_cache(n, opens=opens, closes=closes)
        strategy = DummyStrategy(entry_at={entry_i}, exit_at={exit_i})
        # capital=100_000, fraction=0.2 → available=20_000, qty=200.0
        params = {"position_fraction": 0.2, "sl_percent": 0.0, "cooldown_candles": 0}
        config = _zero_fee_config(whole_shares=True)

        result = simulate(strategy, cache, params, config)
        assert result.n_trades == 1
        assert result.trades[0].quantity == 200.0  # floor(20000/100)
        assert result.trades[0].quantity == math.floor(result.trades[0].quantity)

    def test_whole_shares_skip_if_too_expensive(self) -> None:
        """Prix > capital alloué → n_skipped += 1, pas de trade."""
        n = 50
        entry_i = 10

        opens = np.full(n, 200_000.0)  # Trop cher pour 20k alloué
        closes = np.full(n, 200_000.0)

        cache = _make_cache(n, opens=opens, closes=closes)
        strategy = DummyStrategy(entry_at={entry_i})
        params = {"position_fraction": 0.2, "sl_percent": 0.0, "cooldown_candles": 0}
        config = _zero_fee_config(whole_shares=True)

        result = simulate(strategy, cache, params, config)
        assert result.n_trades == 0
        assert result.n_skipped == 1

    def test_fractional_shares_default(self) -> None:
        """whole_shares=False (défaut) → quantité fractionnelle."""
        n = 50
        entry_i = 10
        exit_i = 15

        opens = np.full(n, 150.0)
        closes = np.full(n, 155.0)

        cache = _make_cache(n, opens=opens, closes=closes)
        strategy = DummyStrategy(entry_at={entry_i}, exit_at={exit_i})
        params = {"position_fraction": 0.2, "sl_percent": 0.0, "cooldown_candles": 0}
        config = _zero_fee_config(whole_shares=False)

        result = simulate(strategy, cache, params, config)
        assert result.n_trades == 1
        # qty = 20_000 / 150 = 133.333...
        expected_qty = 20_000.0 / 150.0
        assert result.trades[0].quantity == pytest.approx(expected_qty, rel=1e-6)


# ══════════════════════════════════════════════════════════════════════════════
# TESTS ANTI-LOOK-AHEAD
# ══════════════════════════════════════════════════════════════════════════════


class TestAntiLookAhead:
    def test_entry_on_open_not_close(self) -> None:
        """L'entry_price doit être opens[i], pas closes[i]."""
        n = 50
        entry_i = 10
        exit_i = 15

        opens = np.full(n, 100.0)
        closes = np.full(n, 110.0)  # Close != Open

        cache = _make_cache(n, opens=opens, closes=closes)
        strategy = DummyStrategy(entry_at={entry_i}, exit_at={exit_i})
        params = {"position_fraction": 0.2, "sl_percent": 0.0, "cooldown_candles": 0}
        config = _zero_fee_config()  # slippage=0

        result = simulate(strategy, cache, params, config)
        assert result.n_trades == 1
        # Entry price = opens[10] = 100 (pas closes[10] = 110)
        assert result.trades[0].entry_price == pytest.approx(100.0)

    def test_signal_uses_previous_candle(self) -> None:
        """DummyStrategy.check_entry(i=10) → entrée sur open[10].

        La stratégie décide sur [i-1], le moteur entre sur open[i].
        Le moteur ne fournit aucune donnée future.
        """
        n = 50
        entry_i = 10
        exit_i = 12

        opens = np.full(n, 100.0)
        closes = np.full(n, 100.0)
        # opens[10] différent pour vérifier
        opens[entry_i] = 98.0
        closes[exit_i] = 105.0

        cache = _make_cache(n, opens=opens, closes=closes)
        strategy = DummyStrategy(entry_at={entry_i}, exit_at={exit_i})
        params = {"position_fraction": 0.2, "sl_percent": 0.0, "cooldown_candles": 0}
        config = _zero_fee_config()

        result = simulate(strategy, cache, params, config)
        assert result.n_trades == 1
        assert result.trades[0].entry_price == pytest.approx(98.0)
        assert result.trades[0].exit_price == pytest.approx(105.0)


# ══════════════════════════════════════════════════════════════════════════════
# TESTS SAME-CANDLE EXIT
# ══════════════════════════════════════════════════════════════════════════════


class TestSameCandleExit:
    def test_same_candle_exit(self) -> None:
        """Entry + exit le même jour (stratégie dit de sortir sur entry candle)."""
        n = 50
        entry_i = 10

        opens = np.full(n, 100.0)
        closes = np.full(n, 105.0)

        cache = _make_cache(n, opens=opens, closes=closes)
        # Entry ET exit sur la même candle
        strategy = DummyStrategy(entry_at={entry_i}, exit_at={entry_i})
        params = {"position_fraction": 0.2, "sl_percent": 0.0, "cooldown_candles": 0}
        config = _zero_fee_config()

        result = simulate(strategy, cache, params, config)
        assert result.n_trades == 1
        assert result.trades[0].entry_candle == entry_i
        assert result.trades[0].exit_candle == entry_i
        assert result.trades[0].holding_days == 0
        # Entry at 100, exit at close 105 → profit
        assert result.trades[0].pnl > 0


# ══════════════════════════════════════════════════════════════════════════════
# TESTS FEE
# ══════════════════════════════════════════════════════════════════════════════


class TestFees:
    def test_fees_reduce_pnl(self) -> None:
        """PnL brut > PnL net quand des frais sont appliqués."""
        n = 50
        entry_i = 10
        exit_i = 15

        opens = np.full(n, 100.0)
        closes = np.full(n, 100.0)
        closes[exit_i] = 110.0

        cache = _make_cache(n, opens=opens, closes=closes)
        strategy = DummyStrategy(entry_at={entry_i}, exit_at={exit_i})
        params = {"position_fraction": 0.2, "sl_percent": 0.0, "cooldown_candles": 0}

        # Sans frais
        config_no_fee = _zero_fee_config()
        result_no_fee = simulate(strategy, cache, params, config_no_fee)

        # Avec frais
        config_fee = _zero_fee_config(fee_model=FEE_MODEL_US_STOCKS_USD)
        result_fee = simulate(strategy, cache, params, config_fee)

        assert result_no_fee.n_trades == 1
        assert result_fee.n_trades == 1
        assert result_fee.trades[0].pnl < result_no_fee.trades[0].pnl

    def test_entry_fee_not_double_counted(self) -> None:
        """Bug Phase 1 : entry_fee soustrait 1 fois (dans pnl), pas 2 fois."""
        n = 50
        entry_i = 10
        exit_i = 15

        opens = np.full(n, 100.0)
        closes = np.full(n, 100.0)
        # Close = entry → gross PnL = 0. Net PnL = -(entry_fee + exit_fee)
        closes[exit_i] = 100.0

        cache = _make_cache(n, opens=opens, closes=closes)
        strategy = DummyStrategy(entry_at={entry_i}, exit_at={exit_i})
        params = {"position_fraction": 0.2, "sl_percent": 0.0, "cooldown_candles": 0}
        config = _zero_fee_config(fee_model=FEE_MODEL_US_STOCKS_USD)

        result = simulate(strategy, cache, params, config)
        assert result.n_trades == 1

        trade = result.trades[0]
        # PnL attendu : 0 - entry_fee - exit_fee - overnight(0 days)
        # = -(entry_fee + exit_fee)
        expected_pnl = -(trade.entry_fee + trade.exit_fee)
        assert trade.pnl == pytest.approx(expected_pnl, rel=1e-6)

        # Le capital final doit refléter : initial - entry_fee - exit_fee
        # (pas initial - 2 * entry_fee - exit_fee)
        expected_capital = config.initial_capital + trade.pnl
        assert result.final_capital == pytest.approx(expected_capital, rel=1e-6)


# ══════════════════════════════════════════════════════════════════════════════
# TESTS FORCE-CLOSE
# ══════════════════════════════════════════════════════════════════════════════


class TestForceClose:
    def test_force_close_excluded_from_trades(self) -> None:
        """Position ouverte en fin de données → pas dans trades."""
        n = 50
        entry_i = 10

        opens = np.full(n, 100.0)
        closes = np.full(n, 100.0)
        closes[-1] = 110.0  # Force-close à 110

        cache = _make_cache(n, opens=opens, closes=closes)
        # Pas d'exit dans la stratégie → force-close
        strategy = DummyStrategy(entry_at={entry_i})
        params = {"position_fraction": 0.2, "sl_percent": 0.0, "cooldown_candles": 0}
        config = _zero_fee_config()

        result = simulate(strategy, cache, params, config)
        assert result.n_trades == 0  # Force-close exclue
        # Mais le capital reflète la force-close
        assert result.final_capital != config.initial_capital


# ══════════════════════════════════════════════════════════════════════════════
# TESTS COOLDOWN
# ══════════════════════════════════════════════════════════════════════════════


class TestCooldown:
    def test_cooldown_prevents_immediate_reentry(self) -> None:
        """Après exit, pas de re-entry pendant cooldown_candles."""
        n = 50
        entry_i_1 = 10
        exit_i_1 = 12
        entry_i_2 = 13  # Pendant cooldown (= 5 candles)
        entry_i_3 = 20  # Après cooldown
        exit_i_3 = 25

        opens = np.full(n, 100.0)
        closes = np.full(n, 105.0)

        cache = _make_cache(n, opens=opens, closes=closes)
        strategy = DummyStrategy(
            entry_at={entry_i_1, entry_i_2, entry_i_3},
            exit_at={exit_i_1, exit_i_3},
        )
        params = {"position_fraction": 0.2, "sl_percent": 0.0, "cooldown_candles": 5}
        config = _zero_fee_config()

        result = simulate(strategy, cache, params, config)
        # Trade 1 : entry 10, exit 12 → OK
        # Trade 2 : entry 13, cooldown (exit 12 + 5 = 17) → BLOQUÉ
        # Trade 3 : entry 20, exit 25 → OK (cooldown terminé)
        assert result.n_trades == 2
        assert result.trades[0].entry_candle == entry_i_1
        assert result.trades[1].entry_candle == entry_i_3


# ══════════════════════════════════════════════════════════════════════════════
# TESTS DD GUARD
# ══════════════════════════════════════════════════════════════════════════════


class TestDDGuard:
    def test_dd_guard_stops_trading(self) -> None:
        """Drawdown > max → arrêt du trading."""
        n = 100

        opens = np.full(n, 100.0)
        closes = np.full(n, 100.0)

        # Premier trade : grosse perte pour trigger le DD guard
        opens[10] = 100.0
        closes[15] = 10.0  # -90% sur la position
        # Deuxième signal après le DD guard
        opens[30] = 100.0
        closes[35] = 200.0

        cache = _make_cache(n, opens=opens, closes=closes)
        strategy = DummyStrategy(
            entry_at={10, 30},
            exit_at={15, 35},
        )
        # position_fraction=1.0 → tout le capital, perte de 90% sur le trade
        params = {"position_fraction": 1.0, "sl_percent": 0.0, "cooldown_candles": 0}
        # DD guard à 80% → s'arrête si equity < 20% du peak
        config = _zero_fee_config(max_wfo_drawdown_pct=80.0)

        result = simulate(strategy, cache, params, config)
        # Après le premier trade, le capital est ~10% du peak
        # Le DD guard devrait empêcher le deuxième trade
        # (mais le premier trade complète avant le guard)
        assert result.n_trades <= 1


# ══════════════════════════════════════════════════════════════════════════════
# TESTS EXIT SLIPPAGE (apply_slippage flag)
# ══════════════════════════════════════════════════════════════════════════════


class TestExitSlippage:
    def test_strategy_exit_with_slippage_long(self) -> None:
        """apply_slippage=True sur LONG → prix dégradé (plus bas)."""
        n = 50
        entry_i = 10
        exit_i = 15
        slippage = 0.01  # 1%

        opens = np.full(n, 100.0)
        closes = np.full(n, 100.0)
        closes[exit_i] = 110.0

        cache = _make_cache(n, opens=opens, closes=closes)
        # Exit avec apply_slippage=True → prix = 110 * (1 - 1 * 0.01) = 108.9
        strategy = DummyStrategy(
            entry_at={entry_i},
            exit_at={exit_i},
            exit_apply_slippage=True,
        )
        params = {"position_fraction": 0.2, "sl_percent": 0.0, "cooldown_candles": 0}
        config = _zero_fee_config(slippage_pct=slippage)

        result = simulate(strategy, cache, params, config)
        assert result.n_trades == 1
        # Entry: 100 * (1 + 0.01) = 101 (slippage entry)
        # Exit: 110 * (1 - 0.01) = 108.9 (slippage exit)
        expected_exit = 110.0 * (1 - slippage)
        assert result.trades[0].exit_price == pytest.approx(expected_exit, rel=1e-4)

    def test_strategy_exit_without_slippage(self) -> None:
        """apply_slippage=False (défaut) → prix utilisé tel quel."""
        n = 50
        entry_i = 10
        exit_i = 15

        opens = np.full(n, 100.0)
        closes = np.full(n, 100.0)
        closes[exit_i] = 110.0

        cache = _make_cache(n, opens=opens, closes=closes)
        strategy = DummyStrategy(
            entry_at={entry_i},
            exit_at={exit_i},
            exit_apply_slippage=False,
        )
        params = {"position_fraction": 0.2, "sl_percent": 0.0, "cooldown_candles": 0}
        config = _zero_fee_config(slippage_pct=0.01)

        result = simulate(strategy, cache, params, config)
        assert result.n_trades == 1
        # Exit price = closes[15] = 110 (pas de slippage sur l'exit)
        assert result.trades[0].exit_price == pytest.approx(110.0)


# ══════════════════════════════════════════════════════════════════════════════
# TESTS BACKTEST RESULT METRICS
# ══════════════════════════════════════════════════════════════════════════════


class TestBacktestResultMetrics:
    def test_win_rate_calculation(self) -> None:
        """WR correct : 2 wins sur 3 trades."""
        n = 100
        opens = np.full(n, 100.0)
        closes = np.full(n, 100.0)

        # Trade 1 : win (close > open)
        closes[15] = 110.0
        # Trade 2 : loss (close < open)
        closes[25] = 90.0
        # Trade 3 : win
        closes[35] = 120.0

        cache = _make_cache(n, opens=opens, closes=closes)
        strategy = DummyStrategy(
            entry_at={10, 20, 30},
            exit_at={15, 25, 35},
        )
        params = {"position_fraction": 0.2, "sl_percent": 0.0, "cooldown_candles": 0}
        config = _zero_fee_config()

        result = simulate(strategy, cache, params, config)
        assert result.n_trades == 3
        assert result.win_rate == pytest.approx(2 / 3, abs=0.001)

    def test_profit_factor_calculation(self) -> None:
        """PF = gross_wins / gross_losses."""
        n = 100
        opens = np.full(n, 100.0)
        closes = np.full(n, 100.0)

        # Win : +10 * qty
        closes[15] = 110.0
        # Loss : -5 * qty
        closes[25] = 95.0

        cache = _make_cache(n, opens=opens, closes=closes)
        strategy = DummyStrategy(
            entry_at={10, 20},
            exit_at={15, 25},
        )
        params = {"position_fraction": 0.2, "sl_percent": 0.0, "cooldown_candles": 0}
        config = _zero_fee_config()

        result = simulate(strategy, cache, params, config)
        assert result.n_trades == 2
        # PF = 2000 / 1000 = 2.0 (approximativement)
        assert result.profit_factor > 1.5

    def test_net_return_pct(self) -> None:
        """Net return % = (final - initial) / initial * 100."""
        n = 50
        opens = np.full(n, 100.0)
        closes = np.full(n, 100.0)
        closes[15] = 110.0

        cache = _make_cache(n, opens=opens, closes=closes)
        strategy = DummyStrategy(entry_at={10}, exit_at={15})
        params = {"position_fraction": 0.2, "sl_percent": 0.0, "cooldown_candles": 0}
        config = _zero_fee_config()

        result = simulate(strategy, cache, params, config)
        expected = (result.final_capital - 100_000.0) / 100_000.0 * 100
        assert result.net_return_pct == pytest.approx(expected, rel=1e-6)

    def test_empty_trades_no_crash(self) -> None:
        """Aucun signal → 0 trades, pas de crash."""
        n = 50
        cache = _make_cache(n)
        strategy = DummyStrategy()  # Pas de signal
        params = {"position_fraction": 0.2, "sl_percent": 0.0, "cooldown_candles": 0}
        config = _zero_fee_config()

        result = simulate(strategy, cache, params, config)
        assert result.n_trades == 0
        assert result.final_capital == config.initial_capital
        assert result.win_rate == 0.0
        assert result.profit_factor == 0.0
        assert result.sharpe == 0.0


# ══════════════════════════════════════════════════════════════════════════════
# TEST CLOSE_POSITION HELPER
# ══════════════════════════════════════════════════════════════════════════════


class TestClosePosition:
    def test_long_profit(self) -> None:
        """PnL correct pour un LONG profitable sans frais."""
        pos = Position(
            entry_price=100.0, entry_candle=10, quantity=10.0,
            direction=Direction.LONG, capital_allocated=1000.0,
            entry_fee=0.0,
        )
        config = _zero_fee_config()
        trade, pnl = _close_position(pos, 110.0, "test", 15, config)
        assert pnl == pytest.approx(100.0)
        assert trade.holding_days == 5

    def test_short_profit(self) -> None:
        """PnL correct pour un SHORT profitable sans frais."""
        pos = Position(
            entry_price=110.0, entry_candle=10, quantity=10.0,
            direction=Direction.SHORT, capital_allocated=1100.0,
            entry_fee=0.0,
        )
        config = _zero_fee_config()
        trade, pnl = _close_position(pos, 100.0, "test", 15, config)
        assert pnl == pytest.approx(100.0)
