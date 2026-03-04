"""Signals endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.dependencies import get_db
from api.routes.market import get_proxy_url
from data.db import SignalRadarDB

router = APIRouter()


@router.get("/today")
def get_today_signals(
    strategy: str | None = Query(None),
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Latest entry/exit signals for all enabled strategies."""
    ts, all_signals = db.get_latest_signals(strategy=strategy)
    
    # Group by strategy
    strategies: dict[str, dict] = {}
    for s in all_signals:
        strat = s["strategy"]
        if strat not in strategies:
            # Short label for UI
            label = strat.split("_")[0].upper()
            strategies[strat] = {"label": label, "signals": []}
        
        sym = s["symbol"]
        
        strategies[strat]["signals"].append({
            "symbol": sym,
            "logo_url": get_proxy_url(sym),
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
    
    # Attach local proxy URLs
    for s in history:
        s["logo_url"] = get_proxy_url(s["symbol"])

    return {
        "total": len(history),
        "signals": history,
    }
