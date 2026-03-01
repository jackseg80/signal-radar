# Audit Architecture scalp-radar — Pour inspiration signal-radar

## Vue d'ensemble

Scalp-radar est une plateforme de trading crypto futures production-grade avec backtesting avancé, WFO automatisé, paper trading et exécution live. L'architecture est **modulaire et extensible** : 17 stratégies (scalp 5m, swing 1h, grid/DCA), 3 moteurs de simulation, pipeline WFO 2-pass avec scoring composite, détection d'overfitting (Monte Carlo, DSR), et exécution live via API Bitget. Config-driven via YAML + Pydantic. 1000+ tests unitaires. Le tout fonctionne sur des futures perpétuels crypto avec leverage, funding rates et margin management.

---

## Pattern stratégie

### Classe abstraite `BaseStrategy`

Fichier : `backend/strategies/base.py` (143 lignes)

```python
class BaseStrategy(ABC):
    name: str = "base"

    @abstractmethod
    def evaluate(self, ctx: StrategyContext) -> StrategySignal | None:
        """Conditions d'entrée. Retourne un signal ou None."""

    @abstractmethod
    def check_exit(self, ctx: StrategyContext, position: OpenPosition) -> str | None:
        """Conditions de sortie anticipée (avant TP/SL)."""

    @abstractmethod
    def compute_indicators(self, candles_by_tf: dict[str, list[Candle]]) -> dict:
        """Pré-calcul de tous les indicateurs sur le dataset complet."""

    @abstractmethod
    def get_current_conditions(self, ctx: StrategyContext) -> list[dict]:
        """Conditions d'entrée avec état actuel (pour dashboard)."""

    @property
    @abstractmethod
    def min_candles(self) -> dict[str, int]:
        """Nombre minimum de bougies par timeframe."""
```

### Dataclasses clés

**StrategyContext** — passé à chaque bougie :
```python
@dataclass
class StrategyContext:
    symbol: str
    timestamp: datetime
    candles: dict[str, list[Candle]]           # Multi-TF
    indicators: dict[str, dict[str, Any]]      # Pré-calculés
    current_position: OpenPosition | None
    capital: float
    config: AppConfig
    extra_data: dict[str, Any] = {}            # funding_rate, OI, etc.
```

**StrategySignal** — retourné par `evaluate()` :
```python
@dataclass
class StrategySignal:
    direction: Direction                        # LONG | SHORT
    entry_price: float
    tp_price: float
    sl_price: float
    score: float                               # 0-1
    strength: SignalStrength                    # STRONG | MODERATE | WEAK
    market_regime: MarketRegime                # TRENDING_UP, RANGING, etc.
    signals_detail: dict[str, float] = {}      # Debug info
```

### Grid/DCA : sous-classe `BaseGridStrategy`

Pour les stratégies multi-positions (envelope_dca, grid_atr, etc.) :

```python
class BaseGridStrategy(BaseStrategy):
    @abstractmethod
    def compute_grid(self, ctx, grid_state) -> list[GridLevel]:
        """Calcule les niveaux d'entrée."""

    @abstractmethod
    def should_close_all(self, ctx, grid_state) -> bool:
        """Décide de fermer toutes les positions."""

    @abstractmethod
    def get_sl_price(self, grid_state) -> float:
    def get_tp_price(self, grid_state) -> float:
```

### Ajouter une nouvelle stratégie (8 étapes)

1. Créer `strategies/my_strategy.py` — hériter `BaseStrategy`
2. Ajouter config Pydantic dans `core/config.py` (MyStrategyConfig)
3. Enregistrer dans `strategies/factory.py` (mapping name → class)
4. Enregistrer dans `optimization/__init__.py` (STRATEGY_REGISTRY)
5. Ajouter param grid dans `config/param_grids.yaml`
6. Ajouter defaults dans `config/strategies.yaml`
7. Écrire les tests unitaires
8. Lancer WFO pour optimisation

**Verdict** : processus clair mais 8 fichiers à toucher = friction. Le double-registre (factory.py + optimization/__init__.py) est une source de bugs.

---

## Moteur de simulation

### Architecture 3 moteurs

| Moteur | Usage | Vitesse |
|--------|-------|---------|
| `BacktestEngine` | Single-position, event-driven | ~1x (référence) |
| `MultiPositionEngine` | Grid/DCA multi-positions | ~1x |
| `FastBacktestEngine` | WFO grid search vectorisé | ~100x |

### BacktestEngine — boucle principale

Fichier : `backend/backtesting/engine.py` (284 lignes)

