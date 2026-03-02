"""Tests pour la sauvegarde des rapports de validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.types import BacktestResult, TradeResult, Direction
from validation.report import (
    AssetValidation,
    ValidationReport,
    Verdict,
    save_report,
)
from validation.robustness import RobustnessResult
from validation.statistics import TTestResult
from validation.sub_periods import SubPeriodResult


def _make_asset_validation(symbol: str, pf: float = 1.5) -> AssetValidation:
    """Cree un AssetValidation minimal pour les tests."""
    trade = TradeResult(
        direction=Direction.LONG,
        entry_price=100.0,
        exit_price=101.0,
        entry_candle=0,
        exit_candle=1,
        quantity=10.0,
        pnl=10.0,
        return_pct=0.01,
        holding_days=1,
        exit_reason="test",
        entry_fee=0.5,
        exit_fee=0.5,
    )
    oos_result = BacktestResult(
        trades=[trade] * 50,
        final_capital=10500.0,
        initial_capital=10000.0,
    )
    robustness = RobustnessResult(
        symbol=symbol,
        n_combos=48,
        n_profitable=45,
        pct_profitable=93.75,
        best_pf=3.0,
        worst_pf=0.8,
        median_pf=pf,
        robust=True,
    )
    sub_periods = SubPeriodResult(
        symbol=symbol,
        n_trades_a=25,
        pf_a=1.6,
        sharpe_a=1.0,
        n_trades_b=25,
        pf_b=1.4,
        sharpe_b=0.8,
        stable=True,
    )
    ttest = TTestResult(
        symbol=symbol,
        n_trades=50,
        mean_return_pct=1.0,
        t_stat=3.5,
        p_value=0.001,
        significant=True,
        label="OUI (p<0.05)",
    )
    return AssetValidation(
        symbol=symbol,
        oos_result=oos_result,
        robustness=robustness,
        sub_periods=sub_periods,
        ttest=ttest,
        verdict=Verdict.VALIDATED,
    )


def _make_report() -> ValidationReport:
    """Cree un ValidationReport minimal pour les tests."""
    report = ValidationReport(
        strategy_name="rsi2",
        universe_name="us_stocks_large",
        timestamp="2026-03-02T12:00:00Z",
    )
    report.assets.append(_make_asset_validation("META", pf=3.49))
    report.assets.append(_make_asset_validation("MSFT", pf=1.66))
    report.pooled_ttest = TTestResult(
        symbol="POOLED",
        n_trades=100,
        mean_return_pct=1.0,
        t_stat=4.27,
        p_value=0.00002,
        significant=True,
        label="OUI (p<0.05)",
    )
    return report


class TestSaveReport:
    """Tests pour save_report()."""

    def test_save_report_creates_file(self, tmp_path: Path) -> None:
        """save_report cree un fichier JSON."""
        report = _make_report()
        path = save_report(report, output_dir=tmp_path)
        assert path.exists()
        assert path.suffix == ".json"

    def test_save_report_filename_format(self, tmp_path: Path) -> None:
        """Nom du fichier = strategy_universe_date.json."""
        report = _make_report()
        path = save_report(report, output_dir=tmp_path)
        assert path.name == "rsi2_us_stocks_large_2026-03-02.json"

    def test_save_report_json_valid(self, tmp_path: Path) -> None:
        """Le JSON est valide et parsable."""
        report = _make_report()
        path = save_report(report, output_dir=tmp_path)
        with open(path) as f:
            data = json.load(f)
        assert data["strategy"] == "rsi2"
        assert data["universe"] == "us_stocks_large"
        assert len(data["assets"]) == 2

    def test_save_report_roundtrip(self, tmp_path: Path) -> None:
        """save + load conserve les donnees cles."""
        report = _make_report()
        path = save_report(report, output_dir=tmp_path)
        with open(path) as f:
            data = json.load(f)

        # Verifier les assets
        meta = data["assets"][0]
        assert meta["symbol"] == "META"
        assert meta["n_trades"] == 50
        assert meta["verdict"] == "VALIDATED"
        assert meta["robustness_pct"] == 93.8

        # Verifier le t-test poole
        assert data["pooled_ttest"]["n_trades"] == 100
        assert data["pooled_ttest"]["t_stat"] == 4.27

        # Verifier le resume
        assert "META" in data["summary"]["validated"]
        assert "MSFT" in data["summary"]["validated"]
