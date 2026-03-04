import yfinance as yf
from data.db import SignalRadarDB
from loguru import logger
import time

def refresh_metadata():
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
                # Generate a flag-based logo URL or similar if possible
                # For now, just name
                db.save_asset_metadata(symbol, name, None)
                continue

            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            name = info.get("longName") or info.get("shortName") or symbol
            logo_url = info.get("logo_url")
            
            # Some tickers don't have logo_url in ticker.info anymore
            # Fallback to clearbit for stocks
            if not logo_url and "." not in symbol:
                domain = info.get("website", "").replace("http://", "").replace("https://", "").split("/")[0]
                if domain:
                    logo_url = f"https://logo.clearbit.com/{domain}"

            db.save_asset_metadata(symbol, name, logo_url)
            logger.success(f"Saved {symbol}: {name}")
            
            # Avoid hitting Yahoo too hard
            time.sleep(0.5)
            
        except Exception as e:
            logger.error(f"Error fetching {symbol}: {e}")

if __name__ == "__main__":
    refresh_metadata()
