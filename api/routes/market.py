"""Market overview endpoint with proximity-to-trigger alerts."""

import json as _json
import httpx
from fastapi import APIRouter, Depends, Query, HTTPException, Response
from fastapi.responses import StreamingResponse

from data.db import SignalRadarDB
from api.config import load_production_config
from api.dependencies import get_db

router = APIRouter()

INDICATOR_LABELS = {
    "rsi2": "RSI(2)",
    "ibs": "IBS",
    "tom": "Days left",
}

# Signals where proximity is relevant (no open position, not already triggered)
_PROXIMITY_SIGNALS = {"NO_SIGNAL", "WATCH"}


def _compute_proximity(
    strategy: str,
    details: dict,
    params: dict,
) -> dict | None:
    """Compute proximity-to-trigger for a non-position asset."""
    if not details:
        return None

    if strategy == "rsi2":
        rsi = details.get("rsi2")
        trend_ok = details.get("trend_ok")
        if rsi is None:
            return None
        threshold = params.get("rsi_entry_threshold", 10.0)
        near_zone = threshold * 2  # RSI < 20 = near zone

        if rsi >= near_zone:
            pct = 0.0
        elif rsi <= threshold:
            pct = 100.0
        else:
            pct = (near_zone - rsi) / (near_zone - threshold) * 100

        near = rsi < near_zone
        if trend_ok is not None and not trend_ok:
            near = False  # trend blocked = not actionable
        return {
            "near": near and rsi > threshold,
            "pct": round(pct, 1),
            "trend_ok": trend_ok,
            "label": f"RSI={rsi:.1f} / {threshold:.0f}",
        }

    elif strategy == "ibs":
        ibs = details.get("ibs")
        trend_ok = details.get("trend_ok")
        if ibs is None:
            return None
        threshold = params.get("ibs_entry_threshold", 0.2)
        near_zone = threshold * 2  # IBS < 0.4 = near zone

        if ibs >= near_zone:
            pct = 0.0
        elif ibs <= threshold:
            pct = 100.0
        else:
            pct = (near_zone - ibs) / (near_zone - threshold) * 100

        near = ibs < near_zone
        if trend_ok is not None and not trend_ok:
            near = False
        return {
            "near": near and ibs > threshold,
            "pct": round(pct, 1),
            "trend_ok": trend_ok,
            "label": f"IBS={ibs:.3f} / {threshold}",
        }

    elif strategy == "tom":
        days_left = details.get("trading_days_left")
        if days_left is None:
            return None
        entry_window = details.get(
            "entry_days_before_eom",
            params.get("entry_days_before_eom", 5),
        )
        near_zone = entry_window + 3  # e.g. 8 days = approaching window

        if days_left > near_zone:
            pct = 0.0
        elif days_left <= entry_window:
            pct = 100.0
        else:
            pct = (near_zone - days_left) / (near_zone - entry_window) * 100

        near = days_left <= near_zone and days_left > entry_window
        return {
            "near": near,
            "pct": round(pct, 1),
            "trend_ok": True,  # TOM has no trend filter
            "label": f"{days_left}d left / {entry_window}d window",
        }

    return None


