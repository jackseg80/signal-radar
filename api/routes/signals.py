"""Signal endpoints."""

from fastapi import APIRouter, Depends

from data.db import SignalRadarDB
from api.dependencies import get_db

router = APIRouter()

STRATEGY_LABELS = {
    "rsi2": "RSI(2) Mean Reversion",
    "ibs": "IBS Mean Reversion",
    "tom": "Turn of the Month",
}


@router.get("/today")
def get_today_signals(
    strategy: str | None = None,
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Latest signals from the most recent scanner run."""
    ts, signals = db.get_latest_signals(strategy=strategy)
    if ts is None:
        return {"scanner_timestamp": None, "strategies": {}}

    grouped: dict[str, dict] = {}
    for s in signals:
        strat = s["strategy"]
        if strat not in grouped:
            grouped[strat] = {
                "label": STRATEGY_LABELS.get(strat, strat),
                "signals": [],
            }
        grouped[strat]["signals"].append({
            "symbol": s["symbol"],
            "signal": s["signal"],
            "close_price": s["close_price"],
            "indicator_value": s["indicator_value"],
            "notes": s["notes"],
        })

    return {"scanner_timestamp": ts, "strategies": grouped}


@router.get("/history")
def get_signal_history(
    strategy: str | None = None,
    symbol: str | None = None,
    signal_type: str | None = None,
    days: int = 7,
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Signal history for the last N days."""
    signals = db.get_signal_history(
        strategy=strategy,
        symbol=symbol,
        signal_type=signal_type,
        days=days,
    )
    return {
        "signals": [
            {
                "timestamp": s["timestamp"],
                "strategy": s["strategy"],
                "symbol": s["symbol"],
                "signal": s["signal"],
                "close_price": s["close_price"],
                "indicator_value": s["indicator_value"],
                "notes": s["notes"],
            }
            for s in signals
        ],
        "total": len(signals),
    }
