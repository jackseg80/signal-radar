"""Walk-Forward Optimizer pour signal-radar.

Optimisation par fenêtres glissantes IS→OOS avec grid search en 2 passes
(coarse Latin Hypercube → fine autour du top 20).
Adapté depuis scalp-radar — suppression du coupling crypto/DB/exchange.
Prend un DataFrame pré-chargé au lieu de requêter une DB.
"""

from __future__ import annotations

import itertools
import json
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from loguru import logger

from engine.backtest_config import BacktestConfig
from engine.fast_backtest import ISResult, run_backtest_from_cache
from engine.indicator_cache import IndicatorCache, build_cache


# ─── Dataclasses résultat ──────────────────────────────────────────────────


@dataclass
class WindowResult:
    """Résultat d'une fenêtre IS+OOS."""

    window_index: int
    is_start: datetime
    is_end: datetime
    oos_start: datetime
    oos_end: datetime
    best_params: dict[str, Any]
    is_sharpe: float
    is_net_return_pct: float
    is_profit_factor: float
    is_trades: int
    oos_sharpe: float
    oos_net_return_pct: float
    oos_profit_factor: float
    oos_trades: int
    top_n_params: list[dict] = field(default_factory=list)


@dataclass
class WFOResult:
    """Résultat complet du walk-forward."""

    strategy_name: str
    symbol: str
    windows: list[WindowResult]
    avg_is_sharpe: float
    avg_oos_sharpe: float
    oos_is_ratio: float
    consistency_rate: float
    recommended_params: dict[str, Any]
    n_distinct_combos: int
    combo_results: list[dict[str, Any]] = field(default_factory=list)


# ─── Helpers ────────────────────────────────────────────────────────────────


def combo_score(
    oos_sharpe: float,
    consistency: float,
    total_trades: int,
    n_windows: int | None = None,
    max_windows: int | None = None,
) -> float:
    """Score composite pour sélectionner le meilleur combo WFO.

    Favorise les combos à haute consistance ET volume de trades.
    window_factor pénalise les combos évalués sur peu de fenêtres OOS.
    """
    sharpe = max(oos_sharpe, 0.0)
    trade_factor = min(1.0, total_trades / 100)
    if n_windows is not None and max_windows is not None and max_windows > 0:
        window_factor = min(1.0, n_windows / max_windows)
    else:
        window_factor = 1.0
    return sharpe * (0.4 + 0.6 * consistency) * trade_factor * window_factor


def _load_param_grids(config_path: str = "config/param_grids.yaml") -> dict[str, Any]:
    """Charge les grilles de paramètres."""
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _build_grid(
    strategy_grids: dict[str, Any], symbol: str
) -> list[dict[str, Any]]:
    """Construit la grille complète pour un (strategy, symbol).

    Merge default + overrides spécifiques au symbol.
    """
    default = strategy_grids.get("default", {})
    overrides = strategy_grids.get(symbol, {})
    merged = {**default, **overrides}

    if not merged:
        return []

    keys = sorted(merged.keys())
    values = [merged[k] for k in keys]
    combos = list(itertools.product(*values))
    return [dict(zip(keys, combo)) for combo in combos]


def _latin_hypercube_sample(
    grid: list[dict[str, Any]], n_samples: int, seed: int = 42
) -> list[dict[str, Any]]:
    """Sous-échantillonnage stratifié de la grille (approximation LHS)."""
    if len(grid) <= n_samples:
        return grid

    rng = np.random.default_rng(seed)
    indices = rng.choice(len(grid), size=n_samples, replace=False)
    return [grid[i] for i in sorted(indices)]


def _to_hashable(v: Any) -> Any:
    if isinstance(v, list):
        return tuple(v)
    return v


def _from_hashable(v: Any) -> Any:
    if isinstance(v, tuple):
        return list(v)
    return v


def _fine_grid_around_top(
    top_params: list[dict[str, Any]],
    full_grid_values: dict[str, list],
) -> list[dict[str, Any]]:
    """Génère un grid fin autour des top N combinaisons.

    Pour chaque paramètre de chaque top combo, explore ±1 step dans le grid.
    """
    fine_combos: set[tuple] = set()
    sorted_keys = sorted(full_grid_values.keys())

    for params in top_params:
        for key in sorted_keys:
            values = full_grid_values[key]
            current_val = params.get(key)
            if current_val not in values:
                continue
            idx = values.index(current_val)
            neighbors: set = set()
            for offset in [-1, 0, 1]:
                ni = idx + offset
                if 0 <= ni < len(values):
                    neighbors.add(_to_hashable(values[ni]))

            for neighbor_val in neighbors:
                combo = dict(params)
                combo[key] = _from_hashable(neighbor_val)
                combo_tuple = tuple(_to_hashable(combo[k]) for k in sorted_keys)
                fine_combos.add(combo_tuple)

    return [
        dict(zip(sorted_keys, [_from_hashable(v) for v in combo]))
        for combo in fine_combos
    ]


