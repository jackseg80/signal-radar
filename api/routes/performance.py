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
) -> list[dict]:
    """Cumulative PnL timeline for the global portfolio (Paper only for now)."""
    # We fetch paper results and build a cumulative curve
    closed = db.get_closed_paper_positions()
    if not closed:
        return []
        
    # Sort by exit_date
    sorted_trades = sorted(closed, key=lambda x: x["exit_date"])
    
    curve = []
    cumulative = 0.0
    for t in sorted_trades:
        cumulative += (t["pnl_dollars"] or 0.0)
        curve.append({
            "date": t["exit_date"],
            "pnl": round(cumulative, 2),
            "trade_pnl": t["pnl_dollars"],
            "symbol": t["symbol"],
        })
        
    return curve

@router.get("/validations/all")
def get_all_validations(
    db: SignalRadarDB = Depends(get_db),
) -> list[dict]:
    """All strategy validations (best version per asset/strategy)."""
    return db.get_validations_filtered(verdict="VALIDATED")
