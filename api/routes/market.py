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

COMMON_DOMAINS = {
    "AAPL": "apple.com", "MSFT": "microsoft.com", "GOOGL": "google.com", "AMZN": "amazon.com",
    "META": "meta.com", "NVDA": "nvidia.com", "TSLA": "tesla.com", "AMD": "amd.com",
    "AVGO": "broadcom.com", "CRM": "salesforce.com", "ADBE": "adobe.com", "NFLX": "netflix.com",
    "ORCL": "oracle.com", "INTC": "intel.com", "CSCO": "cisco.com", "JPM": "jpmorganchase.com",
    "GS": "goldmansachs.com", "BAC": "bankofamerica.com", "V": "visa.com", "MA": "mastercard.com",
    "DIS": "disney.com", "PYPL": "paypal.com", "SQ": "block.xyz", "UBER": "uber.com",
    "ABNB": "airbnb.com", "KO": "cocacola.com", "PEP": "pepsico.com", "WMT": "walmart.com",
    "COST": "costco.com", "NKE": "nike.com", "SBUX": "starbucks.com", "CAT": "caterpillar.com",
    "XOM": "exxonmobil.com", "CVX": "chevron.com", "GE": "ge.com", "UNH": "uhg.com",
    "QQQ": "invesco.com", "SPY": "ssga.com", "DIA": "ssga.com", "VOO": "vanguard.com",
    "IVV": "ishares.com", "IWM": "ishares.com"
}

def get_proxy_url(symbol: str) -> str | None:
    if not symbol or "=X" in symbol: return None
    return f"/api/market/asset/{symbol}/logo"

def _compute_proximity(strategy: str, details: dict, params: dict) -> dict | None:
    """Calculates how close an asset is to its trigger level."""
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
        return {"near": near and rsi > threshold, "pct": round(pct, 1), "trend_ok": trend_ok, "label": f"RSI={rsi:.1f}"}
        
    elif strategy == "ibs":
        ibs = details.get("ibs")
        trend_ok = details.get("trend_ok")
        if ibs is None: return None
        threshold = params.get("ibs_entry_threshold", 0.2)
        near_zone = threshold * 2
        
        pct = 100.0 if ibs <= threshold else (0.0 if ibs >= near_zone else (near_zone - ibs) / (near_zone - threshold) * 100)
        near = ibs < near_zone
        if trend_ok is not None and not trend_ok: near = False
        return {"near": near and ibs > threshold, "pct": round(pct, 1), "trend_ok": trend_ok, "label": f"IBS={ibs:.3f}"}
        
    elif strategy == "tom":
        days_left = details.get("trading_days_left")
        if days_left is None: return None
        entry_window = details.get("entry_days_before_eom", params.get("entry_days_before_eom", 5))
        near_zone = entry_window + 3
        
        pct = 100.0 if days_left <= entry_window else (0.0 if days_left > near_zone else (near_zone - days_left) / (near_zone - entry_window) * 100)
        return {"near": days_left <= near_zone and days_left > entry_window, "pct": round(pct, 1), "trend_ok": True, "label": f"{days_left}d left"}
        
    return None

