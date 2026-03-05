# Signal Radar — Workflow Backtest & Analyse

*Dernière mise à jour : Mars 2026*

---

## Vue d'ensemble

Le backtest dans Signal Radar suit une hiérarchie en 4 niveaux. Chaque niveau
répond à une question différente et s'appuie sur le précédent.

```
Niveau 1 — Backtest individuel   → L'edge existe-t-il ?        (validation)
Niveau 2 — Backtest portfolio    → Comment gérer $5k ensemble ? (sizing)
Niveau 3 — Paper trading         → Le backtest colle-t-il ?     (calibration)
Niveau 4 — Live trading          → Exécution réelle             (production)
```

Ne jamais sauter un niveau. En particulier, le backtest portfolio (Niveau 2)
ne remplace pas la validation individuelle (Niveau 1).

---

## Niveau 1 — Backtest individuel

### Quand l'utiliser
- Pour valider qu'une stratégie a un edge statistique sur un univers d'assets
- Pour rejeter ou confirmer un asset candidat
- Lors du refresh mensuel automatique

### Commandes

**Screen** (rapide, ~45 min pour tout l'univers, pas de robustesse) :
```bash
docker exec -it scanner python -m cli.screen rsi2 us_stocks_large
docker exec -it scanner python -m cli.screen ibs us_etfs_broad
docker exec -it scanner python -m cli.screen tom us_stocks_large
```

**Validate** (complet, ~6.5h pour tout, avec robustesse + t-test) :
```bash
docker exec -it scanner python -m cli.validate rsi2 us_stocks_large
docker exec -it scanner python -m cli.validate ibs us_etfs_sector
docker exec -it scanner python -m cli.validate tom us_etfs_broad
```

Univers disponibles : `us_stocks_large`, `us_etfs_broad`, `us_etfs_sector`

### Lire les résultats

Le rapport s'affiche dans la console et est sauvegardé dans
`validation_results/`. Le dashboard (onglet Backtest) affiche la matrice
de robustesse paramétrique.

**Critères de validation pour retenir un asset :**

| Critère | Seuil minimum | Seuil solide |
|---------|--------------|--------------|
| Profit Factor (PF) | > 1.4 | > 1.6 |
| Win Rate | > 60% | > 65% |
| Robustesse param. | > 80% combos positifs | 100% |
| Sous-périodes | 2/2 stables | 2/2 stables |
| T-test p-value | < 0.05 | < 0.01 |

### Comprendre les métriques clés

**Profit Factor (PF)** = Total gains / Total pertes.
PF 1.0 = breakeven. PF 1.5 = solide. PF 2.0+ = excellent (vérifier l'overfitting).

**Sharpe** = Rendement moyen par trade / Écart-type des rendements, annualisé
par le nombre **réel** de trades/an (pas 252). Utile pour comparer deux assets
avec le même PF mais des profils de risque différents.

**Robustesse paramétrique** = % des 48 combinaisons de paramètres qui restent
profitables. 100% signifie que l'edge ne dépend pas d'un réglage précis.

**T-test** = Test statistique sur mean(return_par_trade) > 0. p < 0.05 confirme
que les gains ne sont pas dus au hasard.

### Refresh mensuel automatique

Le cron tourne le 1er de chaque mois à 4h (mode screen, ~45 min) :
```
0 4 1 * * root . /app/.env.cron && cd /app && python scripts/monthly_refresh.py
```

Pour forcer un validate complet manuellement :
```bash
docker exec -it scanner python scripts/monthly_refresh.py --mode validate
```

Pour un seul combo :
```bash
docker exec -it scanner python scripts/monthly_refresh.py --combos rsi2:us_stocks_large
```

---

## Niveau 2 — Backtest portfolio

### Quand l'utiliser
- Pour décider de la `position_fraction` de chaque stratégie avec $5k réels
- Pour quantifier le coût des conflits de capital
- Pour savoir si $5k est suffisant ou si augmenter le capital est prioritaire

### Commande
```bash
docker exec -it scanner python scripts/portfolio_backtest.py
docker exec -it scanner python scripts/portfolio_backtest.py --capital 10000
```

### Ce que le rapport produit
- Nombre de trades skippés faute de capital
- Nombre de chevauchements par paire de stratégies
- Coût réel des conflits (PnL théorique vs PnL réel)
- Recommandation de `position_fraction` par stratégie
- Capital minimum estimé pour zéro conflit

### Règle de priorité des signaux (fixe, non optimisable)
En cas de conflit le même jour : **TOM > RSI2 > IBS**

Justification : TOM est le plus rare (12x/an) et le plus prévisible
(signal calendaire). IBS est le plus fréquent et peut attendre.

---

## Niveau 3 — Paper trading

### Objectif
Accumuler 30–50 trades fermés pour comparer les résultats réels aux
prédictions du backtest. Détecter les biais d'exécution (slippage réel,
gaps à l'ouverture) avant de risquer du capital live.

### Workflow quotidien

1. **22h15 CET** — Le scanner tourne automatiquement. Vérifier le résumé
   Telegram pour les signaux BUY/SELL du jour.

2. **À l'ouverture US (~15h30 CET)** — Si signal BUY : exécuter l'ordre
   au prix d'ouverture sur Saxo Bank (compte USD).

3. **Logging dans le dashboard** — Utiliser "Log Real Trade" pour enregistrer
   le trade paper avec le prix d'exécution réel.

4. **Notes et slippage** — Ajouter une note dans le Trade Journal si
   l'exécution dévie du signal (gap important, liquidité faible).

### Signaux d'alerte (Approaching Trigger)

Le dashboard affiche les assets qui s'approchent d'un seuil d'entrée.
Surveiller quotidiennement pour anticiper les entrées du lendemain.

### Sizing paper trading

Même règle que le live : `floor(5000 / prix_open)` actions pour IBS et TOM.
Pour RSI2 : `floor(5000 * 0.20 / prix_open)` actions (position_fraction=0.20).

---

## Niveau 4 — Live trading

### Prérequis avant de passer en live

- [ ] 30–50 trades paper fermés enregistrés dans le journal
- [ ] Rapport paper vs backtest généré et analysé
- [ ] Compte USD ouvert sur Saxo Bank Switzerland (obligatoire — FX 0.25%/trade
      détruit l'edge si compte en CHF/EUR)
- [ ] Dépôt Saxo confirmé (blocage Kraken résolu)
- [ ] Backtest portfolio exécuté → position_fractions calibrées

### Règles d'exécution live

- Exécuter uniquement à l'**ouverture du marché** (Market Order at Open)
- Ne jamais modifier la taille de position en cours de trade
- Ne jamais ajouter à une position perdante
- Respecter `max_positions: 1` par stratégie

---

## Hiérarchie des décisions stratégiques

```
Une stratégie est-elle rentable ?
  → Backtest individuel (Niveau 1)

Comment les 3 stratégies coexistent avec $5k ?
  → Backtest portfolio (Niveau 2)

Le backtest colle-t-il à la réalité ?
  → Paper trading (Niveau 3)

Quelle taille de position utiliser en live ?
  → Recommandation du backtest portfolio, confirmée par le paper trading
```

---

## Erreurs classiques à éviter

**1. Optimiser les paramètres sur les données OOS**
Les paramètres canoniques (RSI_period=2, entry=10, SMA_exit=5) viennent de
Connors et ne changent pas. Ne jamais ajuster un paramètre parce que ça
"améliore le backtest".

**2. Confondre rendement théorique et rendement réel**
La somme des 3 backtests individuels surévalue le rendement réel car elle
ignore les conflits de capital. Utiliser le backtest portfolio pour le chiffre réel.

**3. Passer en live sans rapport paper vs backtest**
Si le slippage réel est 2x le slippage backtest, l'edge peut disparaître sur
certains assets. Le paper trading mesure cela avant de risquer du capital.

**4. Annualiser le Sharpe avec 252 jours**
Utiliser le nombre réel de trades/an comme facteur d'annualisation. 252 gonfle
le Sharpe RSI2 de ~5.5x (erreur historique identifiée et corrigée).

---

## Référence rapide — Stratégies validées

| Stratégie | Params | Assets core | PF moyen | WR moyen | Durée |
|-----------|--------|-------------|----------|----------|-------|
| RSI(2) | entry<10, SMA200×1.01, exit SMA5 | META, V, NVDA, GOOGL | 1.6–3.5 | 65–75% | ~4 jours |
| IBS | entry<0.2, SMA200, exit>0.8 ou high[j-1] | NVDA, META, MSFT, AAPL | 1.5–2.1 | 60–70% | ~2-3 jours |
| TOM | J=5 avant EOM, exit M=3 | META, NFLX, COST, TSLA | 1.4–1.9 | 52–65% | ~8 jours |

---

## Fichiers clés

| Fichier | Rôle |
|---------|------|
| `config/production_params.yaml` | Paramètres canoniques, univers, capital |
| `VALIDATION_RESULTS.md` | Verdicts détaillés par asset/stratégie |
| `docs/ANALYSIS_IBS_TOM.md` | Analyse IBS TOM combiné (research, non déployé) |
| `scripts/monthly_refresh.py` | Refresh automatique mensuel |
| `scripts/portfolio_backtest.py` | Backtest capital partagé $5k |
| `validation_results/` | Rapports JSON de validation |
| `logs/` | Logs scanner et refresh |
