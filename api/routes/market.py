"""Market overview endpoint with proximity-to-trigger alerts."""

import json as _json
import httpx
from fastapi import APIRouter, Depends, Query, HTTPException, Response
from loguru import logger

from data.db import SignalRadarDB
from api.config import load_production_config
from api.dependencies import get_db

router = APIRouter()

INDICATOR_LABELS = {
    "rsi2": "RSI(2)",
    "ibs": "IBS",
    "tom": "Days left",
}

_PROXIMITY_SIGNALS = {"NO_SIGNAL", "WATCH"}

def _compute_proximity(strategy: str, details: dict, params: dict) -> dict | None:
    if not details: return None
    if strategy == "rsi2":
        rsi = details.get("rsi2")
        trend_ok = details.get("trend_ok")
        if rsi is None: return None
        threshold = params.get("rsi_entry_threshold", 10.0)
        near_zone = threshold * 2
        pct = 100.0 if rsi <= threshold else (0.0 if rsi >= near_zone else (near_zone - rsi) / (near_zone - threshold) * 100)
        near = rsi < near_zone
        if trend_ok is not None and not trend_ok: near = False
        return {"near": near and rsi > threshold, "pct": round(pct, 1), "trend_ok": trend_ok, "label": f"RSI={rsi:.1f} / {threshold:.0f}"}
    elif strategy == "ibs":
        ibs = details.get("ibs")
        trend_ok = details.get("trend_ok")
        if ibs is None: return None
        threshold = params.get("ibs_entry_threshold", 0.2)
        near_zone = threshold * 2
        pct = 100.0 if ibs <= threshold else (0.0 if ibs >= near_zone else (near_zone - ibs) / (near_zone - threshold) * 100)
        near = ibs < near_zone
        if trend_ok is not None and not trend_ok: near = False
        return {"near": near and ibs > threshold, "pct": round(pct, 1), "trend_ok": trend_ok, "label": f"IBS={ibs:.3f} / {threshold}"}
    elif strategy == "tom":
        days_left = details.get("trading_days_left")
        if days_left is None: return None
        entry_window = details.get("entry_days_before_eom", params.get("entry_days_before_eom", 5))
        near_zone = entry_window + 3
        pct = 100.0 if days_left <= entry_window else (0.0 if days_left > near_zone else (near_zone - days_left) / (near_zone - entry_window) * 100)
        return {"near": days_left <= near_zone and days_left > entry_window, "pct": round(pct, 1), "trend_ok": True, "label": f"{days_left}d left / {entry_window}d window"}
    return None

@router.get("/overview")
def get_market_overview(db: SignalRadarDB = Depends(get_db)) -> dict:
    config = load_production_config(); strategies_cfg = config.get("strategies", {})
    metadata_map = db.get_all_metadata()
    asset_membership = {}
    for strat_name, strat_cfg in strategies_cfg.items():
        if not strat_cfg.get("enabled", False): continue
        for sym in strat_cfg.get("universe", []): asset_membership.setdefault(sym, {})[strat_name] = True
        for sym in strat_cfg.get("watchlist", []): asset_membership.setdefault(sym, {})[strat_name] = False
    ts, all_signals = db.get_latest_signals()
    signal_map = {(s["strategy"], s["symbol"]): s for s in all_signals}
    details_map = {}
    for s in all_signals:
        dj = s.get("details_json")
        if dj:
            try: details_map[(s["strategy"], s["symbol"])] = _json.loads(dj)
            except: pass
    open_pos_map = {}
    for p in db.get_open_positions(): open_pos_map.setdefault(p["symbol"], []).append(p["strategy"])
    assets = []
    for sym in sorted(asset_membership.keys()):
        strat_data = {}
        close_price = None
        for strat_name in strategies_cfg:
            if not strategies_cfg[strat_name].get("enabled", False): continue
            sig = signal_map.get((strat_name, sym))
            if sig:
                if close_price is None: close_price = sig["close_price"]
                prox = None
                if sig["signal"] in _PROXIMITY_SIGNALS:
                    prox = _compute_proximity(strat_name, details_map.get((strat_name, sym)), strategies_cfg.get(strat_name, {}).get("params", {}))
                strat_data[strat_name] = {"signal": sig["signal"], "indicator_value": sig["indicator_value"], "indicator_label": INDICATOR_LABELS.get(strat_name, strat_name), "in_universe": asset_membership.get(sym, {}).get(strat_name, False), "proximity": prox}
            elif strat_name in asset_membership.get(sym, {}):
                strat_data[strat_name] = {"signal": None, "indicator_value": None, "indicator_label": INDICATOR_LABELS.get(strat_name, strat_name), "in_universe": asset_membership[sym][strat_name], "proximity": None}
        pos_strategies = open_pos_map.get(sym, [])
        meta = metadata_map.get(sym)
        if not meta: meta = db.get_asset_metadata(sym) or {}
        assets.append({"symbol": sym, "name": meta.get("name") or sym, "logo_url": meta.get("logo_url"), "close": close_price, "strategies": strat_data, "has_open_position": len(pos_strategies) > 0, "position_strategies": pos_strategies})
    return {"scanner_timestamp": ts, "assets": assets}

