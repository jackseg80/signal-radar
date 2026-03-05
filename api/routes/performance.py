"""Performance summary endpoints."""

from fastapi import APIRouter, Depends

from data.db import SignalRadarDB
from api.dependencies import get_db
from api.config import load_production_config

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
    # Dynamic capital from production_params.yaml
    config = load_production_config()
    initial_capital = config.get("capital", 5000.0)
    current_equity = initial_capital
    
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
