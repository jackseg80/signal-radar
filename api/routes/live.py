"""Live trades endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from api.config import load_production_config
from api.dependencies import get_db
from data.db import SignalRadarDB

router = APIRouter()


@router.post("/open")
def open_live_trade(
    strategy: str,
    symbol: str,
    entry_date: date,
    entry_price: float = Query(..., gt=0),
    shares: float = Query(..., gt=0),
    fees: float | None = Query(None, ge=0),
    notes: str = "",
    paper_position_id: int | None = None,
    instrument_type: str | None = Query(None, pattern="^(stock|cfd)$"),
    signal_session: date | None = None,
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Log a real trade entry."""
    symbol = symbol.strip().upper()
    if signal_session is not None and signal_session > entry_date:
        raise HTTPException(status_code=422, detail="Signal date follows purchase")
    if strategy not in {"rsi2", "ibs", "tom"}:
        raise HTTPException(status_code=422, detail="Unknown strategy")
    if instrument_type is not None:
        configured = load_production_config().get("strategies", {})
        allowed = {stock for settings in configured.values()
                   for stock in settings.get("universe", []) + settings.get("watchlist", [])}
        historical = db._query_one(
            "SELECT 1 FROM signal_decisions WHERE symbol=? LIMIT 1", (symbol,),
        )
        if symbol not in allowed and not historical:
            raise HTTPException(status_code=422, detail="Action outside Signal Radar")
    created = db.open_live_trade(
        strategy, symbol, entry_date.isoformat(), entry_price, shares,
        fees=fees or 0, notes=notes, paper_position_id=paper_position_id,
        instrument_type=instrument_type,
        signal_session=signal_session.isoformat() if signal_session else None,
        entry_fee_known=fees is not None,
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




@router.post("/close/{trade_id}")
def close_live_trade_by_id(
    trade_id: int,
    exit_date: date,
    exit_price: float = Query(..., gt=0),
    fees: float | None = Query(None, ge=0),
    financing_cost: float | None = Query(None, ge=0),
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Close one selected real trade; missing cost fields leave net P&L provisional."""
    trade = db._query_one("SELECT * FROM live_trades WHERE id=?", (trade_id,))
    if trade is None or trade["status"] != "open":
        raise HTTPException(status_code=404, detail="Open trade not found")
    if trade["instrument_type"] == "stock" and financing_cost not in (None, 0):
        raise HTTPException(status_code=422, detail="Stock trade has no CFD financing")
    if exit_date.isoformat() < trade["entry_date"]:
        raise HTTPException(status_code=422, detail="Exit precedes entry")
    result = db.close_live_trade_by_id(
        trade_id, exit_date.isoformat(), exit_price, fees or 0,
        financing_cost or 0, exit_fee_known=fees is not None,
        financing_known=financing_cost is not None,
    )
    return {"status": "closed", "trade": result}


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
        t["other_buy_strategies"] = db.get_other_buy_strategies(
            t["symbol"], t.get("signal_session"), t["strategy"],
        )
        current = prices.get(t["symbol"])
        t["current_price"] = current
        if current is not None and t["entry_price"]:
            t["unrealized_pnl"] = round(
                (current - t["entry_price"]) * t["shares"] - (t["fees_entry"] or 0), 2
            )
            t["unrealized_pnl_provisional"] = True
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
    for trade in trades:
        trade["other_buy_strategies"] = db.get_other_buy_strategies(
            trade["symbol"], trade.get("signal_session"), trade["strategy"],
        )
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
    paper = db.get_v2_paper_summary()
    live = db.get_live_summary()

    result = {
        "paper_series": "next_open_v2",
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
