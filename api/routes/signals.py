"""Signals endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.dependencies import get_db
from api.routes.market import get_proxy_url
from data.db import SignalRadarDB

router = APIRouter()


@router.get("/today")
def get_today_signals(
    strategy: str | None = Query(None),
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Latest entry/exit signals for all enabled strategies."""
    ts, all_signals = db.get_latest_signals(strategy=strategy)
    
    # Group by strategy
    strategies: dict[str, dict] = {}
    for s in all_signals:
        strat = s["strategy"]
        if strat not in strategies:
            # Short label for UI
            label = strat.split("_")[0].upper()
            strategies[strat] = {"label": label, "signals": []}
        
        sym = s["symbol"]
        
        strategies[strat]["signals"].append({
            "symbol": sym,
            "logo_url": get_proxy_url(sym),
            "signal": s["signal"],
            "close_price": s["close_price"],
            "indicator_value": s["indicator_value"],
            "notes": s["notes"],
            "source_session": s.get("source_session"),
            "target_session": s.get("target_session"),
            "technical_signal": s.get("technical_signal"),
            "eligibility": s.get("eligibility"),
            "reasons": s.get("reasons", []),
            "expires_at": s.get("expires_at"),
            "max_budget_usd": s.get("max_budget_usd"),
            "indicative_shares": s.get("indicative_shares"),
            "score": s.get("score"),
            "paper_signal": s.get("paper_signal"),
            "paper_status": s.get("paper_status"),
            "follow_signal": s.get("follow_signal"),
            "follow_status": s.get("follow_status"),
            "paper_reasons": s.get("paper_reasons", []),
            "paper_warnings": s.get("paper_warnings", []),
            "paper_budget_usd": s.get("paper_budget_usd"),
            "paper_indicative_shares": s.get("paper_indicative_shares"),
        })

    return {
        "scanner_timestamp": ts,
        "source_session": all_signals[0].get("source_session") if all_signals else None,
        "target_session": all_signals[0].get("target_session") if all_signals else None,
        "paper_universe_complete": not any(
            signal.get("eligibility") == "DATA_MISSING" for signal in all_signals
        ),
        "paper_excluded_symbols": sorted({
            signal["symbol"] for signal in all_signals
            if signal.get("eligibility") == "DATA_MISSING"
        }),
        "verified_price_repairs": db.get_price_repairs(),
        "strategies": strategies,
    }


@router.get("/candidates")
def get_candidates(db: SignalRadarDB = Depends(get_db)) -> dict:
    """Group simultaneous strategy triggers into one candidate per title."""
    source, signals = db.get_latest_signals()
    groups: dict[str, dict] = {}
    for row in signals:
        if row.get("technical_signal") != "BUY":
            continue
        symbol = row["symbol"]
        item = groups.setdefault(symbol, {
            "symbol": symbol, "strategies": [], "signal": "SKIP",
            "eligibility": "BLOCKED", "reasons": [], "source_session": source,
            "target_session": row.get("target_session"),
            "max_budget_usd": None, "indicative_shares": None,
        })
        item["strategies"].append(row["strategy"])
        if row["signal"] == "BUY":
            item.update({
                "signal": "BUY", "eligibility": "ELIGIBLE",
                "max_budget_usd": row.get("max_budget_usd"),
                "indicative_shares": row.get("indicative_shares"),
                "reasons": [],
            })
        elif item["signal"] != "BUY":
            item["reasons"].extend(row.get("reasons", []))
    return {"source_session": source, "candidates": list(groups.values())}


@router.get("/history")
def get_signal_history(
    days: int = Query(30, gt=0, le=365),
    strategy: str | None = Query(None),
    signal_type: str | None = Query(None),
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Historical signals for auditing and dashboard trends."""
    history = db.get_signal_history(
        strategy=strategy, signal_type=signal_type, days=days
    )
    
    # Attach local proxy URLs
    for s in history:
        s["logo_url"] = get_proxy_url(s["symbol"])

    return {
        "total": len(history),
        "signals": history,
    }
