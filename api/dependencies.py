"""FastAPI dependencies."""

from data.db import SignalRadarDB
from api.config import DB_PATH

_db: SignalRadarDB | None = None


def get_db() -> SignalRadarDB:
    """Singleton DB connection."""
    global _db
    if _db is None:
        _db = SignalRadarDB(str(DB_PATH))
    return _db
