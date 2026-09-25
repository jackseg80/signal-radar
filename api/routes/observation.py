"""Manual Saxo comparison for a fixed twenty-session observation period."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.dependencies import get_db
from data.db import SignalRadarDB
from engine.trading_calendar import last_completed_session, next_session


router = APIRouter()


class BrokerCheck(BaseModel):
    """Saxo opening reference and optional executed order details."""

    source_session: str
    symbol: str
    saxo_open: float = Field(gt=0)
    execution_price: float | None = Field(default=None, gt=0)
    actual_fees_usd: float | None = Field(default=None, ge=0)
    notes: str = ""


@router.post("/start")
def start_observation(db: SignalRadarDB = Depends(get_db)) -> dict:
    """Start observation at the next US close to avoid retroactive sessions."""
    return db.start_observation(next_session(last_completed_session()))


@router.get("/status")
def observation_status(db: SignalRadarDB = Depends(get_db)) -> dict:
    """Progress, missing checks and simulated-versus-Saxo opening gaps."""
    return db.get_observation_status(last_completed_session())


@router.post("/check")
def save_broker_check(
    payload: BrokerCheck, db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Record manually observed Saxo data for a detected candidate."""
    if not db.log_observation_check(
        payload.source_session, payload.symbol, payload.saxo_open,
        payload.execution_price, payload.actual_fees_usd, payload.notes,
    ):
        raise HTTPException(status_code=404, detail="Candidate or observation period not found")
    return {"status": "recorded"}