def _median_params(
    all_best_params: list[dict[str, Any]],
    grid_values: dict[str, list],
) -> dict[str, Any]:
    """Calcule la médiane des paramètres et snappe à la valeur du grid la plus proche."""
    if not all_best_params:
        return {}

    result: dict[str, Any] = {}
    keys = all_best_params[0].keys()

    for key in keys:
        values = [p[key] for p in all_best_params if key in p]
        if not values:
            continue

        if all(isinstance(v, (int, float)) for v in values):
            median_val = float(np.median(values))
            if key in grid_values and grid_values[key]:
                grid_vals = sorted(grid_values[key])
                closest = min(grid_vals, key=lambda x: abs(x - median_val))
                if all(isinstance(v, int) for v in values):
                    result[key] = int(closest)
                else:
                    result[key] = closest
            else:
                result[key] = median_val
        else:
            counts = Counter(_to_hashable(v) for v in values)
            result[key] = _from_hashable(counts.most_common(1)[0][0])

    return result


def _build_windows_from_index(
    trading_dates: pd.DatetimeIndex,
    is_bars: int,
    oos_bars: int,
    step_bars: int,
    embargo_bars: int = 0,
) -> list[tuple[datetime, datetime, datetime, datetime]]:
    """Construit les fenêtres IS+OOS en JOURS DE TRADING (barres du DataFrame).

    is_bars, oos_bars, step_bars comptent en lignes du DataFrame, pas en jours
    calendaires. Avec des données daily stock, 252 barres = 1 an exactement.
    """
    n = len(trading_dates)
    windows = []
    cursor = 0

    while True:
        is_start_idx = cursor
        is_end_idx = is_start_idx + is_bars
        oos_start_idx = is_end_idx + embargo_bars
        oos_end_idx = oos_start_idx + oos_bars

        if oos_end_idx > n:
            break

        windows.append((
            trading_dates[is_start_idx].to_pydatetime(),
            trading_dates[is_end_idx - 1].to_pydatetime(),      # dernière barre IS
            trading_dates[oos_start_idx].to_pydatetime(),
            trading_dates[oos_end_idx - 1].to_pydatetime(),      # dernière barre OOS
        ))
        cursor += step_bars

    return windows


def _slice_df(df: pd.DataFrame, start: datetime, end: datetime) -> pd.DataFrame:
    """Extrait les rows dans [start, end] (bornes incluses)."""
    mask = (df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))
    return df.loc[mask]


def _df_to_arrays(df: pd.DataFrame) -> dict[str, np.ndarray]:
    """Convertit un DataFrame OHLCV en dict de numpy arrays.

    Utilise Adj_Close pour closes (cohérent avec to_cache_arrays).
    Après le fix split-adjust dans yahoo_loader, O/H/L sont déjà ajustés
    et Close == Adj_Close, mais on garde le fallback par sécurité.
    """
    close_col = "Adj_Close" if "Adj_Close" in df.columns else "Close"
    return {
        "opens": df["Open"].values.astype(np.float64),
        "highs": df["High"].values.astype(np.float64),
        "lows": df["Low"].values.astype(np.float64),
        "closes": df[close_col].values.astype(np.float64),
        "volumes": df["Volume"].values.astype(np.float64),
    }


# ─── Worker pour ProcessPoolExecutor ──────────────────────────────────────


def _run_single_combo(args: tuple) -> ISResult:
    """Worker function pour ProcessPoolExecutor."""
    params, arrays, param_grid_values, strategy_name, config_dict = args
    from engine.backtest_config import BacktestConfig
    from engine.fee_model import FeeModel
    from engine.indicator_cache import build_cache

    fee_dict = config_dict.pop("fee_model", {})
    fee_model = FeeModel(**fee_dict) if fee_dict else FeeModel()
    config = BacktestConfig(**config_dict, fee_model=fee_model)

    cache = build_cache(arrays, param_grid_values)
    return run_backtest_from_cache(params, cache, config)


# ─── WalkForwardOptimizer ──────────────────────────────────────────────────