```
Pour chaque bougie du TF principal :
  1. Mise à jour buffers multi-TF
  2. Si position ouverte :
     a. Check TP/SL (heuristique OHLC si les deux touchés sur même bougie)
     b. check_exit() si ni TP ni SL
  3. Si pas de position : evaluate() → signal → ouvrir
  4. Mise à jour equity curve
Force-close en fin de données
```

**Heuristique OHLC** quand TP et SL touchés sur la même bougie : utilise l'ordre O→H→L→C (ou O→L→H→C) pour déterminer lequel a été touché en premier.

### Position sizing — risk-based

```python
sl_distance_pct = abs(entry - sl) / entry
sl_real_cost = sl_distance_pct + taker_fee + slippage
risk_amount = capital * max_risk_per_trade      # 2% par défaut
notional = risk_amount / sl_real_cost
quantity = notional / entry_price
```

**Principe** : SL large → petite position, SL serré → grosse position. Le risque par trade est fixe en % du capital.

### Fee model

```python
@dataclass
class BacktestConfig:
    initial_capital: float = 10_000.0
    leverage: int = 15
    maker_fee: float = 0.0002      # 0.02%
    taker_fee: float = 0.0006      # 0.06%
    slippage_pct: float = 0.0005   # 0.05%
    max_risk_per_trade: float = 0.02
```

Fees appliquées : taker à l'entrée + taker à la sortie + slippage × multiplicateur volatilité.

---

## Pipeline de validation

### 5 étapes standardisées

```
1. Définition stratégie (YAML params)
   ↓
2. Backtest historique (BacktestEngine ou MultiPositionEngine)
   ↓
3. Walk-Forward Optimization (WFO)
   ├─ Split IS/OOS (fenêtres en trading days)
   ├─ Grid search 2-pass : Latin Hypercube coarse (150 combos) → fine autour du top 20
   ├─ Évaluation OOS avec meilleurs params
   ├─ Répéter pour chaque fenêtre
   └─ Agréger (consistency, régime analysis)
   ↓
4. Détection d'overfitting
   ├─ Monte Carlo block bootstrap (p-value)
   ├─ Deflated Sharpe Ratio (DSR, Bailey & Lopez de Prado 2014)
   ├─ Stabilité paramétrique (perturbation ±1 grid step)
   └─ Convergence cross-asset (coefficient de variation)
   ↓
5. Validation live
   ├─ Paper trading (Simulator)
   ├─ Monitoring Telegram
   └─ Production (executor mainnet)
```

### WFO 2-pass grid search

```python
# PASS 1 : Latin Hypercube sampling (coarse, 150 combos)
lhs_grid = _lhs_sample_grid(grid_values, n_samples=150)
results_1 = _run_grid_parallel(lhs_grid, ...)

# PASS 2 : Fine grid autour du top 20
top_20 = sorted(results_1, key=combo_score)[:20]
fine_grid = _fine_grid_around_top(top_20, grid_values)
results_2 = _run_grid_parallel(fine_grid, ...)
```

### Scoring composite (combo_score)

```python
score = oos_sharpe * consistency * min(trades/30, 1.0) * window_factor
```

Où `window_factor = n_windows / max_windows` pénalise les combos fine qui n'apparaissent que dans peu de fenêtres (correction biais de sélection, Sprint 38b).

### Grading final

```
A+ : Sharpe > 2.0 + significant + stable + high transfer ratio
A  : Sharpe > 1.5 + significant + stable
B+ : Sharpe > 1.0 + significant
B  : Sharpe > 0.75 + pas underpowered
C-F : en dessous
```

---

## Gestion des résultats

### Stockage SQLite async

Tables :
- `candles` — OHLCV brut
- `signals` — signaux stratégie
- `trades` — trades clôturés (entry/exit, PnL, fees, régime)
- `sessions` — sessions paper trading
- `optimization_results` — résultats WFO (JSON config + params)
- `portfolio_results` — backtests multi-asset

### Dataclasses résultats

```python
@dataclass
class BacktestResult:
    config: BacktestConfig
    strategy_name: str
    strategy_params: dict
    trades: list[TradeResult]
    equity_curve: list[float]
    final_capital: float

@dataclass
class BacktestMetrics:
    total_trades: int
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown_pct: float
    fee_drag_pct: float
    regime_stats: dict[str, dict]

@dataclass
class WFOResult:
    strategy_name: str
    symbol: str
    windows: list[WindowResult]
    avg_oos_sharpe: float
    consistency_rate: float
    recommended_params: dict
```

### Comparaison

Multi-stratégie sur un asset : comparer OOS Sharpe, consistency, DSR, grade final. Portfolio backtest avec contraintes de corrélation et limites de marge.

---

## Indicator cache

Fichier : `backend/optimization/indicator_cache.py`

