"""Rapport de confiance pour signal-radar.

Grading A-F, métriques OOS, haircut survivorship bias.
Adapté depuis scalp-radar — suppression de tout le coupling crypto/Bitget/DB.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from loguru import logger


# ─── Dataclasses ───────────────────────────────────────────────────────────


@dataclass
class GradeResult:
    """Résultat du grading avec pénalité shallow."""

    grade: str        # Lettre finale (A-F) après pénalité + caps
    score: float      # Score final après pénalité shallow
    is_shallow: bool  # True si n_windows < 24
    raw_score: float  # Score brut avant pénalité


# ─── Grading V2 — Métriques ────────────────────────────────────────────────


def compute_win_rate_oos(windows: list) -> float:
    """Pourcentage de fenêtres OOS avec return > 0%."""
    returns = [
        w.oos_net_return_pct if hasattr(w, "oos_net_return_pct")
        else w.get("oos_net_return_pct", 0)
        for w in windows
    ]
    if not returns:
        return 0.0
    return sum(1 for r in returns if r > 0) / len(returns)


def compute_tail_ratio(windows: list) -> float:
    """Ratio pertes sévères (<-20%) / gains. 0=aucune catastrophe, 1=mangent tous les gains."""
    returns = [
        w.oos_net_return_pct if hasattr(w, "oos_net_return_pct")
        else w.get("oos_net_return_pct", 0)
        for w in windows
    ]
    pos_sum = sum(r for r in returns if r > 0)
    neg_bad = sum(r for r in returns if r < -20)
    if pos_sum <= 0:
        return 1.0
    return abs(neg_bad) / pos_sum


# ─── Grading V2 — Scoring ─────────────────────────────────────────────────


def compute_grade(
    oos_sharpe: float,
    win_rate_oos: float,
    tail_ratio: float,
    dsr: float,
    param_stability: float,
    consistency: float = 1.0,
    total_trades: int = 0,
    n_windows: int | None = None,
) -> GradeResult:
    """Calcule le grade A-F et le score numérique 0-100 (V2 — scoring continu).

    Barème (100 pts) :
        Sharpe OOS      20 pts  (min(20, oos_sharpe × 3.5))
        Win rate OOS    20 pts  (win_rate_oos × 20)
        Tail risk       15 pts  (max(0, 15 × (1 - tail_ratio × 1.5)))
        DSR             15 pts  (dsr × 15)
        Stabilité       15 pts  (param_stability × 15)
        Consistance     10 pts  (consistency × 10)
        Monte Carlo      5 pts  (forfait)

    Pénalité shallow (< 24 fenêtres) : (24 - n_windows) × 0.8 pts soustraits.
    Garde-fou trades : < 30 → plafond C, < 50 → plafond B.
    """
    sharpe_score = min(20, oos_sharpe * 3.5)
    win_rate_score = win_rate_oos * 20
    tail_score = max(0, 15 * (1 - tail_ratio * 1.5))
    dsr_score = dsr * 15
    stability_score = param_stability * 15
    consistency_score = consistency * 10
    mc_score = 5

    raw_score = (
        sharpe_score + win_rate_score + tail_score
        + dsr_score + stability_score + consistency_score + mc_score
    )

    shallow_penalty = 0.0
    if n_windows is not None and n_windows < 24:
        shallow_penalty = max(0, (24 - n_windows) * 0.8)
    score = raw_score - shallow_penalty
    is_shallow = n_windows is not None and n_windows < 24

    if score >= 85:
        grade = "A"
    elif score >= 70:
        grade = "B"
    elif score >= 55:
        grade = "C"
    elif score >= 40:
        grade = "D"
    else:
        grade = "F"

    _GRADE_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3, "F": 4}
    if total_trades > 0:
        if total_trades < 30:
            max_grade = "C"
            if _GRADE_ORDER[grade] < _GRADE_ORDER[max_grade]:
                grade = max_grade
        elif total_trades < 50:
            max_grade = "B"
            if _GRADE_ORDER[grade] < _GRADE_ORDER[max_grade]:
                grade = max_grade

    logger.info(
        "compute_grade: {} ({:.1f}/100{}, trades={}) — "
        "sharpe={:.2f}→{:.1f}/20, wr={:.2f}→{:.1f}/20, "
        "tail={:.2f}→{:.1f}/15, dsr={:.2f}→{:.1f}/15, "
        "stab={:.2f}→{:.1f}/15, cons={:.2f}→{:.1f}/10, mc={}/5",
        grade, score,
        f" raw={raw_score:.1f} shallow=-{shallow_penalty:.1f} n_win={n_windows}"
        if shallow_penalty > 0 else "",
        total_trades,
        oos_sharpe, sharpe_score,
        win_rate_oos, win_rate_score,
        tail_ratio, tail_score,
        dsr, dsr_score,
        param_stability, stability_score,
        consistency, consistency_score,
        mc_score,
    )

    return GradeResult(grade=grade, score=score, is_shallow=is_shallow, raw_score=raw_score)


def grade_with_haircut(
    oos_sharpe: float,
    win_rate_oos: float,
    tail_ratio: float,
    dsr: float,
    param_stability: float,
    consistency: float = 1.0,
    total_trades: int = 0,
    n_windows: int | None = None,
    haircut: float = 0.15,
) -> GradeResult:
    """Grading avec haircut survivorship bias sur le Sharpe OOS.

    Soustrait `haircut` au Sharpe OOS avant grading pour compenser le biais
    de sélection des actifs survivants (actions US = survivorship bias ~0.15 Sharpe).
    """
    adjusted_sharpe = max(0.0, oos_sharpe - haircut)
    return compute_grade(
        oos_sharpe=adjusted_sharpe,
        win_rate_oos=win_rate_oos,
        tail_ratio=tail_ratio,
        dsr=dsr,
        param_stability=param_stability,
        consistency=consistency,
        total_trades=total_trades,
        n_windows=n_windows,
    )
