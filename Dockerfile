FROM python:3.12-slim

# uv (cohérence scalp-radar) + cron
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends cron \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dépendances (layer cache — uv ~10x plus rapide que pip)
COPY requirements.txt ./
RUN uv pip install --system --no-cache -r requirements.txt

# Code projet
COPY engine/ engine/
COPY data/__init__.py data/base_loader.py data/yahoo_loader.py data/
COPY scripts/daily_scanner.py scripts/
COPY config/ config/

# Répertoires pour volumes
RUN mkdir -p data/cache logs

# Cron + entrypoint
COPY deploy/crontab /etc/cron.d/signal-radar
RUN chmod 0644 /etc/cron.d/signal-radar && crontab /etc/cron.d/signal-radar
COPY deploy/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD []
