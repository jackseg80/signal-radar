#!/bin/bash
# deploy/deploy.sh
set -e

DEPLOY_DIR="${DEPLOY_DIR:-$HOME/signal-radar}"
cd "$DEPLOY_DIR"

echo "========================================"
echo "  SIGNAL RADAR -- Déploiement Optimisé"
echo "========================================"

# 1. Vérification de l'environnement
mkdir -p data logs
if [ ! -f .env ]; then
    echo "[!] ATTENTION : .env non trouvé. Création depuis .env.example..."
    cp .env.example .env
    echo "[!] Modifiez le fichier .env avec vos accès réels !"
fi

# 2. Mise à jour du code (Force le nettoyage)
echo "[*] Mise à jour du code depuis master..."
OLD_REV=$(git rev-parse HEAD)
git fetch origin master
git reset --hard origin/master
NEW_REV=$(git rev-parse HEAD)

if [ "$OLD_REV" != "$NEW_REV" ]; then
    echo "[*] Changements détectés ($OLD_REV -> $NEW_REV) :"
    git diff --stat "$OLD_REV" "$NEW_REV"
    echo ""
    echo "[*] Dernier commit :"
    git log -1 --pretty=format:"%h - %s (%cr) <%an>"
    echo ""
else
    echo "[*] Le code est déjà à jour (version $NEW_REV)."
fi

# 3. Build Docker
echo "[*] Construction des images..."
docker compose build --pull

# 4. Redémarrage propre
echo "[*] Redémarrage des conteneurs..."
docker compose down --timeout 15 || true
docker compose up -d --remove-orphans

# 5. Vérification intelligente
echo "[*] Vérification des services (attente 5s)..."
sleep 5

SERVICES=("api" "scanner")
ERREUR=0

for svc in "${SERVICES[@]}"; do
    STATUS=$(docker compose ps --format '{{.State}}' "$svc" 2>/dev/null || echo "introuvable")
    if [[ "$STATUS" == *"running"* ]]; then
        echo "[OK] Service $svc est opérationnel"
    else
        echo "[ERREUR] Service $svc est dans l'état : $STATUS"
        ERREUR=1
    fi
done

# 6. Conclusion
if [ $ERREUR -eq 0 ]; then
    echo ""
    echo "Déploiement réussi !"
    echo "Dashboard : http://$(hostname -I | awk '{print $1}'):9000"
    echo "API Health : http://localhost:9000/api/health"
    
    # Nettoyage seulement si tout va bien
    docker image prune -f
else
    echo "----------------------------------------"
    echo "[!] ÉCHEC DU DÉPLOIEMENT"
    docker compose ps
    docker compose logs --tail 50
    exit 1
fi
