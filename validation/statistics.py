"""Tests statistiques pour la validation de stratégies."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats


@dataclass
class TTestResult:
    """Résultat du t-test one-sample (H0: mean return = 0)."""

    symbol: str
    n_trades: int
    mean_return_pct: float
    t_stat: float
    p_value: float    # one-tailed (mean > 0)
    significant: bool
    label: str        # "OUI (p<0.05)" / "MARGINAL (p<0.10)" / "NON"


def run_ttest(
    returns: list[float],
    symbol: str = "",
    alpha: float = 0.10,
) -> TTestResult:
    """T-test one-tailed : mean(returns) > 0.

    Port de validate_rsi2_stocks_robustness.py lignes 420-443.
    Utilise scipy.stats.ttest_1samp, conversion one-tailed.

    Args:
        returns: Liste des returns par trade (pnl/capital_allocated)
        symbol: Nom du symbole (pour le rapport)
        alpha: Seuil de significativité

    Returns:
        TTestResult avec t_stat, p_value one-tailed, verdict
    """
    n_trades = len(returns)
    if n_trades < 2:
        return TTestResult(
            symbol=symbol,
            n_trades=n_trades,
            mean_return_pct=returns[0] * 100 if n_trades == 1 else 0.0,
            t_stat=0.0,
            p_value=1.0,
            significant=False,
            label="NON",
        )

    arr = np.array(returns)
    mean_ret = float(arr.mean())
    t_stat, p_two = stats.ttest_1samp(arr, 0.0)

    # Conversion one-tailed (H1: mean > 0)
    p_value = float(p_two / 2) if t_stat > 0 else 1.0

    # Label
    if p_value < 0.05:
        label = "OUI (p<0.05)"
    elif p_value < 0.10:
        label = "MARGINAL (p<0.10)"
    else:
        label = "NON"

    return TTestResult(
        symbol=symbol,
        n_trades=n_trades,
        mean_return_pct=mean_ret * 100,
        t_stat=float(t_stat),
        p_value=p_value,
        significant=p_value < alpha,
        label=label,
    )
