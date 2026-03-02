"""Scanner trigger endpoint."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter()

_scan_running = False

SCANNER_SCRIPT = Path(__file__).resolve().parent.parent.parent / "scripts" / "daily_scanner.py"


@router.post("/run")
async def run_scanner() -> dict:
    """Trigger the daily scanner manually.

    Runs the scanner as a subprocess. Only one scan at a time.
    """
    global _scan_running

    if _scan_running:
        raise HTTPException(status_code=409, detail="Scanner already running")

    _scan_running = True
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            ["python", str(SCANNER_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(SCANNER_SCRIPT.parent.parent),
        )

        return {
            "status": "completed" if result.returncode == 0 else "error",
            "returncode": result.returncode,
            "stdout_lines": result.stdout.strip().split("\n")[-20:] if result.stdout else [],
            "stderr_lines": result.stderr.strip().split("\n")[-10:] if result.stderr else [],
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Scanner timed out (5 min)")
    finally:
        _scan_running = False


@router.get("/status")
async def scanner_status() -> dict:
    """Check if a scan is currently running."""
    return {"running": _scan_running}
