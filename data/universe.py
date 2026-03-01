"""Gestion des univers d'assets pour signal-radar."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class AssetConfig:
    """Configuration d'un asset dans l'univers."""

    symbols: list[str]
    market: str
    fee_model: str
    sides: list[str]


def load_asset_config(config_path: str | Path) -> AssetConfig:
    """Charge un fichier de config assets YAML."""
    with open(config_path) as f:
        raw = yaml.safe_load(f)
    return AssetConfig(
        symbols=raw["symbols"],
        market=raw["market"],
        fee_model=raw["fee_model"],
        sides=raw["sides"],
    )
