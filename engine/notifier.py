"""Telegram notifier for signal-radar (stdlib-only).

Uses urllib.request to send messages via the Telegram Bot API.
No external dependency required. Gracefully degrades if token/chat_id are not set.
"""

from __future__ import annotations

import html
import json
import os
import urllib.error
import urllib.request
from datetime import datetime
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from scripts.daily_scanner import SignalResult

# ---------------------------------------------------------------------------
# Telegram send
# ---------------------------------------------------------------------------

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"

_ACTIONABLE_SIGNALS = {"BUY", "SELL", "SAFETY_EXIT"}


def send_telegram(text: str, *, parse_mode: str = "HTML") -> bool:
    """Send a message via Telegram Bot API.

    Reads TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from environment.
    Returns True on success, False on failure. Never raises.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        logger.debug("Telegram not configured (missing token or chat_id)")
        return False

    url = TELEGRAM_API_URL.format(token=token)
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    return True
                logger.warning(
                    "Telegram: HTTP {} (attempt {})", resp.status, attempt + 1
                )
        except urllib.error.URLError as exc:
            logger.warning(
                "Telegram: network error {} (attempt {})", exc, attempt + 1
            )
        except Exception as exc:
            logger.warning(
                "Telegram: unexpected error {} (attempt {})", exc, attempt + 1
            )
            break  # no retry on unexpected errors

    logger.error("Telegram: failed to send after retries")
    return False


# ---------------------------------------------------------------------------
# Message formatting
# ---------------------------------------------------------------------------

_SIGNAL_EMOJI = {
    "BUY": "\U0001f7e2",       # 🟢
    "SELL": "\U0001f534",       # 🔴
    "SAFETY_EXIT": "\u26a0\ufe0f",  # ⚠️
}


def format_signal_message(
    results: list[SignalResult],
    last_dates: dict[str, str],
    watchlist_symbols: set[str] | None = None,
) -> str | None:
    """Format actionable signals as a Telegram HTML message.

    Returns None if no actionable signals (BUY/SELL/SAFETY_EXIT)
    and no watchlist BUY triggers → silence.
    """
    wl = watchlist_symbols or set()

    actionable = [
        r for r in results
        if str(r.signal.value) in _ACTIONABLE_SIGNALS
    ]
    watch_triggers = [
        r for r in results
        if str(r.signal.value) == "WATCH"
        and r.symbol in wl
        and "Would trigger BUY" in r.notes
    ]

    if not actionable and not watch_triggers:
        return None

    today = datetime.now().strftime("%Y-%m-%d")
    lines: list[str] = [f"\U0001f4ca <b>Signal Radar</b> — {today}", ""]

    for r in actionable:
        sig = str(r.signal.value)
        emoji = _SIGNAL_EMOJI.get(sig, "\u2753")
        label = "SAFETY EXIT" if sig == "SAFETY_EXIT" else sig
        lines.append(f"{emoji} <b>{label} {r.symbol}</b>")
        lines.append(f"  {html.escape(r.notes)}")
        lines.append("")

    for r in watch_triggers:
        lines.append(f"\U0001f440 <b>WATCH {r.symbol}</b> (watchlist)")
        lines.append(f"  {html.escape(r.notes)}")
        lines.append("")

    remaining = [
        r for r in results
        if r not in actionable and r not in watch_triggers
        and str(r.signal.value) not in ("NO_SIGNAL", "WATCH")
    ]
    if remaining:
        for r in remaining:
            lines.append(
                f"{r.symbol}: {r.signal.value} — {html.escape(r.notes)}"
            )

    return "\n".join(lines).strip()


def format_weekly_summary(
    results: list[SignalResult],
    positions: dict[str, Any],
) -> str:
    """Format a weekly summary message (sent every Sunday).

    Always returns a message (never None) — the weekly report is sent
    even when there are no actionable signals.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    lines: list[str] = [f"\U0001f4ca <b>Signal Radar Weekly</b> — {today}", ""]

    # Open positions
    open_pos = {
        sym: pos for sym, pos in positions.items()
        if isinstance(pos, dict) and pos.get("status") in ("open", "pending")
    }
    if open_pos:
        lines.append("<b>Positions:</b>")
        for sym, pos in open_pos.items():
            status = pos.get("status", "?")
            entry = pos.get("entry_price", pos.get("close", "?"))
            lines.append(f"  {sym}: {status} (entry ~{entry})")
    else:
        lines.append("Positions: none")

    lines.append("")

    # Signal counts
    buy_count = sum(1 for r in results if str(r.signal.value) == "BUY")
    sell_count = sum(
        1 for r in results
        if str(r.signal.value) in ("SELL", "SAFETY_EXIT")
    )
    watch_count = sum(
        1 for r in results
        if str(r.signal.value) == "WATCH" and "Would trigger BUY" in r.notes
    )

    lines.append(f"Week signals: {buy_count} BUY, {sell_count} SELL")
    if watch_count:
        lines.append(f"Watchlist triggers: {watch_count}")

    lines.append("")
    lines.append("Scanner running normally. \u2705")

    return "\n".join(lines)