class WalkForwardOptimizer:
    """Optimiseur Walk-Forward avec grid search en 2 passes.

    Prend un DataFrame pré-chargé (pas de DB).
    max_workers: int | None = None → séquentiel. int > 0 → ProcessPoolExecutor.
    """

    def __init__(self, config_dir: str = "config") -> None:
        self._config_dir = config_dir
        self._grids = _load_param_grids(str(Path(config_dir) / "param_grids.yaml"))

    def optimize(
        self,
        strategy_name: str,
        symbol: str,
        df: pd.DataFrame,
        config: BacktestConfig,
        sides: list[str] | None = None,
        max_workers: int | None = None,
        params_override: dict | None = None,
    ) -> WFOResult:
        """Walk-forward optimization complète.

        Args:
            strategy_name: Nom de la stratégie (ex: "signal_donchian")
            symbol: Symbole (ex: "AAPL")
            df: DataFrame OHLCV avec DatetimeIndex
            config: BacktestConfig
            sides: ["long"], ["short"], ou ["long", "short"]
            max_workers: None = séquentiel, int = parallèle
            params_override: Sous-grille custom fusionnée dans "default"
        """
        # WFO config from param_grids.yaml
        strategy_grids_raw = self._grids.get(strategy_name, {})
        wfo_config = strategy_grids_raw.get("wfo", {})
        is_days = wfo_config.get("is_days", 756)
        oos_days = wfo_config.get("oos_days", 252)
        step_days = wfo_config.get("step_days", 126)
        embargo_days = wfo_config.get("embargo_days", 1)

        # Build windows from actual trading dates (not calendar days)
        windows = _build_windows_from_index(
            df.index, is_days, oos_days, step_days,
            embargo_bars=embargo_days,
        )
        logger.info(
            "{} fenêtres WFO pour {} {} (IS={}bars OOS={}bars step={}bars)",
            len(windows), strategy_name, symbol, is_days, oos_days, step_days,
        )

        if not windows:
            raise ValueError("Pas assez de données pour au moins une fenêtre WFO")

        # Build grid
        strategy_grids = dict(strategy_grids_raw)
        if params_override:
            merged_default = {**strategy_grids.get("default", {}), **params_override}
            strategy_grids = {**strategy_grids, "default": merged_default}

        full_grid = _build_grid(strategy_grids, symbol)
        grid_values = {**strategy_grids.get("default", {}), **strategy_grids.get(symbol, {})}

        # Inject sides into every combo
        if sides:
            for combo in full_grid:
                combo["sides"] = sides

        logger.info("Grid complet : {} combinaisons", len(full_grid))

        # 2-pass grid search
        coarse_max = 200
        if len(full_grid) > coarse_max:
            coarse_grid = _latin_hypercube_sample(full_grid, coarse_max)
            logger.info("Coarse pass : {} combinaisons (LHS)", len(coarse_grid))
        else:
            coarse_grid = full_grid

        n_distinct_combos = len(coarse_grid)

        # Per-window optimization
        window_results: list[WindowResult] = []
        combo_accumulator: dict[str, list[dict]] = {}

        t0 = time.time()

        for w_idx, (is_start, is_end, oos_start, oos_end) in enumerate(windows):
            logger.info(
                "Fenêtre {}/{} : IS {} → {} | OOS {} → {}",
                w_idx + 1, len(windows),
                is_start.strftime("%Y-%m-%d"), is_end.strftime("%Y-%m-%d"),
                oos_start.strftime("%Y-%m-%d"), oos_end.strftime("%Y-%m-%d"),
            )

            # Slice IS
            is_df = _slice_df(df, is_start, is_end)
            if len(is_df) < 50:
                logger.warning("Fenêtre {} : trop peu de données IS ({}), skip", w_idx, len(is_df))
                continue

            is_arrays = _df_to_arrays(is_df)

            # Build cache for IS (pre-compute all indicators)
            is_cache = build_cache(is_arrays, grid_values)

            # --- Coarse pass ---
            coarse_results = self._run_grid(coarse_grid, is_cache, config)
            coarse_results.sort(key=lambda r: r[1], reverse=True)
            top_20 = coarse_results[:20]

            # --- Fine pass ---
            top_20_params = [r[0] for r in top_20]
            fine_grid = _fine_grid_around_top(top_20_params, grid_values)
            if sides:
                for combo in fine_grid:
                    combo["sides"] = sides
            n_distinct_combos = max(n_distinct_combos, len(coarse_grid) + len(fine_grid))

            if fine_grid:
                fine_results = self._run_grid(fine_grid, is_cache, config)
                all_is_results = coarse_results + fine_results
            else:
                all_is_results = coarse_results

            all_is_results.sort(key=lambda r: r[1], reverse=True)
            best_is = all_is_results[0]
            best_params = best_is[0]

            top_5 = [{"params": r[0], "sharpe": r[1]} for r in all_is_results[:5]]

            logger.info(
                "  IS best: sharpe={:.3f} ret={:+.1f}% trades={} | IS bars={}",
                best_is[1], best_is[2], best_is[4], len(is_df),
            )

            # --- OOS ---
            oos_df = _slice_df(df, oos_start, oos_end)
            if len(oos_df) < 20:
                logger.warning("Fenêtre {} : trop peu de données OOS ({}), skip", w_idx, len(oos_df))
                continue

            oos_arrays = _df_to_arrays(oos_df)
            oos_cache = build_cache(oos_arrays, grid_values)

            # OOS with best IS params
            oos_result = run_backtest_from_cache(best_params, oos_cache, config)

            logger.info(
                "  OOS: sharpe={:.3f} ret={:+.1f}% trades={} | OOS bars={}",
                oos_result[1], oos_result[2], oos_result[4], len(oos_df),
            )

            # Accumulate combo results
            seen_keys = set()
            unique_params = []
            for r in all_is_results:
                key = json.dumps(r[0], sort_keys=True)
                if key not in seen_keys:
                    seen_keys.add(key)
                    unique_params.append(r[0])

            oos_batch = self._run_grid(unique_params, oos_cache, config)
            is_by_key = {json.dumps(r[0], sort_keys=True): r for r in all_is_results}
            oos_by_key = {json.dumps(r[0], sort_keys=True): r for r in oos_batch}

            for params_key in is_by_key:
                is_r = is_by_key[params_key]
                oos_r = oos_by_key.get(params_key)
                if params_key not in combo_accumulator:
                    combo_accumulator[params_key] = []
                combo_accumulator[params_key].append({
                    "window_index": w_idx,
                    "is_sharpe": is_r[1],
                    "oos_sharpe": oos_r[1] if oos_r else 0.0,
                    "oos_trades": oos_r[4] if oos_r else 0,
                    "oos_net_return_pct": oos_r[2] if oos_r else 0.0,
                })

            wr = WindowResult(
                window_index=w_idx,
                is_start=is_start, is_end=is_end,
                oos_start=oos_start, oos_end=oos_end,
                best_params=best_params,
                is_sharpe=best_is[1],
                is_net_return_pct=best_is[2],
                is_profit_factor=best_is[3],
                is_trades=best_is[4],
                oos_sharpe=oos_result[1],
                oos_net_return_pct=oos_result[2],
                oos_profit_factor=oos_result[3],
                oos_trades=oos_result[4],
                top_n_params=top_5,
            )
            window_results.append(wr)

        elapsed = time.time() - t0
        logger.info("WFO terminé en {:.1f}s — {} fenêtres valides", elapsed, len(window_results))

        if not window_results:
            raise ValueError("Aucune fenêtre WFO valide")

        # Aggregate combo results
        max_windows = len(window_results)
        combo_results = []
        for params_key, window_data in combo_accumulator.items():
            oos_sharpes = [w["oos_sharpe"] for w in window_data]
            avg_oos = float(np.mean(oos_sharpes)) if oos_sharpes else 0.0
            cons = sum(1 for s in oos_sharpes if s > 0) / len(oos_sharpes) if oos_sharpes else 0.0
            total_trades = sum(w["oos_trades"] for w in window_data)
            score = combo_score(avg_oos, cons, total_trades,
                                n_windows=len(window_data), max_windows=max_windows)
            combo_results.append({
                "params": json.loads(params_key),
                "avg_oos_sharpe": avg_oos,
                "consistency": cons,
                "total_oos_trades": total_trades,
                "n_windows": len(window_data),
                "score": score,
            })

        combo_results.sort(key=lambda c: c["score"], reverse=True)
        if combo_results:
            combo_results[0]["is_best"] = True

        # Averages
        avg_is = float(np.mean([w.is_sharpe for w in window_results]))
        avg_oos = float(np.mean([w.oos_sharpe for w in window_results]))
        oos_is_ratio = avg_oos / avg_is if avg_is > 0 else 0.0
        consistency = sum(1 for w in window_results if w.oos_sharpe > 0) / len(window_results)

        # Recommended params = median of all window best params
        all_best_params = [w.best_params for w in window_results]
        recommended = _median_params(all_best_params, grid_values)
        if sides:
            recommended["sides"] = sides

        return WFOResult(
            strategy_name=strategy_name,
            symbol=symbol,
            windows=window_results,
            avg_is_sharpe=avg_is,
            avg_oos_sharpe=avg_oos,
            oos_is_ratio=oos_is_ratio,
            consistency_rate=consistency,
            recommended_params=recommended,
            n_distinct_combos=n_distinct_combos,
            combo_results=combo_results,
        )

    def _run_grid(
        self,
        grid: list[dict[str, Any]],
        cache: IndicatorCache,
        config: BacktestConfig,
    ) -> list[ISResult]:
        """Exécute le grid sur un cache (séquentiel)."""
        results = []
        for params in grid:
            try:
                result = run_backtest_from_cache(params, cache, config)
                results.append(result)
            except Exception as exc:
                logger.debug("Backtest échoué pour {} : {}", params, exc)
        return results
