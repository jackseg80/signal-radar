"""Position endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from data.db import SignalRadarDB
from api.dependencies import get_db
from api.routes.market import get_proxy_url

router = APIRouter()


class DividendPayment(BaseModel):
    """Manually verified net Saxo dividend payment."""

    position_id: int
    ex_session: str
    pay_session: str
    net_amount_usd: float = Field(ge=0)


@router.get("/dividends/pending")
def pending_dividends(db: SignalRadarDB = Depends(get_db)) -> dict:
    """Show accrued entitlements that are excluded from available cash."""
    return {"entitlements": db.get_pending_dividends()}


@router.post("/dividends/confirm")
def confirm_dividend(
    payload: DividendPayment, db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Credit cash only after the payment appears on a Saxo statement."""
    try:
        recorded = db.confirm_paper_dividend(
            payload.position_id, payload.ex_session,
            payload.pay_session, payload.net_amount_usd,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not recorded:
        raise HTTPException(status_code=404, detail="Unpaid entitlement not found")
    return {"status": "confirmed"}


@router.get("/open")
def get_open_positions(
    strategy: str | None = None,
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Open paper positions with unrealized P&L."""
    positions = db.get_v2_open_positions()
    if strategy:
        positions = [p for p in positions if p["strategy"] == strategy]

    # Batch fetch prices
    symbols = list({p["symbol"] for p in positions})
    prices = {}
    for symbol in symbols:
        recent = db.get_prices_v2(symbol)
        if not recent.empty:
            prices[symbol] = float(recent["Close"].iloc[-1])

    enriched = []
    total_unrealized = 0.0
    for p in positions:
        current_price = prices.get(p["symbol"])
        unrealized_pnl = 0.0
        unrealized_pct = 0.0
        if current_price is not None and p["entry_price"] > 0:
            unrealized_pnl = round((current_price - p["entry_price"]) * p["shares"], 2)
            unrealized_pct = round((current_price - p["entry_price"]) / p["entry_price"] * 100, 2)
        
        total_unrealized += unrealized_pnl
        enriched.append({
            "id": p["id"],
            "strategy": p["strategy"],
            "symbol": p["symbol"],
            "logo_url": get_proxy_url(p["symbol"]), # Added logo support
            "entry_date": p["entry_session"],
            "entry_price": p["entry_price"],
            "shares": p["shares"],
            "current_price": current_price,
            "unrealized_pnl": unrealized_pnl,
            "unrealized_pct": unrealized_pct,
        })

    return {
        "series": "next_open_v2",
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
    trades = db.get_v2_closed_trades(limit=limit)
    if strategy:
        trades = [t for t in trades if t["strategy"] == strategy]
    if symbol:
        trades = [t for t in trades if t["symbol"] == symbol]
    return {
        "trades": [
            {
                "id": t["id"],
                "strategy": t["strategy"],
                "symbol": t["symbol"],
                "logo_url": get_proxy_url(t["symbol"]), # Added logo support
                "entry_date": t["entry_session"],
                "entry_price": t["entry_price"],
                "exit_date": t["exit_session"],
                "exit_price": t["exit_price"],
                "shares": t["shares"],
                "pnl_dollars": t["pnl_dollars"],
                "pnl_pct": round(100 * t["pnl_dollars"] / t["cost_basis"], 2),
            }
            for t in trades
        ],
        "total": len(trades),
        "series": "next_open_v2",
    }


@router.get("/follow")
def get_signal_follow_positions(db: SignalRadarDB = Depends(get_db)) -> dict:
    """Independent per-signal virtual follow-up, with no shared cash account."""
    from engine.fee_model import load_saxo_ch_costs

    fee_model, costs_verified = load_saxo_ch_costs()
    positions = []
    for pos in db.get_follow_positions():
        prices = db.get_prices_v2(pos["symbol"])
        current_price = float(prices["Close"].iloc[-1]) if not prices.empty else None
        price_session = str(prices.index[-1].date()) if not prices.empty else None
        unrealized = None
        if current_price is not None:
            proceeds = current_price * pos["shares"]
            unrealized = round(
                proceeds - fee_model.total_exit_cost(proceeds)
                + pos["dividend_cash"] - pos["cost_basis"] - pos["entry_fee"], 2,
            )
        positions.append({
            "id": pos["id"], "symbol": pos["symbol"],
            "strategy": pos["strategy"], "source_session": pos["source_session"],
            "entry_session": pos["entry_session"], "entry_price": pos["entry_price"],
            "shares": pos["shares"], "current_price": current_price,
            "price_session": price_session, "unrealized_pnl_estimate": unrealized,
            "dividend_cash_estimate": pos["dividend_cash"],
        })
    closed = db.get_follow_positions("closed")
    return {
        "series": "independent_signal_follow",
        "notional_per_signal_usd": 5000.0,
        "costs_verified": costs_verified,
        "positions": positions,
        "pending_orders": db.get_follow_orders(),
        "closed_count": len(closed),
        "closed_pnl_sum_provisional": round(sum(
            p["pnl_dollars"] or 0 for p in closed
        ), 2),
    }


@router.get("/legacy")
def get_legacy_positions(db: SignalRadarDB = Depends(get_db)) -> dict:
    """Read-only archive of the old close-filled paper series."""
    return {
        "series": "ancien modèle", "read_only": True,
        "open": db.get_open_positions(),
        "closed": db.get_closed_trades(limit=1000),
    }
