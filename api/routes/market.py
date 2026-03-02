"""Market overview endpoint."""

from fastapi import APIRouter, Depends

from data.db import SignalRadarDB
from api.config import load_production_config
from api.dependencies import get_db

router = APIRouter()

INDICATOR_LABELS = {
    "rsi2": "RSI(2)",
    "ibs": "IBS",
    "tom": "Days left",
}


@router.get("/overview")
def get_market_overview(
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Market overview: latest indicators for all tracked assets."""
    config = load_production_config()
    strategies_cfg = config.get("strategies", {})

    # Build asset -> strategy membership mapping
    asset_membership: dict[str, dict[str, bool]] = {}  # symbol -> {strat: in_universe}
    for strat_name, strat_cfg in strategies_cfg.items():
        if not strat_cfg.get("enabled", False):
            continue
        for sym in strat_cfg.get("universe", []):
            asset_membership.setdefault(sym, {})[strat_name] = True
        for sym in strat_cfg.get("watchlist", []):
            asset_membership.setdefault(sym, {})[strat_name] = False

    # Get latest signals for all strategies
    ts, all_signals = db.get_latest_signals()

    # Index signals by (strategy, symbol)
    signal_map: dict[tuple[str, str], dict] = {}
    for s in all_signals:
        signal_map[(s["strategy"], s["symbol"])] = s

    # Get open positions
    open_positions = db.get_open_positions()
    open_pos_map: dict[str, list[str]] = {}  # symbol -> [strategies]
    for p in open_positions:
        open_pos_map.setdefault(p["symbol"], []).append(p["strategy"])

    # Build response
    assets = []
    for sym in sorted(asset_membership.keys()):
        strat_data: dict[str, dict] = {}
        close_price = None
        for strat_name in strategies_cfg:
            if not strategies_cfg[strat_name].get("enabled", False):
                continue
            sig = signal_map.get((strat_name, sym))
            if sig:
                if close_price is None:
                    close_price = sig["close_price"]
                strat_data[strat_name] = {
                    "signal": sig["signal"],
                    "indicator_value": sig["indicator_value"],
                    "indicator_label": INDICATOR_LABELS.get(strat_name, strat_name),
                    "in_universe": asset_membership.get(sym, {}).get(strat_name, False),
                }
            elif strat_name in asset_membership.get(sym, {}):
                strat_data[strat_name] = {
                    "signal": None,
                    "indicator_value": None,
                    "indicator_label": INDICATOR_LABELS.get(strat_name, strat_name),
                    "in_universe": asset_membership[sym][strat_name],
                }

        pos_strategies = open_pos_map.get(sym, [])
        assets.append({
            "symbol": sym,
            "close": close_price,
            "strategies": strat_data,
            "has_open_position": len(pos_strategies) > 0,
            "position_strategies": pos_strategies,
        })

    return {
        "scanner_timestamp": ts,
        "assets": assets,
    }
