"""Rapport de validation et verdict."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from enum import Enum

from engine.types import BacktestResult
from validation.robustness import RobustnessResult
from validation.statistics import TTestResult
from validation.sub_periods import SubPeriodResult


class Verdict(Enum):
    """Verdict de validation pour un asset."""

    VALIDATED = "VALIDATED"
    CONDITIONAL = "CONDITIONAL"
    REJECTED = "REJECTED"


@dataclass
class AssetValidation:
    """Validation complète pour un asset."""

    symbol: str
    oos_result: BacktestResult
    robustness: RobustnessResult
    sub_periods: SubPeriodResult
    ttest: TTestResult
    verdict: Verdict


@dataclass
class ValidationReport:
    """Rapport complet de validation d'une stratégie."""

    strategy_name: str
    assets: list[AssetValidation] = field(default_factory=list)
    pooled_ttest: TTestResult | None = None
    universe_name: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))

    @property
    def validated(self) -> list[str]:
        """Symboles validés."""
        return [a.symbol for a in self.assets if a.verdict == Verdict.VALIDATED]

    @property
    def conditional(self) -> list[str]:
        """Symboles conditionnels."""
        return [a.symbol for a in self.assets if a.verdict == Verdict.CONDITIONAL]

    @property
    def rejected(self) -> list[str]:
        """Symboles rejetés."""
        return [a.symbol for a in self.assets if a.verdict == Verdict.REJECTED]


def determine_verdict(
    robustness: RobustnessResult,
    sub_periods: SubPeriodResult,
    ttest: TTestResult,
    *,
    conditional_p_max: float = 0.15,
) -> Verdict:
    """Détermine le verdict pour un asset.

    VALIDATED  : robust AND stable AND significant
    CONDITIONAL: robust AND (stable OR significant)
    REJECTED   : sinon

    Port de validate_rsi2_stocks_robustness.py lignes 487-501.
    """
    if robustness.robust and sub_periods.stable and ttest.significant:
        return Verdict.VALIDATED
    if robustness.robust and (sub_periods.stable or ttest.significant):
        return Verdict.CONDITIONAL
    return Verdict.REJECTED


def print_report(report: ValidationReport) -> None:
    """Affiche le rapport formaté en console."""
    sep = "=" * 72

    print(f"\n{sep}")
    print(f"  Validation : {report.strategy_name}")
    print(sep)

    # ── Tableau par asset ──
    header = (
        f"  {'Ticker':<8} {'Trades':>6} {'WR':>6} {'PF':>6} "
        f"{'Sharpe':>7} {'Net%':>7}  "
        f"{'Robust':>7} {'Stable':>7} {'Signif':>7}  {'Verdict':<12}"
    )
    print(header)
    print("  " + "-" * 68)

    for a in report.assets:
        r = a.oos_result
        rob = a.robustness
        sub = a.sub_periods
        tt = a.ttest

        rob_str = f"{rob.pct_profitable:.0f}%" if rob.n_combos > 0 else "N/A"
        stab_str = "v" if sub.stable else "x"
        sig_str = "v" if tt.significant else "x"

        print(
            f"  {a.symbol:<8} {r.n_trades:>6} {r.win_rate:>5.0%} "
            f"{r.profit_factor:>6.2f} {r.sharpe:>7.2f} "
            f"{r.net_return_pct:>6.1f}%  "
            f"{rob_str:>7} {stab_str:>7} {sig_str:>7}  "
            f"{a.verdict.value:<12}"
        )

    # ── Pooled t-test ──
    if report.pooled_ttest is not None:
        pt = report.pooled_ttest
        print(f"\n  T-test poole : {pt.n_trades} trades, "
              f"t={pt.t_stat:.2f}, p={pt.p_value:.4f} - {pt.label}")

    # ── Résumé ──
    print(f"\n  VALIDATED    : {', '.join(report.validated) or '-'}")
    print(f"  CONDITIONAL  : {', '.join(report.conditional) or '-'}")
    print(f"  REJECTED     : {', '.join(report.rejected) or '-'}")
    print(sep)


def save_report(
    report: ValidationReport,
    output_dir: Path | None = None,
) -> Path:
    """Sauvegarde le rapport en JSON.

    Nom du fichier : {strategy}_{universe}_{date}.json
    Ex: rsi2_us_stocks_large_2026-03-02.json

    Args:
        report: Rapport de validation complet
        output_dir: Repertoire de sortie (defaut: validation_results/)

    Returns:
        Chemin du fichier JSON cree
    """
    if output_dir is None:
        output_dir = Path("validation_results")
    output_dir.mkdir(exist_ok=True)

    date_str = report.timestamp[:10]
    universe = report.universe_name or "unknown"
    filename = f"{report.strategy_name}_{universe}_{date_str}.json"
    path = output_dir / filename

    pooled: dict = {}
    if report.pooled_ttest is not None:
        pt = report.pooled_ttest
        pooled = {
            "n_trades": pt.n_trades,
            "t_stat": round(pt.t_stat, 4),
            "p_value": round(pt.p_value, 6),
            "significant": pt.significant,
        }

    data = {
        "strategy": report.strategy_name,
        "universe": universe,
        "timestamp": report.timestamp,
        "pooled_ttest": pooled,
        "assets": [
            {
                "symbol": a.symbol,
                "n_trades": a.oos_result.n_trades,
                "win_rate": round(a.oos_result.win_rate, 4),
                "profit_factor": round(a.oos_result.profit_factor, 4),
                "sharpe": round(a.oos_result.sharpe, 4),
                "net_return_pct": round(a.oos_result.net_return_pct, 2),
                "robustness_pct": round(a.robustness.pct_profitable, 1),
                "stable": a.sub_periods.stable,
                "ttest_p": round(a.ttest.p_value, 6),
                "verdict": a.verdict.value,
            }
            for a in report.assets
        ],
        "summary": {
            "validated": report.validated,
            "conditional": report.conditional,
            "rejected": report.rejected,
        },
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return path
