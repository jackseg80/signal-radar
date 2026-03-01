#!/bin/bash
set -e

DEPLOY_DIR="${DEPLOY_DIR:-$HOME/signal-radar}"
cd "$DEPLOY_DIR"

echo "========================================"
echo "  SIGNAL RADAR — Deploy"
echo "========================================"

# Create persistent directories
mkdir -p data logs

# Pull latest code
echo "[*] Updating code..."
git pull origin master

# Build
echo "[*] Building image..."
docker compose build

# Restart
echo "[*] Restarting container..."
docker compose down --timeout 10 || true
docker compose up -d

# Verify
echo "[*] Verifying..."
sleep 2
if docker compose ps --format '{{.State}}' | grep -q running; then
    echo ""
    echo "[OK] Container running"
    echo "[OK] Next scan: 22:15 local time (Sun-Fri)"
    echo ""
    echo "Test now with:"
    echo "  docker compose exec scanner python scripts/daily_scanner.py"
else
    echo ""
    echo "[ERROR] Container not running"
    docker compose logs --tail 20
    exit 1
fi
