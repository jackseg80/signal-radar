"""Scanner trigger endpoint."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException

router = APIRouter()

_scan_lock = asyncio.Lock()
_last_output: List[str] = []
_last_status: str = "idle" # idle, running, completed, error

@router.post("/run")
async def run_scanner():
    """Trigger daily scanner manually."""
    global _last_output, _last_status
    
    if _scan_lock.locked():
        raise HTTPException(status_code=409, detail="Scanner is already running")

    async def _task():
        global _last_output, _last_status
        async with _scan_lock:
            _last_status = "running"
            _last_output = ["Lancement du scanner..."]
            
            script_path = Path(__file__).resolve().parent.parent.parent / "scripts" / "daily_scanner.py"
            
            # Use asyncio to read output line by line
            process = await asyncio.create_subprocess_exec(
                sys.executable, str(script_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                text = line.decode().strip()
                if text:
                    _last_output.append(text)
                    # Keep only last 20 lines
                    if len(_last_output) > 20:
                        _last_output.pop(0)
            
                await asyncio.sleep(0.01) # Small pause to yield control

            return_code = await process.wait()
            if return_code == 0:
                _last_status = "completed"
                _last_output.append("Scanner terminé avec succès.")
            else:
                _last_status = "error"
                _last_output.append(f"Erreur : le processus a retourné le code {return_code}")

    # Fire and forget
    asyncio.create_task(_task())
    return {"status": "started"}


@router.get("/status")
async def scanner_status() -> dict:
    """Check if a scan is currently running and get latest output."""
    return {
        "running": _scan_lock.locked(),
        "status": _last_status,
        "output": _last_output
    }
