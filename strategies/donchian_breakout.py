"""Configuration de la stratégie Donchian Breakout pour signal-radar.

Pas de logique — juste la dataclass de configuration et les defaults.
La logique de simulation est dans engine/fast_backtest.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DonchianBreakoutConfig:
    """Configuration de la stratégie Donchian Breakout."""

    name: str = "donchian_breakout"
    enabled: bool = True
    timeframe: str = "1d"

    # Entry — Donchian channel
    entry_mode: str = "donchian"
    donchian_entry_period: int = 50
    donchian_exit_period: int = 20

    # ADX filter
    adx_period: int = 14
    adx_threshold: float = 20.0   # 0 = disabled

    # Exit
    atr_period: int = 14
    trailing_atr_mult: float = 4.0
    exit_mode: str = "trailing"   # "trailing" ou "channel"
    sl_percent: float = 10.0

    # Sizing
    position_fraction: float = 0.3
    cooldown_candles: int = 3
    sides: list[str] = field(default_factory=lambda: ["long"])

    def to_params(self) -> dict:
        """Convertit en dict de params pour _simulate_trend_follow."""
        return {
            "entry_mode": self.entry_mode,
            "donchian_entry_period": self.donchian_entry_period,
            "donchian_exit_period": self.donchian_exit_period,
            "adx_period": self.adx_period,
            "adx_threshold": self.adx_threshold,
            "atr_period": self.atr_period,
            "trailing_atr_mult": self.trailing_atr_mult,
            "exit_mode": self.exit_mode,
            "sl_percent": self.sl_percent,
            "position_fraction": self.position_fraction,
            "cooldown_candles": self.cooldown_candles,
            "sides": self.sides,
        }
