"""Types partagés pour le framework de backtesting.

Direction, Position, ExitSignal, TradeResult, BacktestResult — utilisés
par le moteur (engine/simulator.py) et les stratégies (strategies/base.py).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class Direction(IntEnum):
    """Direction de trade. IntEnum pour arithmétique directe dans le PnL."""

    SHORT = -1
    FLAT = 0
    LONG = 1


@dataclass
class ExitSignal:
    """Signal de sortie avec prix et raison.

    apply_slippage : si True, le moteur applique le slippage directionnel
    sur le prix (price * (1 - direction * slippage_pct)). Les exits "at close"
    (SMA, RSI, channel, trend break) laissent False (prix observé). Les exits
    "at level" (trailing, signal) mettent True (prix théorique).
    """

    price: float
    reason: str  # "sma_exit", "trend_break", "trailing", "channel", "signal", etc.
    apply_slippage: bool = False


@dataclass
class Position:
    """Position ouverte avec état strategy-specific."""

    entry_price: float
    entry_candle: int
    quantity: float
    direction: Direction
    capital_allocated: float
    entry_fee: float
    sl_price: float = 0.0  # 0.0 = pas de SL (ex: MR Connors)
    state: dict[str, Any] = field(default_factory=dict)  # trailing_level, hwm, etc.


@dataclass
class TradeResult:
    """Résultat d'un trade complété.

    return_pct = pnl / capital_allocated (return sur capital investi).
    Diffère de l'ancien calcul (pnl / capital total post-trade) mais plus
    propre. Note Step 21 : les PnL en $ sont identiques entre ancien et
    nouveau moteur ; le Sharpe peut différer légèrement.
    """

    direction: Direction
    entry_price: float
    exit_price: float
    entry_candle: int
    exit_candle: int
    quantity: float
    pnl: float  # PnL net (après fees)
    return_pct: float  # pnl / capital_allocated
    holding_days: int
    exit_reason: str
    entry_fee: float
    exit_fee: float


@dataclass
class BacktestResult:
    """Résultat complet d'un backtest."""

    trades: list[TradeResult]
    final_capital: float
    initial_capital: float
    n_skipped: int = 0  # Trades skippés car qty < 1 (whole shares)

    @property
    def n_trades(self) -> int:
        return len(self.trades)

    @property
    def pnls(self) -> list[float]:
        return [t.pnl for t in self.trades]

    @property
    def returns(self) -> list[float]:
        return [t.return_pct for t in self.trades]

    @property
    def win_rate(self) -> float:
        if not self.trades:
            return 0.0
        return sum(1 for t in self.trades if t.pnl > 0) / len(self.trades)

    @property
    def profit_factor(self) -> float:
        gross_profit = sum(t.pnl for t in self.trades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in self.trades if t.pnl <= 0))
        if gross_loss == 0:
            return float("inf") if gross_profit > 0 else 0.0
        return gross_profit / gross_loss

    @property
    def net_return_pct(self) -> float:
        if self.initial_capital == 0:
            return 0.0
        return (self.final_capital - self.initial_capital) / self.initial_capital * 100

    @property
    def sharpe(self) -> float:
        """Sharpe annualisé basé sur la fréquence réelle des trades.

        Annualise avec sqrt(trades_per_year) au lieu de sqrt(252),
        car self.returns sont des per-trade returns, pas des daily returns.
        La durée couverte est estimée depuis le premier entry au dernier exit.
        """
        if len(self.returns) < 2:
            return 0.0
        import numpy as np

        rets = np.array(self.returns)
        if rets.std() == 0:
            return 0.0

        # Estimer trades/an depuis la durée couverte en trading days
        first_entry = self.trades[0].entry_candle
        last_exit = self.trades[-1].exit_candle
        span_trading_days = max(last_exit - first_entry, 1)
        span_years = span_trading_days / 252.0
        trades_per_year = len(self.trades) / span_years

        return float(rets.mean() / rets.std() * math.sqrt(trades_per_year))
