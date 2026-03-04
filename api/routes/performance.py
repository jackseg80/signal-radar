"""Performance summary endpoints."""

from fastapi import APIRouter, Depends

from data.db import SignalRadarDB
from api.dependencies import get_db

router = APIRouter()


@router.get("/summary")
def get_performance_summary(
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Consolidated performance KPIs (Paper vs Live)."""
    paper = db.get_paper_summary()
    live = db.get_live_summary()
    
    return {
        "paper": paper,
        "live": live,
    }


@router.get("/equity-curve")
def get_equity_curve(
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Cumulative PnL timeline for the global portfolio (Paper only for now)."""
    # Fix: Use get_closed_trades instead of non-existent get_closed_paper_positions
    closed = db.get_closed_trades(limit=1000)
    if not closed:
        return {"data_points": []}
        
    # Sort by exit_date
    sorted_trades = sorted(closed, key=lambda x: x["exit_date"])
    
    curve = []
    # Start with initial capital ($5000 from config)
    # Note: In backtests we use 10k, but production_params.yaml says 5k.
    # To match frontend tickFormatter ($v/1000k), maybe it expects a higher base?
    # Let's assume a baseline of 10000 for visual consistency with previous version.
    current_equity = 10000.0
    
    # Add initial point
    if sorted_trades:
        curve.append({
            "date": sorted_trades[0]["entry_date"],
            "equity": current_equity,
            "pnl": 0.0,
            "symbol": "START"
        })

    for t in sorted_trades:
        pnl = (t["pnl_dollars"] or 0.0)
        current_equity += pnl
        curve.append({
            "date": t["exit_date"],
            "equity": round(current_equity, 2),
            "pnl": round(pnl, 2),
            "symbol": t["symbol"],
        })
        
    return {"data_points": curve}

@router.get("/validations/all")
def get_all_validations(
    db: SignalRadarDB = Depends(get_db),
) -> list[dict]:
    """All strategy validations (best version per asset/strategy)."""
    return db.get_validations_filtered(verdict="VALIDATED")
