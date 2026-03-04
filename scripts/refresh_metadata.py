import yfinance as yf
from data.db import SignalRadarDB
from loguru import logger
import time
import os

def refresh_metadata():
    # Force PYTHONPATH or relative import if needed
    db = SignalRadarDB("data/signal_radar.db")
    
    # Get all symbols from OHLCV and Validations
    ohlcv_symbols = [a["symbol"] for a in db.list_assets()]
    validations = db.get_validations_filtered()
    val_symbols = [v["symbol"] for v in validations]
    
    symbols = sorted(list(set(ohlcv_symbols + val_symbols)))
    logger.info(f"Refreshing metadata for {len(symbols)} symbols...")
    
    for symbol in symbols:
        try:
            logger.info(f"Fetching info for {symbol}...")
            
            # Special case for Forex
            if symbol.endswith("=X"):
                name = symbol.replace("=X", "")
                name = f"{name[:3]}/{name[3:]} Forex Pair"
                db.save_asset_metadata(symbol, name, None)
                continue

            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            name = info.get("longName") or info.get("shortName") or symbol
            
            # IMPROVED LOGO LOGIC
            logo_url = None
            
            # 1. Try to get domain from website info
            website = info.get("website")
            if website:
                # Extract domain (e.g. https://www.apple.com -> apple.com)
                domain = website.replace("http://", "").replace("https://", "").replace("www.", "").split("/")[0]
                if domain:
                    logo_url = f"https://logo.clearbit.com/{domain}"
            
            # 2. Fallback for ETFs (Yahoo often has no website for them)
            if not logo_url and (symbol.startswith("XL") or symbol in ["SPY", "QQQ", "DIA", "IWM"]):
                # Generic financial icon for ETFs if no logo
                logo_url = f"https://api.faviconkit.com/ssga.com/144" if "SPDR" in name else None

            db.save_asset_metadata(symbol, name, logo_url)
            logger.success(f"Saved {symbol}: {name} (Logo: {logo_url})")
            
            # Avoid hitting Yahoo too hard
            time.sleep(0.5)
            
        except Exception as e:
            logger.error(f"Error fetching {symbol}: {e}")

if __name__ == "__main__":
    refresh_metadata()
