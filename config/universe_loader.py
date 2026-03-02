"""Charge les univers d'assets depuis les fichiers YAML."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

UNIVERSES_DIR = Path(__file__).parent / "universes"


@dataclass
class UniverseConfig:
    """Configuration d'un univers d'assets.

    Attributes:
        name: Nom lisible (ex: "US Large Cap Stocks")
        description: Description de l'univers
        market: Type de marche (us_stocks, us_etfs, forex)
        default_fee_model: Nom du fee model par defaut
        default_start: Date de debut par defaut
        assets: Mapping {symbol: start_date}
    """

    name: str
    description: str
    market: str
    default_fee_model: str
    default_start: str
    assets: dict[str, str]


def load_universe(name: str) -> UniverseConfig:
    """Charge un univers par nom (sans extension).

    Args:
        name: Nom du fichier YAML sans extension
              (ex: "us_stocks_large" -> config/universes/us_stocks_large.yaml)

    Returns:
        UniverseConfig avec tous les assets et metadata

    Raises:
        FileNotFoundError: Si le fichier YAML n'existe pas
    """
    path = UNIVERSES_DIR / f"{name}.yaml"
    if not path.exists():
        available = list_universes()
        raise FileNotFoundError(
            f"Universe '{name}' not found at {path}. "
            f"Available: {', '.join(available)}"
        )

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    default_start = data.get("default_start", "2005-01-01")
    assets: dict[str, str] = {}
    for symbol, config in data["assets"].items():
        if config and "start" in config:
            assets[symbol] = config["start"]
        else:
            assets[symbol] = default_start

    return UniverseConfig(
        name=data["name"],
        description=data.get("description", ""),
        market=data.get("market", "unknown"),
        default_fee_model=data.get("default_fee_model", "default"),
        default_start=default_start,
        assets=assets,
    )


def list_universes() -> list[str]:
    """Liste les univers disponibles (noms sans extension)."""
    return sorted(p.stem for p in UNIVERSES_DIR.glob("*.yaml"))
