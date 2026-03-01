# CLAUDE.md — signal-radar

## Project Status
Phase 1 COMPLETE — Phase 2 (daily signal scanner) in progress.
Validated strategy : RSI(2) mean reversion, 5 ETFs, params Connors canonical.

## Stack
Python 3.12+, pytest, numpy, pandas, scipy, yfinance

## Commandes
- Tests : `pytest tests/ -v`
- Validation finale : `python scripts/validate_rsi2_final.py`
- Params production : `config/production_params.yaml`

## Règles
- JAMAIS modifier scalp-radar (D:\Python\scalp-radar\ = lecture seule)
- JAMAIS importer depuis scalp-radar — tout est copié et indépendant
- Tous les tests doivent passer avant commit
- Type hints + docstrings obligatoires
- Data loader toujours via BaseDataLoader (jamais yfinance en dur)
- Tests gap-aware = priorité #1 (ne pas avancer sans qu'ils passent)

## Stratégie validée : RSI(2) Mean Reversion

Universe : SPY, QQQ, IWM, DIA, EFA

Params (Connors canonical, NON optimisés) :
- RSI(2) < 10 entry
- SMA(200) × 1.01 trend filter (buffer anti-whipsaw)
- SMA(5) exit (close > SMA5)
- Pas de stop-loss, position_fraction=0.2, long-only

Fee model : us_etfs_usd_account (compte USD Saxo, pas de conversion FX)

Résultats OOS 2014-2025 (Step 10) :
- 380 trades, WR 69%, PF 1.36, Sharpe 0.65
- t-test p=0.0166 (significatif)
- 100% des 48 combos de sensibilité PF > 1.0 (Step 7)
- Meilleur asset : QQQ (PF 1.83, Sharpe 0.63)

## Stratégies rejetées

1. Donchian TF sur US stocks (Steps 1-4) — WFO tout grade F (stocks mean-revertent)
2. Donchian TF sur forex majors (Step 8) — PF OOS 0.50 (range-bound post-2015)
3. RSI(2) sur GLD (Step 9) — PF OOS 0.95 (l'or trend, ne mean-revert pas)
4. RSI(2) sur TLT (Step 9) — PF OOS 1.04 (edge MR faible sur obligations)
5. RSI(2) sur XLE (Step 9) — PF OOS 1.02 (trop cyclique)

## Contraintes critiques

- Compte USD sur Saxo OBLIGATOIRE — FX 0.25%/trade tue l'edge court-terme
- Round-trip USD : ~0.07% ($1 commission + 0.03% spread)
- Round-trip EUR : ~0.55% → stratégie non viable en EUR

## Architecture

```
engine/
  indicators.py              — SMA, EMA, Donchian, ATR, ADX, RSI (Wilder)
  indicator_cache.py         — Build cache indicateurs par asset (SMA/RSI by period)
  fee_model.py               — FeeModel dataclass + presets (US_ETFS_USD, FOREX, etc.)
  backtest_config.py         — BacktestConfig (symbol, capital, slippage, fee_model)
  fast_backtest.py           — Engine trend following (Donchian/EMA, trailing ATR stop)
  mean_reversion_backtest.py — Engine RSI(2) mean reversion (SMA filter, SMA exit)

data/
  base_loader.py             — BaseDataLoader + to_cache_arrays()
  yahoo_loader.py            — YahooLoader, cache parquet, adj-close O/H/L

optimization/
  walk_forward.py            — WFO fenêtres en barres (trading days)
  overfit_detection.py       — Monte Carlo block bootstrap, DSR, stabilité

tests/
  test_mean_reversion.py     — 12 tests RSI(2) (entry, exit, gap SL, anti-look-ahead)
  test_fee_model.py          — Tests fee model
  test_indicator_cache.py    — Tests cache indicateurs
  test_fast_backtest.py      — Tests engine trend following
  conftest.py                — Fixtures partagées

scripts/
  validate_rsi2_final.py     — Step 10 : validation portfolio final 5 ETFs [REFERENCE]
  validate_rsi2_spy.py       — Step 5  : RSI(2) sur SPY seul, comparaison fees
  validate_rsi2_portfolio.py — Step 6  : Portfolio 4 ETFs equity, IS/OOS
  validate_rsi2_robustness.py— Step 7  : Monte Carlo + sensibilité 48 combos
  validate_rsi2_expanded.py  — Step 9  : Univers élargi GLD/TLT/XLE/EFA
  validate_donchian_forex.py — Step 8  : REJECTED — Donchian forex PF OOS 0.50

config/
  production_params.yaml     — Params production figés pour Phase 2
  fee_models.yaml            — Modèles de frais (us_stocks, us_etfs_usd, forex, eu)
  assets_etf_us.yaml         — Univers ETFs equity US (SPY/QQQ/IWM/DIA)
  assets_forex.yaml          — 7 paires forex majeures (rejeté)

docs/
  PHASE1_RESULTS.md          — Résultats complets Phase 1, leçons apprises
```

## Conventions techniques

- Anti-look-ahead : signal sur [i-1], action sur open[i]
- Gap-aware exits : vérifier open vs SL avant le intraday
- Force-close fin de données : EXCLU de trade_pnls (biais)
- Méthodologie split IS/OOS : slicer le DataFrame avant l'engine (SMA recalculée proprement)
- t-test pour signification statistique MR (block bootstrap teste l'ordre, pas la sélection)
- `to_cache_arrays(df)` : fonction module-level dans `data/base_loader.py`
- `holding_days_out` : liste vide passée à `_simulate_mean_reversion` pour durées trades
- FeeModel : `entry_fee` inclus dans le PnL retourné par `_close_trend_position`
  → ne PAS soustraire à nouveau dans `capital +=` (bug corrigé en Phase 1)

## Phase 2 — Objectifs

Scanner quotidien de signaux RSI(2) :
- Vérifier RSI(2) sur 5 ETFs à la clôture (après 22h CET)
- Output : "BUY QQQ demain au open" / "SELL SPY à la clôture (SMA5 crossé)"
- Exécution manuelle sur Saxo via sous-compte USD
- Pas d'automatisation — signaux manuels uniquement