```python
@dataclass
class IndicatorCache:
    n_candles: int
    opens: np.ndarray
    highs: np.ndarray
    lows: np.ndarray
    closes: np.ndarray
    volumes: np.ndarray

    rsi: dict[int, np.ndarray]                          # {period: array}
    vwap: np.ndarray
    atr_by_period: dict[int, np.ndarray]
    bb_upper: dict[tuple[int, float], np.ndarray]       # {(period, std): array}
    bb_lower: dict[tuple[int, float], np.ndarray]
    supertrend_direction: dict[tuple[int, float], np.ndarray]
    regime: np.ndarray                                   # int8 encoded
    # + filtres multi-TF alignés sur indices du TF principal
```

**Construction** : `build_cache(candles_by_tf, grid_values, strategy_name)` pré-calcule TOUS les indicateurs pour TOUTES les variantes de paramètres du grid. Le cache est réutilisé pour chaque combo → speedup ~100×.

**C'est exactement le pattern de signal-radar** (`indicator_cache.py` avec `build_cache(arrays, CACHE_GRID)`), mais scalp-radar va plus loin avec les indicateurs multi-TF et le regime encoding.

---

## Configuration

### 3 couches de config

| Couche | Source | Usage |
|--------|--------|-------|
| YAML | `config/strategies.yaml` | Defaults live + per_asset overrides |
| YAML | `config/param_grids.yaml` | Grille de paramètres pour WFO |
| Pydantic | `core/config.py` | Validation + merge + resolution |

### Exemple strategies.yaml

```yaml
vwap_rsi:
  enabled: false
  live_eligible: true
  timeframe: 5m
  rsi_period: 14
  rsi_long_threshold: 30
  per_asset:
    BTC/USDT:
      rsi_period: 12          # Override BTC
```

### Exemple param_grids.yaml

```yaml
vwap_rsi:
  default:
    rsi_period: [10, 14, 20]
    rsi_long_threshold: [25, 30, 35]
    tp_percent: [0.4, 0.6, 0.8, 1.0]
    sl_percent: [0.2, 0.3, 0.4, 0.5]
  BTC/USDT:
    sl_percent: [0.2, 0.3, 0.4]   # Custom per asset
```

### Resolution des paramètres

- **Production** : YAML → `_resolve_param()` (per_asset overrides)
- **Optimisation** : bypass YAML → injection directe des params du grid

**Bon pattern** : la même classe stratégie fonctionne en production et en optimisation, seule la source des params change.

---

## Tests

### Couverture : 1000+ tests

| Catégorie | Tests approx |
|-----------|-------------|
| Core (models, config, indicators) | ~100 |
| Backtesting (engine, metrics, stratégies) | ~200 |
| Optimization (WFO, overfitting, cache) | ~150 |
| Simulator/Arena | ~100 |
| Data engine, database, executor | ~300 |
| Risk management, position sizing | ~100 |

### Pattern de test

Stratégies testées avec des **stratégies factices** (AlwaysLongStrategy, AlwaysShortStrategy) pour isoler le moteur :

```python
class AlwaysLongStrategy(BaseStrategy):
    name = "test_always_long"
    def evaluate(self, ctx):
        return StrategySignal(direction=Direction.LONG, ...)
    def check_exit(self, ctx, position):
        return None

def test_backtest_tp_exit():
    candles = _make_candles([(100, 101, 99, 100), (101, 102, 100, 101)])
    engine = BacktestEngine(config, AlwaysLongStrategy())
    result = engine.run({"5m": candles})
    assert result.trades[0].exit_reason == "tp"
```

**Tests WFO intégration** : données réelles courtes, vérification que le pipeline complet tourne et produit des résultats cohérents.

---

## Points forts à reproduire

1. **BaseStrategy ABC** — interface claire, 5 méthodes abstraites, chaque stratégie = 1 fichier
2. **StrategyContext** — tout ce dont la stratégie a besoin dans un seul objet
3. **StrategySignal** — retour typé avec score, strength, regime → utile pour le ranking
4. **Indicator cache vectorisé** — pré-calcul numpy pour toutes les variantes de params → 100× speedup WFO
5. **Config YAML + Pydantic** — params en YAML, validation Python, per_asset overrides
6. **Pipeline WFO 2-pass** — Latin Hypercube coarse + fine autour du top 20 (efficace, pas brute force)
7. **4 méthodes overfitting** — Monte Carlo, DSR, stabilité paramétrique, convergence cross-asset
8. **Grading automatique** — A+ à F avec critères objectifs
9. **Séparation moteur/stratégie** — le moteur gère l'exécution, la stratégie fournit les signaux
10. **Tests avec stratégies factices** — isolation parfaite entre test du moteur et test de la logique

---

## Points faibles à éviter

