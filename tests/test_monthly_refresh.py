"""Tests for scripts/monthly_refresh.py -- monthly refresh logic."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure scripts/ is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.monthly_refresh import (
    DEFAULT_COMBOS,
    RefreshSummary,
    _compute_verdict_changes,
    _snapshot_validations,
    format_refresh_telegram,
)


class TestVerdictChanges:
    """Test verdict comparison logic."""

    def test_no_changes(self) -> None:
        before = {("rsi2_mean_reversion", "us_stocks_large", "META"): "VALIDATED"}
        after = {("rsi2_mean_reversion", "us_stocks_large", "META"): "VALIDATED"}
        assert _compute_verdict_changes(before, after) == []

    def test_upgrade(self) -> None:
        before = {("rsi2_mean_reversion", "us_stocks_large", "META"): "CONDITIONAL"}
        after = {("rsi2_mean_reversion", "us_stocks_large", "META"): "VALIDATED"}
        changes = _compute_verdict_changes(before, after)
        assert len(changes) == 1
        assert "CONDITIONAL -> VALIDATED" in changes[0]
        assert "META" in changes[0]

    def test_downgrade(self) -> None:
        before = {("rsi2_mean_reversion", "us_stocks_large", "META"): "VALIDATED"}
        after = {("rsi2_mean_reversion", "us_stocks_large", "META"): "REJECTED"}
        changes = _compute_verdict_changes(before, after)
        assert len(changes) == 1
        assert "VALIDATED -> REJECTED" in changes[0]

    def test_new_asset(self) -> None:
        before: dict[tuple[str, str, str], str] = {}
        after = {("ibs_mean_reversion", "us_stocks_large", "ORCL"): "VALIDATED"}
        changes = _compute_verdict_changes(before, after)
        assert len(changes) == 1
        assert "NEW -> VALIDATED" in changes[0]
        assert "ORCL" in changes[0]

    def test_removed_asset(self) -> None:
        before = {("tom", "us_etfs_broad", "IWM"): "REJECTED"}
        after: dict[tuple[str, str, str], str] = {}
        changes = _compute_verdict_changes(before, after)
        assert len(changes) == 1
        assert "REJECTED -> REMOVED" in changes[0]

    def test_multiple_changes(self) -> None:
        before = {
            ("rsi2", "stocks", "META"): "VALIDATED",
            ("rsi2", "stocks", "MSFT"): "CONDITIONAL",
            ("rsi2", "stocks", "GOOGL"): "REJECTED",
        }
        after = {
            ("rsi2", "stocks", "META"): "VALIDATED",  # no change
            ("rsi2", "stocks", "MSFT"): "VALIDATED",   # upgrade
            ("rsi2", "stocks", "GOOGL"): "REJECTED",   # no change
        }
        changes = _compute_verdict_changes(before, after)
        assert len(changes) == 1  # only MSFT changed
        assert "MSFT" in changes[0]

    def test_empty_snapshots(self) -> None:
        assert _compute_verdict_changes({}, {}) == []


class TestTelegramFormat:
    """Test Telegram message formatting."""

    def test_format_screen_basic(self) -> None:
        summary = RefreshSummary(
            mode="screen",
            combos_run=3,
            combos_ok=3,
            duration_seconds=1800,
        )
        msg = format_refresh_telegram(summary)
        assert "Monthly Screen Refresh" in msg
        assert "3/3 OK" in msg
        assert "30.0 min" in msg
        assert "Refresh complete" in msg

    def test_format_validate_basic(self) -> None:
        summary = RefreshSummary(
            mode="validate",
            combos_run=2,
            combos_ok=2,
            duration_seconds=7200,
        )
        msg = format_refresh_telegram(summary)
        assert "Monthly Validation Refresh" in msg
        assert "120.0 min" in msg

    def test_format_with_failures(self) -> None:
        summary = RefreshSummary(
            mode="screen",
            combos_run=3,
            combos_ok=2,
            combos_failed=1,
            failures=["rsi2/forex_majors: ValueError: no data"],
            duration_seconds=60,
        )
        msg = format_refresh_telegram(summary)
        assert "1 failed" in msg
        assert "Failures:" in msg
        assert "rsi2/forex_majors" in msg

    def test_format_with_verdict_changes(self) -> None:
        summary = RefreshSummary(
            mode="validate",
            combos_run=1,
            combos_ok=1,
            verdict_changes=["META (rsi2/stocks): CONDITIONAL -> VALIDATED"],
            duration_seconds=300,
        )
        msg = format_refresh_telegram(summary)
        assert "Verdict Changes:" in msg
        assert "CONDITIONAL" in msg

    def test_format_html_escapes_special_chars(self) -> None:
        summary = RefreshSummary(
            mode="screen",
            combos_run=1,
            combos_ok=0,
            combos_failed=1,
            failures=["rsi2/test: ValueError: price < 0"],
            duration_seconds=10,
        )
        msg = format_refresh_telegram(summary)
        assert "&lt;" in msg  # < is escaped


class TestDefaultCombos:
    """Test that DEFAULT_COMBOS references valid strategies/universes."""

    def test_all_strategies_valid(self) -> None:
        from cli.runner import STRATEGIES

        for strat, _univ in DEFAULT_COMBOS:
            assert strat in STRATEGIES, f"Unknown strategy in DEFAULT_COMBOS: {strat}"

    def test_all_universes_valid(self) -> None:
        from config.universe_loader import list_universes

        universes = list_universes()
        for _strat, univ in DEFAULT_COMBOS:
            assert univ in universes, f"Unknown universe in DEFAULT_COMBOS: {univ}"

    def test_combo_count(self) -> None:
        # 3 strategies x 3 universes = 9 combos
        assert len(DEFAULT_COMBOS) == 9

    def test_no_forex(self) -> None:
        for _strat, univ in DEFAULT_COMBOS:
            assert "forex" not in univ

    def test_no_donchian(self) -> None:
        for strat, _univ in DEFAULT_COMBOS:
            assert strat != "donchian"


class TestSnapshotValidations:
    """Test _snapshot_validations with a real temp DB."""

    def test_snapshot_empty_db(self, tmp_path: Path) -> None:
        db = SignalRadarDB(str(tmp_path / "test.db"))
        snap = _snapshot_validations(db)
        assert snap == {}


# Import here to avoid import error if DB not available
from data.db import SignalRadarDB
