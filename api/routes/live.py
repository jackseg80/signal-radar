"""Live trades endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import get_db
from data.db import SignalRadarDB

router = APIRouter()


@router.post("/open")
def open_live_trade(
    strategy: str,
    symbol: str,
    entry_date: str,
    entry_price: float = Query(..., gt=0),
    shares: float = Query(..., gt=0),
    fees: float = Query(0, ge=0),
    notes: str = "",
    paper_position_id: int | None = None,
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Log a real trade entry."""
    created = db.open_live_trade(
        strategy, symbol, entry_date, entry_price, shares,
        fees=fees, notes=notes, paper_position_id=paper_position_id,
    )
    if not created:
        raise HTTPException(
            status_code=409,
            detail=f"Live trade already exists: {strategy}/{symbol}/{entry_date}",
        )
    return {"status": "created", "strategy": strategy, "symbol": symbol}


@router.post("/close")
def close_live_trade(
    strategy: str,
    symbol: str,
    exit_date: str,
    exit_price: float = Query(..., gt=0),
    fees: float = Query(0, ge=0),
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Log a real trade exit."""
    trade = db.close_live_trade(strategy, symbol, exit_date, exit_price, fees=fees)
    if trade is None:
        raise HTTPException(
            status_code=404,
            detail=f"No open live trade: {strategy}/{symbol}",
        )
    return {"status": "closed", "trade": trade}


@router.delete("/{trade_id}")
def delete_live_trade(
    trade_id: int,
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Delete a live trade by ID."""
    if not db.delete_live_trade(trade_id):
        raise HTTPException(status_code=404, detail="Trade not found")
    return {"deleted": True, "id": trade_id}


@router.get("/open")
def get_open_live_trades(
    strategy: str | None = None,
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Open live trades with current prices."""
    trades = db.get_open_live_trades(strategy=strategy)

    symbols = list({t["symbol"] for t in trades})
    prices = db.get_latest_prices(symbols) if symbols else {}

    for t in trades:
        current = prices.get(t["symbol"])
        t["current_price"] = current
        if current and t["entry_price"]:
            t["unrealized_pnl"] = round(
                (current - t["entry_price"]) * t["shares"] - (t["fees_entry"] or 0), 2
            )
            t["unrealized_pct"] = round(
                (current - t["entry_price"]) / t["entry_price"] * 100, 2
            )
        else:
            t["unrealized_pnl"] = None
            t["unrealized_pct"] = None

    return {"trades": trades}


@router.get("/closed")
def get_closed_live_trades(
    strategy: str | None = None,
    symbol: str | None = None,
    limit: int = Query(50, ge=1, le=1000),
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Closed live trades."""
    trades = db.get_closed_live_trades(strategy=strategy, symbol=symbol, limit=limit)
    return {"trades": trades, "total": len(trades)}


@router.get("/summary")
def get_live_summary(
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Live trading performance summary."""
    return db.get_live_summary()


@router.get("/compare")
def compare_paper_vs_live(
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Compare paper vs live performance side by side."""
    paper = db.get_paper_summary()
    live = db.get_live_summary()

    result = {
        "paper": {
            "n_trades": paper["n_trades"],
            "win_rate": paper["win_rate"],
            "total_pnl": paper["total_pnl"],
            "avg_pnl_per_trade": (
                round(paper["total_pnl"] / paper["n_trades"], 2)
                if paper["n_trades"] > 0 else 0.0
            ),
        },
        "live": {
            "n_trades": live["n_trades"],
            "win_rate": live["win_rate"],
            "total_pnl": live["total_pnl"],
            "avg_pnl_per_trade": (
                round(live["total_pnl"] / live["n_trades"], 2)
                if live["n_trades"] > 0 else 0.0
            ),
        },
    }

    return result
