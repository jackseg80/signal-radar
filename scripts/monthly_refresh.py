"""Monthly Backtest Refresh -- re-runs screens (and optionally validations)
for all strategy x universe combos, compares verdicts, sends Telegram summary.

Usage:
    python scripts/monthly_refresh.py                          # screen mode (fast, ~45 min)
    python scripts/monthly_refresh.py --mode validate          # full validation (~6.5h)
    python scripts/monthly_refresh.py --dry-run                # just show what would run
    python scripts/monthly_refresh.py --combos rsi2:us_etfs_broad  # single combo

Scheduling (Docker cron):
    0 4 1 * * root . /app/.env.cron && cd /app && python scripts/monthly_refresh.py >> /proc/1/fd/1 2>> /proc/1/fd/2
"""

from __future__ import annotations

import argparse
import html
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

# ── Path setup ──

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cli.runner import STRATEGIES, ScreenResult, ValidateResult, run_screen, run_validate
from data.db import SignalRadarDB
from engine.notifier import send_telegram

# ── Configuration ──

# Default combos to refresh.
# Excludes: forex_majors (all strategies REJECTED, not traded on Saxo USD)
# Excludes: donchian (REJECTED on all universes)
DEFAULT_COMBOS: list[tuple[str, str]] = [
    # Stocks large cap -- core system
    ("rsi2", "us_stocks_large"),
    ("ibs", "us_stocks_large"),
    ("tom", "us_stocks_large"),
    # ETFs broad -- diversified portfolio
    ("rsi2", "us_etfs_broad"),
    ("ibs", "us_etfs_broad"),
    ("tom", "us_etfs_broad"),
    # ETFs sector -- sector coverage
    ("rsi2", "us_etfs_sector"),
    ("ibs", "us_etfs_sector"),
    ("tom", "us_etfs_sector"),
]

LOG_PATH = PROJECT_ROOT / "logs" / "monthly_refresh.log"


# ── Result dataclass ──


@dataclass
class RefreshSummary:
    """Aggregate results of a monthly refresh run."""

    mode: str  # "screen" or "validate"
    combos_run: int = 0
    combos_ok: int = 0
    combos_failed: int = 0
    failures: list[str] = field(default_factory=list)
    screen_results: list[ScreenResult] = field(default_factory=list)
    validate_results: list[ValidateResult] = field(default_factory=list)
    verdict_changes: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0


# ── Verdict snapshot & diff ──


def _snapshot_validations(db: SignalRadarDB) -> dict[tuple[str, str, str], str]:
    """Snapshot current verdicts: {(strategy, universe, symbol): verdict}."""
    rows = db.get_validations_filtered()
    return {
        (r["strategy"], r["universe"], r["symbol"]): r["verdict"]
        for r in rows
    }


def _compute_verdict_changes(
    before: dict[tuple[str, str, str], str],
    after: dict[tuple[str, str, str], str],
) -> list[str]:
    """Compute verdict changes between two snapshots."""
    changes: list[str] = []
    all_keys = sorted(set(before.keys()) | set(after.keys()))
    for key in all_keys:
        old = before.get(key)
        new = after.get(key)
        if old and new and old != new:
            strat, univ, sym = key
            changes.append(f"{sym} ({strat}/{univ}): {old} -> {new}")
        elif old and not new:
            strat, univ, sym = key
            changes.append(f"{sym} ({strat}/{univ}): {old} -> REMOVED")
        elif not old and new:
            strat, univ, sym = key
            changes.append(f"{sym} ({strat}/{univ}): NEW -> {new}")
    return changes


# ── Core refresh logic ──


def run_refresh(
    combos: list[tuple[str, str]],
    mode: str = "screen",
    dry_run: bool = False,
) -> RefreshSummary:
    """Run the monthly refresh for all combos.

    Args:
        combos: List of (strategy_key, universe_name) tuples.
        mode: "screen" (fast) or "validate" (full).
        dry_run: If True, just log what would run.

    Returns:
        RefreshSummary with aggregate results.
    """
    summary = RefreshSummary(mode=mode)
    t0 = time.time()

    db = SignalRadarDB()

    # Snapshot verdicts before (validate mode only)
    verdicts_before: dict[tuple[str, str, str], str] = {}
    if mode == "validate":
        verdicts_before = _snapshot_validations(db)

    for strategy_key, universe_name in combos:
        summary.combos_run += 1
        label = f"{strategy_key}/{universe_name}"

        if dry_run:
            logger.info(f"[DRY RUN] Would {mode}: {label}")
            summary.combos_ok += 1
            continue

        logger.info(
            f"[{summary.combos_run}/{len(combos)}] {mode.upper()}: {label}"
        )

        try:
            if mode == "screen":
                result = run_screen(strategy_key, universe_name, db=db)
                summary.screen_results.append(result)
                logger.info(
                    f"  -> {len(result.assets)} assets, "
                    f"{result.n_profitable} profitable"
                )
            else:
                result = run_validate(strategy_key, universe_name, db=db)
                summary.validate_results.append(result)
                rpt = result.report
                n_v = len(rpt.validated)
                n_c = len(rpt.conditional)
                n_r = len(rpt.rejected)
                logger.info(
                    f"  -> {len(rpt.assets)} assets: "
                    f"{n_v} VALIDATED, {n_c} CONDITIONAL, {n_r} REJECTED"
                )

            summary.combos_ok += 1

        except Exception as e:
            summary.combos_failed += 1
            err_msg = f"{label}: {type(e).__name__}: {e}"
            summary.failures.append(err_msg)
            logger.error(f"  FAILED: {err_msg}")

    # Compute verdict changes (validate mode only)
    if mode == "validate" and not dry_run:
        verdicts_after = _snapshot_validations(db)
        summary.verdict_changes = _compute_verdict_changes(
            verdicts_before, verdicts_after
        )

    summary.duration_seconds = time.time() - t0
    return summary


