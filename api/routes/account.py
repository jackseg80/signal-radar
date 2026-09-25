"""Manual Saxo account confirmation, scoped to the completed US session."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.dependencies import get_db
from data.db import SignalRadarDB
from engine.trading_calendar import last_completed_session


router = APIRouter()


class AccountConfirmation(BaseModel):
    """Cash and all held ticker symbols entered by the account owner."""

    source_session: str
    cash_usd: float = Field(ge=0)
    holdings: list[str]
    note: str = ""


@router.get("/current")
def current_confirmation(db: SignalRadarDB = Depends(get_db)) -> dict:
    """Show the exact session requiring manual confirmation."""
    session = last_completed_session()
    return {
        "source_session": session,
        "confirmation": db.get_account_confirmation(session),
    }


@router.post("/confirm")
def confirm_account(
    payload: AccountConfirmation, db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Accept a deliberate confirmation for the current completed session."""
    expected = last_completed_session()
    if payload.source_session != expected:
        raise HTTPException(
            status_code=409,
            detail=f"Confirm the current completed session {expected}",
        )
    return db.confirm_account(
        expected, payload.cash_usd, payload.holdings, payload.note,
    )


class ManualCashSnapshot(BaseModel):
    """User-entered Saxo available cash; it is not computed from tracked trades."""

    available_usd: float = Field(ge=0)


@router.get("/manual-cash")
def latest_manual_cash(db: SignalRadarDB = Depends(get_db)) -> dict:
    """Return the latest dated manual cash snapshot."""
    return {"snapshot": db.get_manual_cash()}


@router.post("/manual-cash")
def save_manual_cash(
    payload: ManualCashSnapshot, db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Save cash without implying full Saxo portfolio reconciliation."""
    return db.record_manual_cash(payload.available_usd)
