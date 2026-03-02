"""Position endpoints."""

from fastapi import APIRouter, Depends, Query

from data.db import SignalRadarDB
from api.dependencies import get_db

router = APIRouter()


@router.get("/open")
def get_open_positions(
    strategy: str | None = None,
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Open paper positions with unrealized P&L."""
    positions = db.get_open_positions(strategy=strategy)

    # Batch fetch prices (avoids N+1 queries)
    symbols = list({p["symbol"] for p in positions})
    prices = db.get_latest_prices(symbols) if symbols else {}

    enriched = []
    total_unrealized = 0.0
    for p in positions:
        current_price = prices.get(p["symbol"])
        unrealized_pnl = 0.0
        unrealized_pct = 0.0
        if current_price is not None and p["entry_price"] > 0:
            unrealized_pnl = round(
                (current_price - p["entry_price"]) * p["shares"], 2
            )
            unrealized_pct = round(
                (current_price - p["entry_price"]) / p["entry_price"] * 100, 2
            )
        total_unrealized += unrealized_pnl
        enriched.append({
            "id": p["id"],
            "strategy": p["strategy"],
            "symbol": p["symbol"],
            "entry_date": p["entry_date"],
            "entry_price": p["entry_price"],
            "shares": p["shares"],
            "current_price": current_price,
            "unrealized_pnl": unrealized_pnl,
            "unrealized_pct": unrealized_pct,
        })

    return {
        "positions": enriched,
        "total_unrealized_pnl": round(total_unrealized, 2),
    }


@router.get("/closed")
def get_closed_positions(
    strategy: str | None = None,
    symbol: str | None = None,
    limit: int = Query(50, ge=1, le=1000),
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Closed paper trades."""
    trades = db.get_closed_trades(strategy=strategy, symbol=symbol, limit=limit)
    return {
        "trades": [
            {
                "id": t["id"],
                "strategy": t["strategy"],
                "symbol": t["symbol"],
                "entry_date": t["entry_date"],
                "entry_price": t["entry_price"],
                "exit_date": t["exit_date"],
                "exit_price": t["exit_price"],
                "shares": t["shares"],
                "pnl_dollars": t["pnl_dollars"],
                "pnl_pct": t["pnl_pct"],
            }
            for t in trades
        ],
        "total": len(trades),
    }
