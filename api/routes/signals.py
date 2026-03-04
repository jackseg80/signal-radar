"""Signals endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.dependencies import get_db
from data.db import SignalRadarDB

router = APIRouter()


@router.get("/today")
def get_today_signals(
    strategy: str | None = Query(None),
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Latest entry/exit signals for all enabled strategies."""
    ts, all_signals = db.get_latest_signals(strategy=strategy)
    
    # Get all metadata
    metadata_map = db.get_all_metadata()

    # Group by strategy
    strategies: dict[str, dict] = {}
    for s in all_signals:
        strat = s["strategy"]
        if strat not in strategies:
            # Short label for UI
            label = strat.split("_")[0].upper()
            strategies[strat] = {"label": label, "signals": []}
        
        meta = metadata_map.get(s["symbol"], {})
        
        strategies[strat]["signals"].append({
            "symbol": s["symbol"],
            "name": meta.get("name") or s["symbol"],
            "logo_url": meta.get("logo_url"),
            "signal": s["signal"],
            "close_price": s["close_price"],
            "indicator_value": s["indicator_value"],
            "notes": s["notes"],
        })

    return {
        "scanner_timestamp": ts,
        "strategies": strategies,
    }


@router.get("/history")
def get_signal_history(
    days: int = Query(30, gt=0, le=365),
    strategy: str | None = Query(None),
    signal_type: str | None = Query(None),
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Historical signals for auditing and dashboard trends."""
    history = db.get_signal_history(
        strategy=strategy, signal_type=signal_type, days=days
    )
    
    # Get all metadata
    metadata_map = db.get_all_metadata()
    
    # Attach metadata to history
    for s in history:
        meta = metadata_map.get(s["symbol"], {})
        s["name"] = meta.get("name") or s["symbol"]
        s["logo_url"] = meta.get("logo_url")

    return {
        "total": len(history),
        "signals": history,
    }
