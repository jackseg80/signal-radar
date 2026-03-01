# Phase 2 — Individual Stocks + Daily Scanner + Deployment

Période : 2026-03-01
Objectif : remplacer l'univers ETFs ($100k) par des actions individuelles viables à $10k,
puis déployer un scanner quotidien automatisé avec notifications Telegram.

---

## Démarche

```text
ETFs $100k (PF 1.36) → Sizing test $10k → ETFs marginaux (PF 1.15) → Pivot stocks individuels
→ 15 stocks testés → 6 candidats PF > 1.3 → Robustesse 3 validés + 1 watchlist
→ Scanner quotidien → Docker + Telegram
```

**Raison du pivot ETFs → stocks** : les ETFs sont trop liquides pour des pullbacks RSI(2) profonds.
Un RSI(2) < 10 sur SPY = drop de ~1.5% → rebond attendu ~0.5% → AvgPnL $1.56 à $10k.
Sur actions individuelles, le même signal correspond à un drop de 5–10% → AvgPnL $6.15.

---

## Step 11 — Univers 15 actions US

**Script** : `scripts/validate_rsi2_stocks.py`
**Période OOS** : 2014–2025. **Capital** : $10 000, whole shares. **Fee model** : `us_stocks_usd_account`.

### Résultats OOS 2014–2025 (triés par PF)

| Ticker | Trades | WR  | PF   | Sharpe | Net%   | AvgPnL$ |
|--------|--------|-----|------|--------|--------|---------|
| META   | 84     | 74% | 2.98 | 1.09   | +18.4% | $21.94  |
| MSFT   | 78     | 73% | 1.74 | 0.48   | +6.9%  | $8.89   |
| GOOGL  | 78     | 68% | 1.66 | 0.49   | +8.3%  | $10.59  |
| AMZN   | 71     | 65% | 1.48 | 0.35   | +5.8%  | $8.17   |
| NVDA   | 86     | 67% | 1.48 | 0.34   | +13.6% | $15.84  |
| GS     | 63     | 63% | 1.44 | 0.30   | +3.9%  | $6.16   |
| AMD    | 73     | 62% | 1.29 | 0.19   | +8.6%  | $11.84  |
| AAPL   | 82     | 66% | 1.20 | 0.18   | +2.9%  | $3.55   |
| WMT    | 69     | 71% | 1.13 | 0.09   | +0.9%  | $1.29   |
| CAT    | 67     | 63% | 1.06 | 0.05   | +0.9%  | $1.27   |
| KO/XOM | —     | —   | ~1.0 | —      | ~0%    | —       |
| TSLA   | 51     | 63% | 0.98 | -0.03  | -0.5%  | -$1.00  |
| JPM    | 82     | 60% | 0.91 | -0.09  | -1.3%  | -$1.63  |
| JNJ    | 65     | 54% | 0.62 | -0.40  | -3.0%  | -$4.59  |

**Poolé 15 stocks** : 1063 trades, WR 65%, PF 1.30, Sharpe 0.69, t-test p=0.0116.
**Candidats retenus** (PF > 1.3) : META, MSFT, GOOGL, AMZN, NVDA, GS.

### Comparaison ETFs vs stocks à $10k

| Univers           | Trades | WR  | PF   | Sharpe | AvgPnL$ |
|-------------------|--------|-----|------|--------|---------|
| ETFs (5, $10k)    | 380    | 69% | 1.15 | 0.28   | $1.56   |
| Stocks (15, $10k) | 1063   | 65% | 1.30 | 0.69   | $6.15   |

---

## Step 12 — Robustesse 6 candidats

**Script** : `scripts/validate_rsi2_stocks_robustness.py`

### V1 — Robustesse paramétrique (48 combos)

Grille : RSI_threshold ∈ {5,10,15,20} × SMA_trend ∈ {150,200,250} × SMA_exit ∈ {3,5,7,10}