@router.get("/asset/{symbol}")
def get_asset_details(symbol: str, db: SignalRadarDB = Depends(get_db)) -> dict:
    meta = db.get_asset_metadata(symbol) or {}
    ts, all_signals = db.get_latest_signals(); asset_signals = [s for s in all_signals if s["symbol"] == symbol]
    last_price = db.get_latest_price(symbol)
    if last_price is None:
        df = db.get_ohlcv(symbol)
        if df.empty: raise HTTPException(status_code=404, detail=f"Asset {symbol} not found")
        last_price = float(df.iloc[-1]["close"])
    membership = []
    for s_name, s_cfg in load_production_config().get("strategies", {}).items():
        if symbol in s_cfg.get("universe", []): membership.append({"strategy": s_name, "type": "universe"})
        elif symbol in s_cfg.get("watchlist", []): membership.append({"strategy": s_name, "type": "watchlist"})
    return {"symbol": symbol, "name": meta.get("name") or symbol, "logo_url": meta.get("logo_url"), "last_price": last_price, "timestamp": ts, "signals": asset_signals, "membership": membership, "open_positions": [p for p in db.get_open_positions() if p["symbol"] == symbol], "validations": [v for v in db.get_validations_filtered(verdict="VALIDATED") if v["symbol"] == symbol]}

@router.get("/asset/{symbol}/logo")
async def get_asset_logo_proxy(symbol: str, db: SignalRadarDB = Depends(get_db)):
    """Proxy for asset logo with browser-like headers."""
    meta = db.get_asset_metadata(symbol)
    if not meta or not meta.get("logo_url"):
        raise HTTPException(status_code=404)
    
    url = meta["logo_url"]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
    }
    
    try:
        async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
            resp = await client.get(url, headers=headers, follow_redirects=True)
            if resp.status_code != 200:
                logger.error(f"Logo proxy failed for {symbol}: {resp.status_code}")
                raise HTTPException(status_code=404)
            
            return Response(content=resp.content, media_type=resp.headers.get("Content-Type", "image/png"))
    except Exception as e:
        logger.error(f"Logo proxy exception for {symbol}: {str(e)}")
        raise HTTPException(status_code=404) # Fallback to 404 to trigger frontend initials

@router.get("/asset/{symbol}/history")
def get_asset_history(symbol: str, days: int = Query(60, gt=0, le=365), db: SignalRadarDB = Depends(get_db)) -> list:
    return db.get_signal_history(symbol=symbol, days=days)

@router.get("/asset/{symbol}/prices")
def get_asset_prices(symbol: str, days: int = Query(60, gt=0, le=365), db: SignalRadarDB = Depends(get_db)) -> list:
    import pandas as pd
    start_date = (pd.Timestamp.now() - pd.Timedelta(days=days)).strftime("%Y-%m-%d")
    df = db.get_ohlcv(symbol, start=start_date)
    return [{"date": date.strftime("%Y-%m-%d") if isinstance(date, pd.Timestamp) else str(date), "close": float(row["close"])} for date, row in df.iterrows()]
