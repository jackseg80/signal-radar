# Deploiement signal-radar

Scanner multi-strategie (RSI2 + IBS + TOM) avec notifications Telegram + dashboard web, conteneurise avec Docker.

## Pre-requis

- Docker + Docker Compose sur le serveur (Ubuntu 22.04+)
- Bot Telegram cree via @BotFather (optionnel)

## Creer le bot Telegram

1. Ouvre Telegram, cherche **@BotFather**
2. `/newbot` -> nom: "Signal Radar" -> username: `signal_radar_xxx_bot`
3. Copie le token (format: `123456:ABC-DEF...`)
4. Envoie un message au bot (n'importe quoi)
5. Visite `https://api.telegram.org/bot<TOKEN>/getUpdates`
6. Copie le `chat_id` depuis la reponse JSON (`result[0].message.chat.id`)

## Deploiement

```bash
# 1. Clone le repo sur le serveur
git clone <repo-url> ~/signal-radar
cd ~/signal-radar

# 2. Configurer l'environnement
cp .env.example .env
nano .env  # remplir TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID

# 3. Deployer (build images Docker + start)
bash deploy/deploy.sh
```

## Dashboard

Apres deploiement, le dashboard est accessible sur le LAN :

```bash
# Depuis le reseau local
http://<server-ip>:9000

# API docs (Swagger auto-genere)
http://<server-ip>:9000/docs

# Health check
curl http://<server-ip>:9000/api/health
```

Le dashboard est read-only et affiche :

- Signaux du jour (RSI2, IBS, TOM)
- Positions paper trading ouvertes/fermees
- Performance et equity curve
- Market overview multi-strategie
- Resultats backtest et validations

Les donnees sont mises a jour par le scanner a 22h15.

## Test

```bash
# Executer le scanner manuellement (sans attendre 22h15)
docker compose exec scanner python scripts/daily_scanner.py

# Tester l'API
curl http://localhost:9000/api/health

# Tester l'envoi Telegram
docker compose exec scanner python -c "
from engine.notifier import send_telegram
send_telegram('Test Signal Radar')
"
```

## Monitoring

```bash
# Logs en temps reel
docker compose logs -f

# Logs d'un service
docker compose logs -f scanner
docker compose logs -f api

# Etat des services
docker compose ps

# Signaux du jour via API
curl http://localhost:9000/api/signals/today
```

## Mise a jour

```bash
cd ~/signal-radar
bash deploy/deploy.sh
# Le script fait: git pull -> docker compose build (npm build inclus) -> restart -> verification
```

## Depannage

**Le scanner ne tourne pas a 22h15 :**

- Verifier le timezone : `docker compose exec scanner date`
- Verifier le cron : `docker compose exec scanner crontab -l`

**Telegram n'envoie pas :**

- Verifier les variables : `docker compose exec scanner env | grep TELEGRAM`
- Le scanner fonctionne sans Telegram (mode silencieux)

**Le dashboard ne repond pas :**

- Verifier le service : `docker compose ps api`
- Logs API : `docker compose logs api --tail 20`
- Au premier deploiement, lancer le scanner une fois pour creer la DB :
  `docker compose exec scanner python scripts/daily_scanner.py`
