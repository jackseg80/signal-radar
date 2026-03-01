"""Configuration de backtest pour signal-radar.

Dataclass légère remplaçant le BacktestConfig crypto de scalp-radar.
Pas de leverage, pas de taker_fee, pas de maker_fee.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.fee_model import FeeModel


@dataclass
class BacktestConfig:
    """Configuration pour un backtest trend following daily."""

    symbol: str = ""
    initial_capital: float = 100_000.0
    slippage_pct: float = 0.0003          # 0.03% slippage actions
    max_wfo_drawdown_pct: float = 80.0    # Kill switch DD (%)
    fee_model: FeeModel = field(default_factory=FeeModel)
    whole_shares: bool = False  # True → floor(qty), skip si qty < 1
