#!/bin/bash
set -e

DEPLOY_DIR="${DEPLOY_DIR:-$HOME/signal-radar}"
cd "$DEPLOY_DIR"

echo "========================================"
echo "  SIGNAL RADAR -- Deploy"
echo "========================================"

# Create persistent directories
mkdir -p data logs

# Pull latest code
echo "[*] Updating code..."
git pull origin master

# Build frontend (requires Node.js >= 18)
echo "[*] Building frontend..."
if [ -d "frontend" ] && [ -f "frontend/package.json" ]; then
    cd frontend
    npm ci --no-audit --no-fund
    npm run build
    cd "$DEPLOY_DIR"
    echo "[OK] Frontend built -> frontend/dist/"
else
    echo "[WARN] No frontend found -- skipping build"
fi

# Build Docker images
echo "[*] Building images..."
docker compose build

# Restart
echo "[*] Restarting containers..."
docker compose down --timeout 10 || true
docker compose up -d

# Verify
echo "[*] Verifying..."
sleep 3
RUNNING=$(docker compose ps --format '{{.Service}} {{.State}}' | grep -c running || true)
if [ "$RUNNING" -ge 2 ]; then
    echo ""
    echo "[OK] Both services running"
    echo "[OK] Scanner: cron 22:15 local time (Sun-Fri)"
    echo "[OK] Dashboard: http://$(hostname -I | awk '{print $1}'):8000"
    echo ""
    echo "Test scanner:"
    echo "  docker compose exec scanner python scripts/daily_scanner.py"
    echo ""
    echo "Test API:"
    echo "  curl http://localhost:8000/api/health"
else
    echo ""
    echo "[ERROR] Not all services running"
    docker compose ps
    docker compose logs --tail 20
    exit 1
fi
