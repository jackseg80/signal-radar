"""Market overview endpoint with proximity-to-trigger alerts."""

import json as _json
import httpx
from fastapi import APIRouter, Depends, Query, HTTPException, Response
from loguru import logger

from data.db import SignalRadarDB
from api.config import load_production_config
from api.dependencies import get_db

router = APIRouter()

INDICATOR_LABELS = {"rsi2": "RSI(2)", "ibs": "IBS", "tom": "Days left"}
_PROXIMITY_SIGNALS = {"NO_SIGNAL", "WATCH"}

# Expanded mapping including major ETF issuers
COMMON_DOMAINS = {
    # Tech & Stocks
    "AAPL": "apple.com", "MSFT": "microsoft.com", "GOOGL": "google.com", "AMZN": "amazon.com",
    "META": "meta.com", "NVDA": "nvidia.com", "TSLA": "tesla.com", "AMD": "amd.com",
    "AVGO": "broadcom.com", "CRM": "salesforce.com", "ADBE": "adobe.com", "NFLX": "netflix.com",
    "ORCL": "oracle.com", "INTC": "intel.com", "CSCO": "cisco.com", "JPM": "jpmorganchase.com",
    "GS": "goldmansachs.com", "BAC": "bankofamerica.com", "V": "visa.com", "MA": "mastercard.com",
    "DIS": "disney.com", "PYPL": "paypal.com", "SQ": "block.xyz", "UBER": "uber.com",
    "ABNB": "airbnb.com", "KO": "cocacola.com", "PEP": "pepsico.com", "WMT": "walmart.com",
    "COST": "costco.com", "NKE": "nike.com", "SBUX": "starbucks.com", "CAT": "caterpillar.com",
    "XOM": "exxonmobil.com", "CVX": "chevron.com", "GE": "ge.com", "UNH": "uhg.com",
    
    # ETFs (Major issuers)
    "QQQ": "invesco.com",
    "SPY": "ssga.com", "DIA": "ssga.com", 
    "XLY": "ssga.com", "XLP": "ssga.com", "XLE": "ssga.com", "XLF": "ssga.com", 
    "XLV": "ssga.com", "XLI": "ssga.com", "XLB": "ssga.com", "XLK": "ssga.com", 
    "XLU": "ssga.com", "XLRE": "ssga.com", "XLC": "ssga.com",
    "VOO": "vanguard.com", "VTI": "vanguard.com", "BND": "vanguard.com",
    "IVV": "ishares.com", "IWM": "ishares.com", "IJR": "ishares.com", "EFA": "ishares.com", "IEFA": "ishares.com"
}

def _get_domain(symbol: str, db: SignalRadarDB) -> str | None:
    """Helper to find a domain for a symbol."""
    if symbol in COMMON_DOMAINS:
        return COMMON_DOMAINS[symbol]
    
    meta = db.get_asset_metadata(symbol)
    if meta and meta.get("logo_url") and "logo.clearbit.com/" in meta["logo_url"]:
        return meta["logo_url"].split("logo.clearbit.com/")[1]
    
    return None

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
    ts, all_signals = db.get_latest_signals()
    signal_map = {(s["strategy"], s["symbol"]): s for s in all_signals}
    details_map = { (s["strategy"], s["symbol"]): _json.loads(s["details_json"]) for s in all_signals if s.get("details_json") }
    open_pos_map = {}
    for p in db.get_open_positions(): open_pos_map.setdefault(p["symbol"], []).append(p["strategy"])
    
    # Pre-calculate assets membership
    asset_membership = {}
    for strat_name, strat_cfg in strategies_cfg.items():
        if not strat_cfg.get("enabled", False): continue
        for sym in strat_cfg.get("universe", []): asset_membership.setdefault(sym, {})[strat_name] = True
        for sym in strat_cfg.get("watchlist", []): asset_membership.setdefault(sym, {})[strat_name] = False

    assets = []
    for sym in sorted(asset_membership.keys()):
        strat_data = {}
        close_price = None
        for strat_name in strategies_cfg:
            if not strategies_cfg[strat_name].get("enabled", False): continue
            sig = signal_map.get((strat_name, sym))
            if sig:
                if close_price is None: close_price = sig["close_price"]
                prox = _compute_proximity(strat_name, details_map.get((strat_name, sym)), strategies_cfg.get(strat_name, {}).get("params", {})) if sig["signal"] in _PROXIMITY_SIGNALS else None
                strat_data[strat_name] = {"signal": sig["signal"], "indicator_value": sig["indicator_value"], "indicator_label": INDICATOR_LABELS.get(strat_name, strat_name), "in_universe": asset_membership.get(sym, {}).get(strat_name, False), "proximity": prox}
            elif strat_name in asset_membership.get(sym, {}):
                strat_data[strat_name] = {"signal": None, "indicator_value": None, "indicator_label": INDICATOR_LABELS.get(strat_name, strat_name), "in_universe": asset_membership[sym][strat_name], "proximity": None}
        
        # Only provide logo URL if we actually have a domain
        domain = _get_domain(sym, db)
        logo_url = f"/api/market/asset/{sym}/logo" if domain else None
        
        assets.append({
            "symbol": sym, 
            "name": sym, # Minimal name to keep it fast
            "logo_url": logo_url, 
            "close": close_price, 
            "strategies": strat_data, 
            "has_open_position": sym in open_pos_map, 
            "position_strategies": open_pos_map.get(sym, [])
        })
    return {"scanner_timestamp": ts, "assets": assets}