def format_daily_summary(
    all_results: dict[str, list[SignalResult]],
    paper_summary: dict,
    open_positions: list[dict],
    current_prices: dict[str, float],
    approaching: list[dict] | None = None,
) -> str:
    """Format a complete daily summary (sent every day after scan).

    Always returns a string (never None). Includes signals, open positions
    with unrealized PnL, paper trading stats, and approaching triggers.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    total_pnl = paper_summary.get("total_pnl", 0)
    n_trades = paper_summary.get("n_trades", 0)
    n_open = paper_summary.get("n_open", 0)
    wr = paper_summary.get("win_rate", 0)
    pnl_sign = "+" if total_pnl >= 0 else ""

    # Count strategies and assets
    n_strats = len(all_results)
    n_assets = sum(len(v) for v in all_results.values())

    lines: list[str] = [
        f"\U0001f4ca <b>Signal Radar</b> -- {today}",
        f"\u2705 Scan complete -- {n_strats} strategies, {n_assets} assets",
        "",
    ]

    # --- Actionable signals ---
    actionable: list[SignalResult] = []
    watch_triggers: list[SignalResult] = []

    for _strat_name, results in all_results.items():
        for r in results:
            sig_str = str(r.signal.value)
            if sig_str in _ACTIONABLE_SIGNALS:
                actionable.append(r)
            elif sig_str == "WATCH" and "Would trigger BUY" in r.notes:
                watch_triggers.append(r)

    if actionable or watch_triggers:
        lines.append("\U0001f4cb <b>Signals:</b>")
        for r in actionable:
            sig = str(r.signal.value)
            emoji = _SIGNAL_EMOJI.get(sig, "\u2753")
            label = "SAFETY EXIT" if sig == "SAFETY_EXIT" else sig
            strat_label = r.strategy.upper()
            lines.append(
                f"  {emoji} <b>{label} {r.symbol}</b> ({strat_label})"
            )
            lines.append(f"    {html.escape(r.notes)}")

        for r in watch_triggers:
            strat_label = r.strategy.upper()
            lines.append(
                f"  \U0001f440 <b>WATCH {r.symbol}</b> ({strat_label})"
            )
            lines.append(f"    {html.escape(r.notes)}")
        lines.append("")
    else:
        lines.append("No actionable signals today.")
        lines.append("")

    # --- Open positions with unrealized PnL ---
    if open_positions:
        lines.append("\U0001f4c2 <b>Positions ({} open):</b>".format(
            len(open_positions),
        ))
        for pos in open_positions:
            sym = pos["symbol"]
            entry = pos["entry_price"]
            shares = pos["shares"]
            current = current_prices.get(sym, entry)
            unrealized = (current - entry) * shares
            u_pct = ((current - entry) / entry * 100) if entry > 0 else 0
            u_sign = "+" if unrealized >= 0 else ""
            pct_sign = "+" if u_pct >= 0 else ""
            lines.append(
                f"  {pos['strategy'].upper()} {sym}:"
                f" ${entry:.2f} -> ${current:.2f}"
                f" ({u_sign}${unrealized:.2f}, {pct_sign}{u_pct:.1f}%)"
            )
        lines.append("")

    # --- Paper P&L summary ---
    lines.append(
        f"\U0001f4b0 Paper P&amp;L: {pnl_sign}${total_pnl:.2f}"
        f" ({wr:.0f}% WR, {n_trades} closed)"
    )
    lines.append("")

    # --- Approaching triggers ---
    if approaching:
        lines.append("\u26a1 <b>Approaching trigger:</b>")
        for a in approaching[:5]:
            lines.append(
                f"  {a['strategy'].upper()} {a['symbol']}"
                f" -- {a['label']}"
            )
        lines.append("")

    return "\n".join(lines).strip()
