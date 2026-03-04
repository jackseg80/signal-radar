"""Signal Radar -- FastAPI application."""

from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from api.routes import signals, positions, performance, market, backtest, scanner, live, journal

# Configuration des chemins
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"

app = FastAPI(title="Signal Radar API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routes
app.include_router(signals.router, prefix="/api/signals", tags=["signals"])
app.include_router(positions.router, prefix="/api/positions", tags=["positions"])
app.include_router(performance.router, prefix="/api/performance", tags=["performance"])
app.include_router(market.router, prefix="/api/market", tags=["market"])
app.include_router(backtest.router, prefix="/api/backtest", tags=["backtest"])
app.include_router(scanner.router, prefix="/api/scanner", tags=["scanner"])
app.include_router(live.router, prefix="/api/live", tags=["live"])
app.include_router(journal.router, prefix="/api/journal", tags=["journal"])

@app.get("/api/health")
def health():
    return {"status": "ok"}

# Serve Frontend
if FRONTEND_DIR.is_dir():
    # Mount assets directory first
    if (FRONTEND_DIR / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")

    # Catch-all route for the SPA
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # If the request is for a file that exists in dist (like favicon.ico), serve it
        file_path = FRONTEND_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        
        # Otherwise, serve index.html for React Router to handle the path
        return FileResponse(FRONTEND_DIR / "index.html")
else:
    @app.get("/")
    def index():
        return {"detail": "Frontend dist not found. Please build frontend first."}