@router.get("/overview")
def get_market_overview(db: SignalRadarDB = Depends(get_db)) -> dict:
    config = load_production_config(); strategies_cfg = config.get("strategies", {})
    ts, all_signals = db.get_latest_signals()
    signal_map = {(s["strategy"], s["symbol"]): s for s in all_signals}
    
    # Load details for proximity calculation
    details_map = {}
    for s in all_signals:
        dj = s.get("details_json")
        if dj:
            try: details_map[(s["strategy"], s["symbol"])] = _json.loads(dj)
            except: pass
            
    open_pos_map = {p["symbol"]: True for p in db.get_open_positions()}
    
    asset_membership = {}
    for s_name, s_cfg in strategies_cfg.items():
        if not s_cfg.get("enabled", False): continue
        for sym in s_cfg.get("universe", []): asset_membership.setdefault(sym, {})[s_name] = True
        for sym in s_cfg.get("watchlist", []): asset_membership.setdefault(sym, {})[s_name] = False

    assets = []
    for sym in sorted(asset_membership.keys()):
        strat_data = {}
        close_price = None
        for s_name in strategies_cfg:
            if not strategies_cfg[s_name].get("enabled", False): continue
            sig = signal_map.get((s_name, sym))
            if sig:
                if close_price is None: close_price = sig["close_price"]
                
                prox = None
                if sig["signal"] in _PROXIMITY_SIGNALS:
                    params = strategies_cfg.get(s_name, {}).get("params", {})
                    details = details_map.get((s_name, sym))
                    prox = _compute_proximity(s_name, details, params)
                
                strat_data[s_name] = {
                    "signal": sig["signal"], 
                    "indicator_value": sig["indicator_value"], 
                    "indicator_label": INDICATOR_LABELS.get(s_name, s_name), 
                    "in_universe": asset_membership.get(sym, {}).get(s_name, False), 
                    "proximity": prox
                }
            elif s_name in asset_membership.get(sym, {}):
                strat_data[s_name] = {"signal": None, "indicator_value": None, "indicator_label": INDICATOR_LABELS.get(s_name, s_name), "in_universe": asset_membership[sym][s_name], "proximity": None}
        
        assets.append({
            "symbol": sym, 
            "logo_url": get_proxy_url(sym), 
            "close": close_price, 
            "strategies": strat_data, 
            "has_open_position": sym in open_pos_map,
            "position_strategies": [] 
        })
    return {"scanner_timestamp": ts, "assets": assets}

@router.get("/asset/{symbol}")
def get_asset_details(symbol: str, db: SignalRadarDB = Depends(get_db)) -> dict:
    ts, all_signals = db.get_latest_signals()
    last_price = db.get_latest_price(symbol)
    if last_price is None:
        df = db.get_ohlcv(symbol)
        if not df.empty: last_price = float(df.iloc[-1]["close"])
    
    return {
        "symbol": symbol, 
        "logo_url": get_proxy_url(symbol), 
        "last_price": last_price, 
        "timestamp": ts, 
        "signals": [s for s in all_signals if s["symbol"] == symbol],
        "open_positions": [p for p in db.get_open_positions() if p["symbol"] == symbol], 
        "validations": [v for v in db.get_validations_filtered(verdict="VALIDATED") if v["symbol"] == symbol]
    }

@router.get("/asset/{symbol}/logo")
async def get_asset_logo_proxy(symbol: str, db: SignalRadarDB = Depends(get_db)):
    """Ultra-robust logo proxy: uses DB, then Common Mapping, then Google."""
    domain = COMMON_DOMAINS.get(symbol)
    if not domain:
        meta = db.get_asset_metadata(symbol)
        if meta and meta.get("logo_url") and "logo.clearbit.com/" in meta["logo_url"]:
            domain = meta["logo_url"].split("logo.clearbit.com/")[1]
    
    if not domain: domain = f"{symbol.lower()}.com"
    if "=X" in symbol: raise HTTPException(status_code=404)

    url = f"https://www.google.com/s2/favicons?domain={domain}&sz=128"
    try:
        async with httpx.AsyncClient(verify=False, timeout=5.0) as client:
            resp = await client.get(url, follow_redirects=True)
            if resp.status_code == 200:
                return Response(content=resp.content, media_type=resp.headers.get("Content-Type", "image/png"))
    except: pass
    raise HTTPException(status_code=404)

@router.get("/asset/{symbol}/history")
def get_asset_history(symbol: str, days: int = Query(60), db: SignalRadarDB = Depends(get_db)) -> list:
    return db.get_signal_history(symbol=symbol, days=days)

@router.get("/asset/{symbol}/prices")
def get_asset_prices(symbol: str, days: int = Query(60), db: SignalRadarDB = Depends(get_db)) -> list:
    import pandas as pd
    start_date = (pd.Timestamp.now() - pd.Timedelta(days=days)).strftime("%Y-%m-%d")
    df = db.get_ohlcv(symbol, start=start_date)
    return [{"date": date.strftime("%Y-%m-%d") if isinstance(date, pd.Timestamp) else str(date), "close": float(row["close"])} for date, row in df.iterrows()]