| Ticker | Combos PF>1 | % Profitable | Robuste? |
|--------|-------------|--------------|----------|
| META   | 48/48       | 100%         | OUI      |
| MSFT   | 48/48       | 100%         | OUI      |
| GOOGL  | 48/48       | 100%         | OUI      |
| NVDA   | 48/48       | 100%         | OUI      |
| AMZN   | 42/48       | 88%          | OUI      |
| GS     | 23/48       | 48%          | NON      |

Seuil : > 80% combos profitables.

### V2 — Stabilité sous-périodes

OOS-A : 2014-01 → 2019-06 / OOS-B : 2019-07 → 2025-01.

| Ticker | PF-A | PF-B | Stable? |
|--------|------|------|---------|
| META   | 6.26 | 3.19 | OUI     |
| MSFT   | 1.81 | 2.43 | OUI     |
| GOOGL  | 1.07 | 2.45 | OUI     |
| NVDA   | 1.42 | 2.10 | OUI     |
| AMZN   | 2.59 | 0.92 | NON     |
| GS     | 2.36 | 2.09 | OUI     |

Seuil : PF > 1.0 dans les deux sous-périodes.

### V3 — Significativité statistique (t-test)

| Ticker | Mean Ret% | p-value | Significatif? |
|--------|-----------|---------|---------------|
| META   | +0.200%   | 0.0003  | p < 0.05      |
| MSFT   | +0.085%   | 0.057   | p < 0.10      |
| GOOGL  | +0.100%   | 0.055   | p < 0.10      |
| NVDA   | +0.142%   | 0.135   | NON           |
| AMZN   | +0.078%   | 0.126   | NON           |
| GS     | +0.059%   | 0.162   | NON           |

### Matrice de décision finale

| Ticker    | Robuste >80% | Stable | Signif p<0.10 | VERDICT     |
|-----------|-------------|--------|---------------|-------------|
| **META**  | 100%        | OUI    | OUI           | **VALIDE**  |
| **MSFT**  | 100%        | OUI    | OUI           | **VALIDE**  |
| **GOOGL** | 100%        | OUI    | OUI           | **VALIDE**  |
| NVDA      | 100%        | OUI    | NON           | WATCHLIST   |
| AMZN      | 88%         | NON    | NON           | REJETE      |
| GS        | 48%         | OUI    | NON           | REJETE      |

---

## Univers de production

| Rôle                         | Tickers           | Fee model             |
|------------------------------|-------------------|-----------------------|
| Actif (signaux BUY auto)     | META, MSFT, GOOGL | us_stocks_usd_account |
| Watchlist (indicateurs seul) | NVDA              | us_stocks_usd_account |

**NVDA** : 100% robust, stable — pas encore significatif (p=0.135, ~86 trades OOS).
À promouvoir dans l'univers actif si la p-value passe sous 0.10 avec un historique plus long.

---

## Step 13 — Scanner quotidien

**Script** : `scripts/daily_scanner.py` — opérationnel depuis 2026-03-01.

### Architecture du scanner

- `evaluate_signal(rsi2, close, sma200, sma5, position, ..., watchlist=False)` → `SignalResult`
  — fonction pure testable, miroir exact du backtest
- Signaux : BUY / SELL / SAFETY_EXIT / HOLD / NO_SIGNAL / PENDING_VALID / PENDING_EXPIRED / WATCH
- `data/positions.json` — state machine : null → pending (auto) → open (manuel) → null (manuel)
- `data/signal_history.csv` — log append-only
- `logs/scanner.log` — log rotatif (loguru, 1 MB, 30 jours)

### Cohérence anti-look-ahead

| Action | Timing backtest | Timing scanner |
|--------|-----------------|----------------|
| Signal entry | close[i-1] | today's close |
| Execution entry | open[i] | tomorrow's open |
| Signal exit | close[i-1] | today's close |
| Execution exit | open[i] | tomorrow's open |

