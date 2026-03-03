"""Trade journal endpoints -- unified paper + live trades timeline."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import get_db
from data.db import SignalRadarDB

router = APIRouter()


@router.get("/entries")
def get_journal_entries(
    strategy: str | None = None,
    symbol: str | None = None,
    source: str | None = None,
    search: str | None = None,
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Unified timeline of paper + live trades with signal context."""
    return db.get_journal_entries(
        strategy=strategy,
        symbol=symbol,
        source=source,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.patch("/paper/{position_id}/notes")
def update_paper_notes(
    position_id: int,
    notes: str = Query(""),
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Update notes on a paper position."""
    if not db.update_paper_notes(position_id, notes):
        raise HTTPException(status_code=404, detail="Paper position not found")
    return {"status": "updated", "id": position_id}


@router.patch("/live/{trade_id}/notes")
def update_live_notes(
    trade_id: int,
    notes: str = Query(""),
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Update notes on a live trade."""
    if not db.update_live_notes(trade_id, notes):
        raise HTTPException(status_code=404, detail="Live trade not found")
    return {"status": "updated", "id": trade_id}