1. **Double registre** — `strategies/factory.py` ET `optimization/__init__.py` enregistrent les stratégies séparément → désynchronisation possible. **Solution** : un seul registre.

2. **8 fichiers pour ajouter une stratégie** — trop de friction. **Solution** : auto-registration via décorateur ou scanning de module.

3. **3 moteurs de simulation** — `BacktestEngine`, `MultiPositionEngine`, `FastBacktestEngine` avec du code dupliqué. Pour signal-radar (daily, single-position seulement), un seul moteur suffit.

4. **Config 1500+ lignes** — `core/config.py` est un monolithe Pydantic. **Solution** : une config par stratégie, chargée séparément.

5. **`extra_data: dict[str, Any]`** — pas de type safety pour funding_rate, OI, etc. **Solution** : dataclass typée.

6. **`StrategyContext.config = None` en backtest** — contourne le type system. **Solution** : Optional explicite ou contexte séparé.

7. **ProcessPoolExecutor instable** — problèmes documentés (segfaults, timeouts). Pour signal-radar avec backtests daily (~250 lignes par an), la parallélisation est peu critique.

8. **param_grids.yaml pas synchronisé** avec les configs Pydantic — si on ajoute un param à la config, on peut oublier le grid. **Solution** : générer les defaults du grid depuis le modèle Pydantic.

---

## Éléments spécifiques crypto (non applicables)

| Élément | Description | Pourquoi pas applicable |
|---------|------------|------------------------|
| Leverage | 1-20× sur futures perpétuels | signal-radar = cash only, leverage=1 |
| Funding rates | Coût des perpétuels toutes les 8h | Pas de perpetuals sur actions US |
| Maker/taker fees | Binance/Bitget fee structure | Saxo = commission fixe + spread |
| Margin ratio | 70% max margin kill switch | Cash account, pas de marge |
| Open Interest | Détection liquidations cascades | Pas d'OI sur actions individuelles |
| Grid/DCA multi-position | 6 stratégies grid spécialisées | RSI(2) = single position, long-only |
| Resampling 4h depuis 1h | Certains exchanges n'ont pas le TF | yfinance a daily nativement |
| Short selling | Direction.SHORT dans StrategySignal | signal-radar = long-only |

---

## Recommandations pour signal-radar

### Ce qu'on reprend

1. **`BaseStrategy` ABC** adapté au daily :
   ```python
   class BaseStrategy(ABC):
       name: str
       @abstractmethod
       def generate_signals(self, cache: IndicatorCache, config: BacktestConfig) -> SignalArray
       @abstractmethod
       def default_params(self) -> dict
       @abstractmethod
       def param_grid(self) -> dict[str, list]
   ```
   Plus simple que scalp-radar : pas de multi-TF, pas de StrategyContext event-driven, pas de check_exit séparé (la stratégie retourne directement les signaux entry+exit sur tout le dataset).

2. **Moteur unique** — un seul `simulate(signals, cache, config)` qui gère : position sizing (whole shares + fractional), fees via FeeModel, gap-aware exits, anti-look-ahead, force-close.

3. **Indicator cache** — on a déjà `build_cache()`, l'étendre pour supporter les grids de params de chaque stratégie.

4. **Pipeline standardisé** — `validate(strategy, universe, config)` → IS/OOS → robustesse 48 combos → sous-périodes → t-test → rapport avec verdict.

5. **Config YAML** — params par stratégie, fee models, univers d'assets en YAML (déjà en place).

6. **Résultats structurés** — dataclasses `BacktestResult`, `ValidationResult`, `StrategyReport` avec export JSON.

### Ce qu'on ne reprend PAS

1. **Multi-position / grid** — pas nécessaire pour RSI(2) long-only
2. **Event-driven loop** — overkill pour daily. Vectorisé suffit.
3. **3 moteurs** — un seul, performant
4. **Double registre** — un seul registre avec auto-discovery
5. **Pydantic monolithe** — configs simples par stratégie
6. **SQLite database** — trop lourd pour 3 assets. JSON/CSV + dataclasses suffisent pour maintenant
7. **Funding, leverage, margin** — pas applicable stocks

### Estimation de complexité

| Composant | Effort | Lignes estimées |
|-----------|--------|-----------------|
| `BaseStrategy` + registre | 1 jour | ~100 |
| Moteur générique `simulate()` | 2 jours | ~200 (refactor des 2 existants) |
| Migration RSI(2) MR | 0.5 jour | ~80 |
| Migration Donchian TF | 0.5 jour | ~80 |
| Pipeline `validate()` | 2 jours | ~300 |
| Tests | 1 jour | ~200 |
| **Total** | **~7 jours** | **~960 lignes** |
