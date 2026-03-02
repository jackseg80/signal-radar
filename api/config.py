"""API configuration."""

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "signal_radar.db"
CONFIG_PATH = PROJECT_ROOT / "config" / "production_params.yaml"


def load_production_config() -> dict:
    """Load production_params.yaml."""
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)
