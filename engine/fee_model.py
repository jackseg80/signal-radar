"""Modèle de frais par classe d'actifs pour signal-radar.

Remplace le flat taker_fee de scalp-radar par un modèle complet :
commission fixe + variable, spread, conversion FX, taxe, overnight.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FeeModel:
    """Modèle de frais par classe d'actifs.

    Tous les champs sont en fraction (0.001 = 0.1%),
    sauf commission_per_trade qui est en devise (ex: $1).
    """

    name: str = "default"
    commission_per_trade: float = 0.0    # Fixe par ORDRE (ex: $1 actions US)
    commission_pct: float = 0.0          # Variable (ex: 0.10% actions EU)
    spread_pct: float = 0.0              # Spread moyen (ex: 0.05% actions, 0.01% forex)
    fx_conversion_pct: float = 0.0       # Frais de change (ex: 0.25% si EUR→USD)
    tax_pct: float = 0.0                 # TTF/stamp duty (ex: 0.3% France)
    overnight_daily_pct: float = 0.0     # Funding CFD (0 si pas de leverage)

    def total_entry_cost(self, notional: float) -> float:
        """Coût total à l'entrée d'un trade."""
        return (
            self.commission_per_trade
            + notional * self.commission_pct
            + notional * self.spread_pct / 2  # demi-spread à l'entrée
            + notional * self.fx_conversion_pct
            + notional * self.tax_pct
        )

    def total_exit_cost(self, notional: float) -> float:
        """Coût total à la sortie d'un trade.

        Pas de tax à la sortie (TTF = achat seulement en France/UK).
        """
        return (
            self.commission_per_trade
            + notional * self.commission_pct
            + notional * self.spread_pct / 2  # demi-spread à la sortie
            + notional * self.fx_conversion_pct
        )

    def overnight_cost(self, notional: float, n_days: int) -> float:
        """Coût de financement overnight."""
        return notional * self.overnight_daily_pct * n_days


# ─── Presets par classe d'actifs ─────────────────────────────────────────────

FEE_MODEL_US_STOCKS = FeeModel(
    name="us_stocks",
    commission_per_trade=1.0,
    commission_pct=0.0,
    spread_pct=0.0005,          # 0.05% spread moyen large caps
    fx_conversion_pct=0.0025,   # 0.25% EUR→USD (compte SaxoBank EUR)
    tax_pct=0.0,
    overnight_daily_pct=0.0,
)

FEE_MODEL_US_STOCKS_USD = FeeModel(
    name="us_stocks_usd_account",
    commission_per_trade=1.0,
    commission_pct=0.0,
    spread_pct=0.0005,          # 0.05% spread moyen large caps (plus large que ETFs)
    fx_conversion_pct=0.0,      # Compte USD — pas de conversion
    tax_pct=0.0,
    overnight_daily_pct=0.0,
)

FEE_MODEL_US_ETFS_USD = FeeModel(
    name="us_etfs_usd_account",
    commission_per_trade=1.0,
    commission_pct=0.0,
    spread_pct=0.0003,          # 0.03% spread ETFs liquides (SPY, QQQ)
    fx_conversion_pct=0.0,      # Compte USD — pas de conversion
    tax_pct=0.0,
    overnight_daily_pct=0.0,
)

FEE_MODEL_FOREX = FeeModel(
    name="forex_majors",
    commission_per_trade=0.0,
    commission_pct=0.0,
    spread_pct=0.0001,          # ~1 pip = 0.01% sur majeures
    fx_conversion_pct=0.0,
    tax_pct=0.0,
    overnight_daily_pct=0.0,
)

FEE_MODEL_FOREX_SAXO = FeeModel(
    name="forex_saxo",
    commission_per_trade=0.0,       # Pas de commission sur forex Saxo
    commission_pct=0.0,
    spread_pct=0.00015,             # ~1.5 pips sur majors ~ 0.015%
    fx_conversion_pct=0.0,
    tax_pct=0.0,
    overnight_daily_pct=0.0,        # Swap ignore pour backtest (holding < 5j)
)

FEE_MODEL_EU_STOCKS = FeeModel(
    name="eu_stocks",
    commission_per_trade=10.0,
    commission_pct=0.001,       # 0.10%
    spread_pct=0.001,           # 0.10% spread
    fx_conversion_pct=0.0,
    tax_pct=0.003,              # 0.30% TTF France
    overnight_daily_pct=0.0,
)
