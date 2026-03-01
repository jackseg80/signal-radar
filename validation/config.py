"""Configuration pour le pipeline de validation."""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.fee_model import FeeModel


@dataclass
class ValidationConfig:
    """Configuration complète pour une validation multi-asset.

    Paramètres:
        universe: Mapping symbol → date de début (ex: {"META": "2012-06-01"})
        data_end: Fin des données (ex: "2025-01-01")
        is_end: Fin in-sample / début OOS (ex: "2014-01-01")
        initial_capital: Capital initial par asset
        whole_shares: True → floor(qty), skip si qty < 1
        slippage_pct: Slippage en fraction (0.0003 = 0.03%)
        fee_model: Modèle de frais
        min_profitable_pct: Seuil robustesse (% combos avec PF > 1.0)
        oos_mid: Date de split OOS en deux sous-périodes (auto si None)
        ttest_alpha: Seuil de significativité t-test
        conditional_p_max: p-value max pour verdict CONDITIONAL
    """

    universe: dict[str, str]
    data_end: str
    is_end: str
    initial_capital: float = 10_000.0
    whole_shares: bool = True
    slippage_pct: float = 0.0003
    fee_model: FeeModel = field(default_factory=FeeModel)
    min_profitable_pct: float = 80.0
    oos_mid: str | None = None
    ttest_alpha: float = 0.10
    conditional_p_max: float = 0.15
