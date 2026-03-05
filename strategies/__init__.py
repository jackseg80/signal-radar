"""Centralized strategy registry and resolution logic."""

from __future__ import annotations
from typing import Type, TYPE_CHECKING

if TYPE_CHECKING:
    from strategies.base import BaseStrategy

# Import strategies
from strategies.rsi2_mean_reversion import RSI2MeanReversion
from strategies.ibs_mean_reversion import IBSMeanReversion
from strategies.turn_of_month import TurnOfMonth

# Central Registry
STRATEGIES_MAP: dict[str, Type[BaseStrategy]] = {
    "rsi2": RSI2MeanReversion,
    "ibs": IBSMeanReversion,
    "tom": TurnOfMonth,
}

# Alias mapping for various sources (Frontend, DB, CLI)
STRATEGY_ALIASES = {
    "rsi2_mean_reversion": "rsi2",
    "ibs_mean_reversion": "ibs",
    "turn_of_month": "tom",
    "turn": "tom"
}

def resolve_strategy_key(name: str | None) -> str | None:
    """Resolve a strategy name or alias to a canonical short key."""
    if not name:
        return None
    
    name = name.lower().strip()
    if name in STRATEGIES_MAP:
        return name
    if name in STRATEGY_ALIASES:
        return STRATEGY_ALIASES[name]
    
    # Fuzzy matching for names containing the key
    for k in STRATEGIES_MAP:
        if k in name:
            return k
            
    return None

def get_strategy_class(name: str) -> Type[BaseStrategy] | None:
    """Get the strategy class for a given name/alias."""
    key = resolve_strategy_key(name)
    return STRATEGIES_MAP.get(key) if key else None

def get_strategy_instance(name: str) -> BaseStrategy | None:
    """Get an initialized instance of a strategy by name/alias."""
    cls = get_strategy_class(name)
    return cls() if cls else None
