#!/bin/bash
set -e

# Write environment variables to a file that cron jobs can source.
# Cron does NOT inherit Docker env vars — this is the standard workaround.
env | grep -E '^(TELEGRAM_|TZ=|HOME=|PATH=)' > /app/.env.cron
echo "PYTHONPATH=/app" >> /app/.env.cron

echo "[signal-radar] Container started at $(date)"
echo "[signal-radar] TZ=${TZ:-not set}"
echo "[signal-radar] Cron schedule: 22:15 Sun-Fri (local time)"
if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
    echo "[signal-radar] Telegram: configured"
else
    echo "[signal-radar] Telegram: not configured (scanner will run without notifications)"
fi

# Optional: run scanner once at startup (for testing)
if [ "${RUN_ON_STARTUP:-false}" = "true" ]; then
    echo "[signal-radar] Running scanner on startup..."
    cd /app && python scripts/daily_scanner.py
fi

# Support direct command execution (e.g. docker compose exec scanner python ...)
if [ $# -gt 0 ]; then
    exec "$@"
fi

# Start cron in foreground (PID 1 — handles Docker signals correctly)
echo "[signal-radar] Starting cron daemon..."
exec cron -f
