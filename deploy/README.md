# Déploiement signal-radar

Scanner RSI(2) quotidien avec notifications Telegram, conteneurisé avec Docker.

## Pré-requis

- Docker + Docker Compose sur le serveur (Ubuntu 22.04+)
- Bot Telegram créé via @BotFather (optionnel)

## Créer le bot Telegram

1. Ouvre Telegram, cherche **@BotFather**
2. `/newbot` → nom: "Signal Radar" → username: `signal_radar_xxx_bot`
3. Copie le token (format: `123456:ABC-DEF...`)
4. Envoie un message au bot (n'importe quoi)
5. Visite `https://api.telegram.org/bot<TOKEN>/getUpdates`
6. Copie le `chat_id` depuis la réponse JSON (`result[0].message.chat.id`)

## Déploiement

```bash
# 1. Clone le repo sur le serveur
git clone <repo-url> ~/signal-radar
cd ~/signal-radar

# 2. Configurer l'environnement
cp .env.example .env
nano .env  # remplir TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID

# 3. Déployer
bash deploy/deploy.sh
```

## Test

```bash
# Exécuter le scanner manuellement (sans attendre 22h15)
docker compose exec scanner python scripts/daily_scanner.py

# Tester l'envoi Telegram
docker compose exec scanner python -c "
from engine.notifier import send_telegram
send_telegram('Test Signal Radar')
"
```

## Monitoring

```bash
# Logs en temps réel
docker compose logs -f

# Dernières lignes
docker compose logs --tail 50

# État des positions
docker compose exec scanner cat data/positions.json

# Historique des signaux
docker compose exec scanner tail -20 data/signal_history.csv
```

## Mise à jour

```bash
cd ~/signal-radar
bash deploy/deploy.sh
# Le script fait: git pull → build → restart → vérification
```

## Dépannage

**Le scanner ne tourne pas à 22h15 :**
- Vérifier le timezone : `docker compose exec scanner date`
- Vérifier le cron : `docker compose exec scanner crontab -l`

**Telegram n'envoie pas :**
- Vérifier les variables : `docker compose exec scanner env | grep TELEGRAM`
- Le scanner fonctionne sans Telegram (mode silencieux)

**Données Yahoo obsolètes :**
- Cache parquet dans `data/cache/` — supprimer pour forcer un re-téléchargement
- `docker compose exec scanner rm -rf data/cache/*.parquet`
