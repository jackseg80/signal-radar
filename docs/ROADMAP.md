# Signal-Radar — Roadmap

## Phase 1 — Backtesting Engine & Strategy Validation ✅ COMPLETE
## Phase 2 — Daily Signal Scanner & Deployment ✅ COMPLETE
## Phase 3 — Backtesting Framework ✅ COMPLETE
## Infra Scale-Up ✅ COMPLETE

---

## Phase 4 — Live Validation ✅ COMPLETE

**Période :** Mars 2026
**Objectif :** Valider la stratégie en conditions réelles et tracker le slippage.

### Réalisations
- ✅ Migration SQLite pour le tracking des positions.
- ✅ Système de "Log Real Trade" pour comparer Paper vs Live.
- ✅ Journal de trading unifié avec notes et forensics.

---

## Phase 5 — Dashboard Web & UI/UX ✅ COMPLETE

**Période :** Mars 2026
**Objectif :** Interface moderne pour remplacer le CLI et les fichiers CSV.

### Réalisations
- ✅ Dashboard React + Tailwind v4 + Recharts.
- ✅ Matrice de Confiance (vue croisée assets/stratégies).
- ✅ Explorateur de Backtests (heatmap de robustesse).
- ✅ **Asset Detail Panel (Nouveau)** : Analyse OOS 2014-2025 détaillée par actif avec courbes d'equity et drawdown synchronisées.

---

## Phase 6 — Quantitative Forensic & Stability ✅ EN COURS

**Période :** Mars 2026
**Objectif :** Approfondir la validation statistique et la stabilité des outils.

### Steps en cours / réalisés
- ✅ **Portail de détail par actif** : Visualisation trade-par-trade sur 10 ans OOS.
- ✅ **Synchronisation Equity/Drawdown** : Analyse visuelle des régimes de marché (COVID, Rate Hikes).
- ✅ **Stabilisation Dashboard & Live** : Correction du formulaire de clôture (LiveTradeForm) et des imports UI.
- ✅ **Robustesse des Tests** : Migration des tests DB vers des timestamps dynamiques pour éviter les régressions liées aux filtres temporels.
- 📋 **Refactorisation Dette Technique** : Centralisation de la logique de stratégie et composant BaseModal (Prochaine étape).
- 📋 **Extraction Configuration** : Déplacer les événements de marché hardcodés vers une config globale.

---

## Phase 7 — Scale Up & Automatisation 📋 VISION LONG TERME

- API Saxo / IBKR (exécution automatique).
- Position sizing dynamique (Kelly / vol targeting).
- Exploration des marchés européens et Small Caps.

---

## Historique des décisions clés

| Date | Décision | Raison |
|------|----------|--------|
| Mars 2026 | Implémenter React Portals pour les modals | Résoudre les conflits de dimensions Recharts et de z-index parents. |
| Mars 2026 | Ajouter endpoint `/api/backtest/equity-curve` | Permettre l'analyse visuelle granulaire sans recharger toute la DB. |
| Mars 2026 | Harmoniser UI Dashboard et Backtest | Réduire la charge cognitive et préparer la factorisation BaseModal. |
| Mars 2026 | Fix LiveTradeForm (Close mode) | Permettre la clôture manuelle correcte des positions réelles avec prix de sortie dynamique. |
| Mars 2026 | Dynamic timestamps dans les tests DB | Assurer que les tests de régression passent indépendamment de la date actuelle (filtre 7 jours). |