@router.get("/asset/{symbol}")
def get_asset_details(symbol: str, db: SignalRadarDB = Depends(get_db)) -> dict:
    meta = db.get_asset_metadata(symbol) or {}
    ts, all_signals = db.get_latest_signals(); asset_signals = [s for s in all_signals if s["symbol"] == symbol]
    last_price = db.get_latest_price(symbol)
    if last_price is None:
        df = db.get_ohlcv(symbol)
        if not df.empty: last_price = float(df.iloc[-1]["close"])
    
    domain = _get_domain(symbol, db)
    logo_url = f"/api/market/asset/{symbol}/logo" if domain else None
    
    return {
        "symbol": symbol, 
        "name": meta.get("name") or symbol, 
        "logo_url": logo_url, 
        "last_price": last_price, 
        "timestamp": ts, 
        "signals": asset_signals, 
        "membership": [], 
        "open_positions": [p for p in db.get_open_positions() if p["symbol"] == symbol], 
        "validations": [v for v in db.get_validations_filtered(verdict="VALIDATED") if v["symbol"] == symbol]
    }

@router.get("/asset/{symbol}/logo")
async def get_asset_logo_proxy(symbol: str, db: SignalRadarDB = Depends(get_db)):
    """Ultra-robust logo proxy: uses DB, then Common Mapping, then Google."""
    domain = _get_domain(symbol, db)
    
    if not domain:
        # Final guess attempt for the proxy specifically
        if not symbol.includes('=X'):
            domain = f"{symbol.lower()}.com"
        else:
            raise HTTPException(status_code=404)

    # Use Google Favicon service via proxy
    url = f"https://www.google.com/s2/favicons?domain={domain}&sz=128"
    
    try:
        async with httpx.AsyncClient(verify=False, timeout=5.0) as client:
            resp = await client.get(url, follow_redirects=True)
            if resp.status_code == 200:
                return Response(content=resp.content, media_type=resp.headers.get("Content-Type", "image/png"))
    except: pass
    raise HTTPException(status_code=404)

@router.get("/asset/{symbol}/history")
def get_asset_history(symbol: str, days: int = Query(60, gt=0, le=365), db: SignalRadarDB = Depends(get_db)) -> list:
    return db.get_signal_history(symbol=symbol, days=days)

@router.get("/asset/{symbol}/prices")
def get_asset_prices(symbol: str, days: int = Query(60, gt=0, le=365), db: SignalRadarDB = Depends(get_db)) -> list:
    import pandas as pd
    start_date = (pd.Timestamp.now() - pd.Timedelta(days=days)).strftime("%Y-%m-%d")
    df = db.get_ohlcv(symbol, start=start_date)
    return [{"date": date.strftime("%Y-%m-%d") if isinstance(date, pd.Timestamp) else str(date), "close": float(row["close"])} for date, row in df.iterrows()]
