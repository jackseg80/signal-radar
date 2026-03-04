"""Journal entries and notes endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.dependencies import get_db
from api.routes.market import get_proxy_url
from data.db import SignalRadarDB

router = APIRouter()

class JournalUpdate(BaseModel):
    notes: str | None = None
    tags: str | None = None
    sentiment: str | None = None

@router.get("/entries")
def get_journal_entries(
    strategy: str | None = Query(None),
    symbol: str | None = Query(None),
    source: str | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Consolidated trade timeline with stats."""
    res = db.get_journal_entries(
        strategy=strategy,
        symbol=symbol,
        source=source,
        search=search,
        limit=limit,
    )
    
    # Secure access to entries
    entries = res.get("entries", [])
    for entry in entries:
        entry["logo_url"] = get_proxy_url(entry.get("symbol"))
            
    return res

@router.patch("/paper/{id}/update")
def update_paper_entry(
    id: int,
    update: JournalUpdate,
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Update paper trade details (notes, tags, sentiment)."""
    success = db.update_paper_entry(id, notes=update.notes, tags=update.tags, sentiment=update.sentiment)
    if not success:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"status": "updated"}

@router.patch("/live/{id}/update")
def update_live_entry(
    id: int,
    update: JournalUpdate,
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Update live trade details (notes, tags, sentiment)."""
    success = db.update_live_entry(id, notes=update.notes, tags=update.tags, sentiment=update.sentiment)
    if not success:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"status": "updated"}

# Backward compatibility routes
@router.patch("/paper/{id}/notes")
def update_paper_notes(id: int, notes: str = Query(...), db: SignalRadarDB = Depends(get_db)):
    return update_paper_entry(id, JournalUpdate(notes=notes), db)

@router.patch("/live/{id}/notes")
def update_live_notes(id: int, notes: str = Query(...), db: SignalRadarDB = Depends(get_db)):
    return update_live_entry(id, JournalUpdate(notes=notes), db)
