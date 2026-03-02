"""API configuration."""

from pathlib import Path

from loguru import logger
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "signal_radar.db"
CONFIG_PATH = PROJECT_ROOT / "config" / "production_params.yaml"

_config_cache: dict | None = None


def load_production_config() -> dict:
    """Load production_params.yaml with caching and error handling.

    Returns a default empty config if the file is missing or malformed,
    so the API stays up even without the config file.
    """
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    try:
        with open(CONFIG_PATH) as f:
            _config_cache = yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.warning("Config file not found: {}", CONFIG_PATH)
        _config_cache = {}
    except yaml.YAMLError as exc:
        logger.error("Invalid YAML in {}: {}", CONFIG_PATH, exc)
        _config_cache = {}

    return _config_cache
