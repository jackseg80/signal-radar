"""Signal Radar -- FastAPI application."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routes import signals, positions, performance, market, backtest

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown."""
    yield


app = FastAPI(
    title="Signal Radar API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(signals.router, prefix="/api/signals", tags=["signals"])
app.include_router(positions.router, prefix="/api/positions", tags=["positions"])
app.include_router(performance.router, prefix="/api/performance", tags=["performance"])
app.include_router(market.router, prefix="/api/market", tags=["market"])
app.include_router(backtest.router, prefix="/api/backtest", tags=["backtest"])


@app.get("/api/health")
def health():
    """Health check."""
    return {"status": "ok"}


# Serve frontend SPA (AFTER API routes so /api/* takes priority)
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