### Workflow manuel Saxo

1. Lancer scanner après clôture US (~22h CET)
2. BUY → pending auto dans positions.json → exécuter au open suivant
3. Mettre à jour positions.json manuellement : `status: open`, `entry_price: <prix>`
4. SELL / SAFETY_EXIT → exécuter manuellement → remettre `null` dans positions.json

---

## Step 14 — Déploiement Docker + Telegram

### Architecture

```text
Dockerfile
  python:3.12-slim + uv + cron
  ENTRYPOINT ["/entrypoint.sh"]
  CMD []  (passthrough pour exec manuel)

docker-compose.yml
  service scanner
  volumes: data/, logs/, config/ (read-only)
  restart: unless-stopped
  env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TZ

deploy/entrypoint.sh
  Écrit les env vars dans /app/.env.cron pour le cron
  Passthrough : if [ $# -gt 0 ]; then exec "$@"; fi

deploy/crontab
  15 22 * * 0-5  → scanner à 22h15 dim-ven (TZ=Europe/Zurich)
```

### Notifications Telegram

- BUY / SELL / SAFETY_EXIT → message immédiat avec prix et indicateurs
- WATCH avec trigger BUY → inclus dans le message principal
- Silence si aucun signal actionnable (pas de spam quotidien)
- Rapport hebdo dimanche soir même sans signal
- `html.escape(r.notes)` obligatoire — notes contiennent `<` et `>` (RSI=7.4 < 10.0)

### Déploiement serveur Ubuntu

```bash
cp .env.example .env          # TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID
bash deploy/deploy.sh         # rsync + docker compose up -d
docker compose exec scanner python scripts/daily_scanner.py  # test
```

### Variables d'environnement

```env
TELEGRAM_BOT_TOKEN=<bot_token>
TELEGRAM_CHAT_ID=<chat_id>
TZ=Europe/Zurich
```

---

## Findings critiques

### 1. Stocks > ETFs à $10k grâce aux pullbacks plus profonds

RSI(2) < 10 sur action = drop de 5–10% → rebond attendu proportionnellement plus large.
AvgPnL $6.15 (stocks) vs $1.56 (ETFs) : 4× plus de PnL moyen par trade.

### 2. La robustesse > PF brut comme critère de sélection

- GS (PF 1.44) rejeté : 48% combos profitables — edge fragile, dépend des params exacts
- AMZN (PF 1.48) rejeté : PF-B = 0.92 en 2019–2025 — edge non persistant
- Un PF élevé sur la période complète peut masquer un collapse en sous-période récente

### 3. Défensives et énergie ne mean-revertent pas

KO, JNJ, XOM : PF ≈ 1.0. Dividendes et cycles matières premières dominent le signal RSI court terme.
Le MR court-terme est une propriété des growth/tech equity liquides.

### 4. Compte USD sur Saxo obligatoire

FX 0.25%/trade (compte EUR) = round-trip ~0.62% → edge détruit.
Compte USD : round-trip ~0.12% → PF 1.66–2.98 viable.

### 5. `html.escape()` obligatoire pour Telegram HTML

`r.notes` contient des chevrons (ex. "RSI=7.4 < 10.0"). Sans `html.escape()`, l'API Telegram
rejette le message avec 400 Bad Request.

---

## Timeline Phase 2

| Step | Script                              | Résultat                                  |
|------|-------------------------------------|-------------------------------------------|
| 11   | validate_rsi2_stocks.py             | 15 stocks testés, 6 candidats PF > 1.3   |
| 12   | validate_rsi2_stocks_robustness.py  | 3 validés, 1 watchlist, 2 rejetés        |
| 13   | daily_scanner.py                    | Scanner quotidien opérationnel            |
| 14   | Dockerfile + docker-compose.yml     | Docker + cron déployé                     |
| 15   | notifier.py                         | Telegram notifications + rapport hebdo   |