# ── Telegram formatting ──


def format_refresh_telegram(summary: RefreshSummary) -> str:
    """Format the refresh summary as a Telegram HTML message."""
    today = datetime.now().strftime("%Y-%m-%d")
    mode_label = "Screen" if summary.mode == "screen" else "Validation"

    lines: list[str] = [
        f"\U0001f504 <b>Monthly {mode_label} Refresh</b> -- {today}",
        "",
    ]

    # Combos summary
    status = f"Combos: {summary.combos_ok}/{summary.combos_run} OK"
    if summary.combos_failed:
        status += f" ({summary.combos_failed} failed)"
    lines.append(status)
    lines.append(f"Duration: {summary.duration_seconds / 60:.1f} min")
    lines.append("")

    # Screen results
    if summary.mode == "screen" and summary.screen_results:
        lines.append("<b>Results:</b>")
        for sr in summary.screen_results:
            lines.append(
                f"  {sr.strategy_key}/{sr.universe_name}: "
                f"{len(sr.assets)} assets, {sr.n_profitable} PF&gt;1"
            )
        lines.append("")

    # Validate results
    if summary.mode == "validate" and summary.validate_results:
        lines.append("<b>Results:</b>")
        for vr in summary.validate_results:
            rpt = vr.report
            n_v = len(rpt.validated)
            n_c = len(rpt.conditional)
            n_r = len(rpt.rejected)
            lines.append(
                f"  {vr.strategy_key}/{vr.universe_name}: "
                f"{n_v}V / {n_c}C / {n_r}R"
            )
        lines.append("")

    # Verdict changes
    if summary.verdict_changes:
        lines.append("<b>Verdict Changes:</b>")
        for change in summary.verdict_changes:
            lines.append(f"  {html.escape(change)}")
        lines.append("")

    # Failures
    if summary.failures:
        lines.append("<b>Failures:</b>")
        for f in summary.failures:
            lines.append(f"  {html.escape(f)}")
        lines.append("")

    lines.append("\u2705 Refresh complete.")
    return "\n".join(lines)


# ── CLI ──


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Monthly backtest refresh")
    parser.add_argument(
        "--mode",
        choices=["screen", "validate"],
        default="screen",
        help="screen (fast, ~45min) or validate (full, ~6.5h)",
    )
    parser.add_argument("--dry-run", action="store_true", help="List combos without running")
    parser.add_argument(
        "--combos",
        type=str,
        default=None,
        help="Override combos: 'rsi2:us_stocks_large,ibs:us_etfs_broad'",
    )
    args = parser.parse_args()

    # Setup logging
    LOG_PATH.parent.mkdir(exist_ok=True)
    logger.add(str(LOG_PATH), rotation="1 MB", retention="90 days", level="DEBUG")

    # Parse combos
    if args.combos:
        combos: list[tuple[str, str]] = []
        for pair in args.combos.split(","):
            parts = pair.strip().split(":")
            if len(parts) != 2:
                print(f"  Error: invalid combo format '{pair}' (expected strategy:universe)")
                sys.exit(1)
            combos.append((parts[0].strip(), parts[1].strip()))
    else:
        combos = DEFAULT_COMBOS

    # Header
    print(f"\n{'=' * 60}")
    print(f"  SIGNAL RADAR -- Monthly Backtest Refresh")
    print(f"  {datetime.now():%Y-%m-%d %H:%M}")
    print(f"  {len(combos)} combinations, mode={args.mode}")
    if args.dry_run:
        print(f"  ** DRY RUN **")
    print(f"{'=' * 60}\n")

    logger.info(
        f"Monthly refresh: mode={args.mode}, "
        f"combos={len(combos)}, dry_run={args.dry_run}"
    )

    # Run
    summary = run_refresh(combos, mode=args.mode, dry_run=args.dry_run)

    # Telegram (skip in dry run)
    if not args.dry_run:
        msg = format_refresh_telegram(summary)
        sent = send_telegram(msg)
        if sent:
            logger.info("Telegram summary sent")
        else:
            logger.warning("Telegram not sent (not configured or error)")

    # Console summary
    print(f"\n{'=' * 60}")
    print(f"  REFRESH COMPLETE -- {summary.duration_seconds / 60:.1f} min")
    print(f"  {summary.combos_ok}/{summary.combos_run} OK", end="")
    if summary.combos_failed:
        print(f" ({summary.combos_failed} failed)", end="")
    print()

    if summary.verdict_changes:
        print(f"\n  Verdict changes ({len(summary.verdict_changes)}):")
        for c in summary.verdict_changes:
            print(f"    {c}")

    if summary.failures:
        print(f"\n  Failures ({len(summary.failures)}):")
        for f in summary.failures:
            print(f"    {f}")

    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
