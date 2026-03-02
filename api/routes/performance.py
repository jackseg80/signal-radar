"""Performance endpoints."""

from fastapi import APIRouter, Depends

from data.db import SignalRadarDB
from api.config import load_production_config
from api.dependencies import get_db

router = APIRouter()


@router.get("/summary")
def get_performance_summary(
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Paper trading performance summary."""
    summary = db.get_paper_summary()
    config = load_production_config()
    capital = config.get("capital", 5000)

    # Unrealized P&L from open positions (batch fetch)
    open_positions = db.get_open_positions()
    symbols = list({p["symbol"] for p in open_positions})
    prices = db.get_latest_prices(symbols) if symbols else {}
    total_unrealized = 0.0
    for p in open_positions:
        current_price = prices.get(p["symbol"])
        if current_price is not None and p["entry_price"] > 0:
            total_unrealized += (current_price - p["entry_price"]) * p["shares"]

    return {
        "capital": capital,
        "n_closed_trades": summary["n_trades"],
        "n_wins": summary["n_wins"],
        "win_rate": summary["win_rate"],
        "total_realized_pnl": summary["total_pnl"],
        "total_unrealized_pnl": round(total_unrealized, 2),
        "n_open_positions": summary["n_open"],
        "by_strategy": summary["by_strategy"],
    }


@router.get("/equity-curve")
def get_equity_curve(
    strategy: str | None = None,
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Cumulative P&L over time from closed trades."""
    trades = db.get_closed_trades(strategy=strategy, limit=10000)

    # Sort by exit_date ASC (get_closed_trades returns DESC)
    trades.sort(key=lambda t: t["exit_date"] or "")

    cumulative = 0.0
    data_points = []
    for t in trades:
        pnl = t["pnl_dollars"] or 0.0
        cumulative += pnl
        data_points.append({
            "date": t["exit_date"],
            "cumulative_pnl": round(cumulative, 2),
            "trade_pnl": pnl,
            "strategy": t["strategy"],
            "symbol": t["symbol"],
        })

    return {"data_points": data_points}
