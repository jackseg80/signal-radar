"""Config and settings endpoints."""

from fastapi import APIRouter
from api.config import load_production_config

router = APIRouter()


@router.get("/settings")
def get_settings() -> dict:
    """Returns global application settings from production_params.yaml."""
    config = load_production_config()
    # Default to 5000 if not found in config
    initial_capital = config.get("capital", 5000)
    
    return {
        "initial_capital": initial_capital,
    }
