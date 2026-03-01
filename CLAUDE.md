# CLAUDE.md — signal-radar

## Projet
Moteur de backtest trend following pour actions/forex (daily).
Signaux manuels pour exécution sur SaxoBank. Pas d'automatisation.
Réutilise les patterns de scalp-radar (D:\Python\scalp-radar\) mais code 100% indépendant.

## Stack
Python 3.12+, pytest, numpy, pandas, yfinance

## Commandes
- Tests : `pytest tests/ -v`
- Backtest single : `python scripts/optimize.py --strategy donchian --symbol AAPL`

## Règles
- JAMAIS modifier scalp-radar (D:\Python\scalp-radar\ = lecture seule)
- JAMAIS importer depuis scalp-radar — tout est copié et indépendant
- Tous les tests doivent passer avant commit
- Type hints + docstrings obligatoires
- Data loader toujours via BaseDataLoader (jamais yfinance en dur)
- Tests gap-aware = priorité #1 (ne pas avancer sans qu'ils passent)