@router.get("/overview")
def get_market_overview(
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Market overview: latest indicators for all tracked assets."""
    config = load_production_config()
    strategies_cfg = config.get("strategies", {})
    
    metadata_map = db.get_all_metadata()

    asset_membership: dict[str, dict[str, bool]] = {}
    for strat_name, strat_cfg in strategies_cfg.items():
        if not strat_cfg.get("enabled", False):
            continue
        for sym in strat_cfg.get("universe", []):
            asset_membership.setdefault(sym, {})[strat_name] = True
        for sym in strat_cfg.get("watchlist", []):
            asset_membership.setdefault(sym, {})[strat_name] = False

    ts, all_signals = db.get_latest_signals()

    signal_map: dict[tuple[str, str], dict] = {}
    for s in all_signals:
        signal_map[(s["strategy"], s["symbol"])] = s

    details_map: dict[tuple[str, str], dict] = {}
    for s in all_signals:
        dj = s.get("details_json")
        if dj:
            try:
                details_map[(s["strategy"], s["symbol"])] = _json.loads(dj)
            except (ValueError, TypeError):
                pass

    open_positions = db.get_open_positions()
    open_pos_map: dict[str, list[str]] = {}
    for p in open_positions:
        open_pos_map.setdefault(p["symbol"], []).append(p["strategy"])

    assets = []
    for sym in sorted(asset_membership.keys()):
        strat_data: dict[str, dict] = {}
        close_price = None
        for strat_name in strategies_cfg:
            if not strategies_cfg[strat_name].get("enabled", False):
                continue
            sig = signal_map.get((strat_name, sym))
            if sig:
                if close_price is None:
                    close_price = sig["close_price"]

                prox = None
                if sig["signal"] in _PROXIMITY_SIGNALS:
                    details = details_map.get((strat_name, sym))
                    strat_params = strategies_cfg.get(strat_name, {}).get("params", {})
                    prox = _compute_proximity(strat_name, details, strat_params)

                strat_data[strat_name] = {
                    "signal": sig["signal"],
                    "indicator_value": sig["indicator_value"],
                    "indicator_label": INDICATOR_LABELS.get(strat_name, strat_name),
                    "in_universe": asset_membership.get(sym, {}).get(strat_name, False),
                    "proximity": prox,
                }
            elif strat_name in asset_membership.get(sym, {}):
                strat_data[strat_name] = {
                    "signal": None,
                    "indicator_value": None,
                    "indicator_label": INDICATOR_LABELS.get(strat_name, strat_name),
                    "in_universe": asset_membership[sym][strat_name],
                    "proximity": None,
                }

        pos_strategies = open_pos_map.get(sym, [])
        
        # Get metadata, fetch if missing
        meta = metadata_map.get(sym)
        if not meta:
            meta = db.get_asset_metadata(sym) or {}
        
        assets.append({
            "symbol": sym,
            "name": meta.get("name") or sym,
            "logo_url": meta.get("logo_url"),
            "close": close_price,
            "strategies": strat_data,
            "has_open_position": len(pos_strategies) > 0,
            "position_strategies": pos_strategies,
        })

    return {
        "scanner_timestamp": ts,
        "assets": assets,
    }


@router.get("/asset/{symbol}")
def get_asset_details(
    symbol: str,
    db: SignalRadarDB = Depends(get_db),
) -> dict:
    """Detailed info for a specific asset across all strategies."""
    config = load_production_config()
    strategies_cfg = config.get("strategies", {})
    
    meta = db.get_asset_metadata(symbol) or {}
    
    ts, all_signals = db.get_latest_signals()
    asset_signals = [s for s in all_signals if s["symbol"] == symbol]
    
    last_price = db.get_latest_price(symbol)
    if last_price is None:
        df = db.get_ohlcv(symbol)
        if df.empty:
             raise HTTPException(status_code=404, detail=f"Asset {symbol} not found")
        last_price = float(df.iloc[-1]["close"])

    membership = []
    for s_name, s_cfg in strategies_cfg.items():
        if symbol in s_cfg.get("universe", []):
            membership.append({"strategy": s_name, "type": "universe"})
        elif symbol in s_cfg.get("watchlist", []):
            membership.append({"strategy": s_name, "type": "watchlist"})

    open_pos = [p for p in db.get_open_positions() if p["symbol"] == symbol]
    validations = db.get_validations_filtered(verdict="VALIDATED")
    asset_validations = [v for v in validations if v["symbol"] == symbol]

    return {
        "symbol": symbol,
        "name": meta.get("name") or symbol,
        "logo_url": meta.get("logo_url"),
        "last_price": last_price,
        "timestamp": ts,
        "signals": asset_signals,
        "membership": membership,
        "open_positions": open_pos,
        "validations": asset_validations
    }


@router.get("/asset/{symbol}/logo")
async def get_asset_logo_proxy(
    symbol: str,
    db: SignalRadarDB = Depends(get_db),
):
    """Proxy for asset logo to bypass adblockers."""
    meta = db.get_asset_metadata(symbol)
    if not meta or not meta.get("logo_url"):
        raise HTTPException(status_code=404, detail="Logo URL not found")
    
    url = meta["logo_url"]
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=5.0, follow_redirects=True)
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code)
            
            return Response(content=resp.content, media_type=resp.headers.get("Content-Type", "image/png"))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch logo: {str(e)}")


@router.get("/asset/{symbol}/history")
def get_asset_history(
    symbol: str,
    days: int = Query(60, gt=0, le=365),
    db: SignalRadarDB = Depends(get_db),
) -> list:
    """Historical signals for a specific asset."""
    history = db.get_signal_history(symbol=symbol, days=days)
    return history


@router.get("/asset/{symbol}/prices")
def get_asset_prices(
    symbol: str,
    days: int = Query(60, gt=0, le=365),
    db: SignalRadarDB = Depends(get_db),
) -> list:
    """Historical prices (OHLCV) for a specific asset."""
    import pandas as pd
    start_date = (pd.Timestamp.now() - pd.Timedelta(days=days)).strftime("%Y-%m-%d")
    df = db.get_ohlcv(symbol, start=start_date)
    
    prices = []
    for date, row in df.iterrows():
        prices.append({
            "date": date.strftime("%Y-%m-%d") if isinstance(date, pd.Timestamp) else str(date),
            "close": float(row["close"])
        })
    return prices
