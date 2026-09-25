"""Session-aware scanner that never treats a raw trigger as a buy order."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from loguru import logger

from data.db import SignalRadarDB
from data.yahoo_loader import YahooLoader
from engine.fee_model import FeeModel, load_saxo_ch_costs
from engine.ranking import conservative_monthly_score, historical_next_open_trades
from engine.trading_calendar import (
    is_expired, last_completed_session, next_session, session_open,
)
from scripts.daily_scanner import (
    Signal, SignalResult, compute_indicators, evaluate_ibs_signal,
    evaluate_signal, evaluate_tom_signal, load_config,
)
from strategies.ibs_mean_reversion import IBSMeanReversion
from strategies.rsi2_mean_reversion import RSI2MeanReversion
from strategies.turn_of_month import TurnOfMonth


STRATEGIES = {
    "rsi2": RSI2MeanReversion,
    "ibs": IBSMeanReversion,
    "tom": TurnOfMonth,
}


def _technical_result(
    name: str, params: dict, symbol: str, ind: dict,
    position: dict | None, watchlist: bool, source_session: str,
) -> SignalResult:
    """Evaluate a strategy without touching cash, positions or order state."""
    if name == "rsi2":
        result = evaluate_signal(
            ind["rsi2"], ind["close"], ind["sma200"], ind["sma5"],
            position,
            rsi_entry_threshold=params.get("rsi_entry_threshold", 10.0),
            sma_trend_buffer=params.get("sma_trend_buffer", 1.01),
            watchlist=watchlist,
        )
    elif name == "ibs":
        result = evaluate_ibs_signal(
            ind["ibs"], ind["close"], ind["high"], ind["high_yesterday"],
            ind["sma200"], position,
            ibs_entry_threshold=params.get("ibs_entry_threshold", 0.2),
            ibs_exit_threshold=params.get("ibs_exit_threshold", 0.8),
            watchlist=watchlist,
        )
    elif name == "tom":
        result = evaluate_tom_signal(
            ind["close"], ind["trading_days_left_in_month"],
            ind["trading_day_of_month"], position,
            entry_days_before_eom=params.get("entry_days_before_eom", 5),
            exit_day_of_new_month=params.get("exit_day_of_new_month", 3),
            current_date=source_session, watchlist=watchlist,
        )
    else:
        raise ValueError(f"Unknown strategy {name}")
    result.symbol = symbol
    result.strategy = name
    return result


def _score(df: pd.DataFrame, strategy_name: str, params: dict, fee_model: FeeModel) -> tuple[float | None, float | None, int]:
    """Use only completed trades before the proposed next opening."""
    strategy = STRATEGIES[strategy_name]()
    merged_params = {**strategy.default_params(), **params, "position_fraction": 1.0}
    trades = historical_next_open_trades(
        df, strategy, merged_params, fee_model,
    )
    score = conservative_monthly_score(
        trades, str(df.index[0].date()), str(df.index[-1].date()),
    )
    return score.lower_monthly_return, score.max_drawdown, score.n_trades


def _indicative_shares(budget: float, raw_close: float, fee_model: FeeModel) -> int:
    """Floor a share estimate using closing price and estimated entry costs."""
    shares = max(0, math.floor(budget / raw_close))
    while shares:
        notional = shares * raw_close
        if notional + fee_model.total_entry_cost(notional) <= budget:
            return shares
        shares -= 1
    return 0


def run_safe_scanner(
    *, db: SignalRadarDB | None = None, loader: YahooLoader | None = None,
    now: datetime | None = None,
) -> dict:
    """Scan one completed XNYS session, recording auditable decisions.

    Replaying a session updates the same rows. No Saxo order is ever sent.
    """
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    database = db or SignalRadarDB()
    prices = loader or YahooLoader()
    config = load_config()
    fee_model, costs_verified = load_saxo_ch_costs()
    source = last_completed_session(current)
    target = next_session(source)
    prior_session, prior_rows = database.get_latest_decisions()
    database.upsert_scanner_session(source, target, "running")
    strategy_configs: dict = config.get("strategies", {})
    symbols = sorted({symbol for cfg in strategy_configs.values() if cfg.get("enabled", True)
                      for symbol in cfg.get("universe", []) + cfg.get("watchlist", [])}
                     | {pos["symbol"] for pos in database.get_v2_open_positions()}
                     | {order["symbol"] for order in database.get_pending_paper_orders()}
                     | {pos["symbol"] for pos in database.get_follow_positions()}
                     | {order["symbol"] for order in database.get_follow_orders()})
    frames: dict[str, pd.DataFrame] = {}
    indicators: dict[str, dict] = {}
    errors: dict[str, str] = {}
    for symbol in symbols:
        try:
            df = prices.get_daily_candles_strict(
                symbol, "2014-01-01", target, source,
            )
            ind = compute_indicators(df)
            if any(not math.isfinite(value) for value in ind.values()
                   if isinstance(value, float)):
                raise ValueError("indicator is not finite")
            frames[symbol] = df
            indicators[symbol] = ind
        except Exception as exc:
            errors[symbol] = str(exc)
            logger.error("{}: {}", symbol, exc)

    # Fill orders only when the exact target raw opening bar has been fetched.
    database.fill_due_paper_orders(source, fee_model)
    database.fill_due_follow_orders(source, fee_model)
    follow_open = database.get_follow_positions()
    follow_pending = database.get_follow_orders()
    paper_open = database.get_v2_open_positions()
    live_open = database.get_open_live_trades()
    confirmation = database.get_account_confirmation(source)
    held_symbols = set(confirmation["holdings"]) if confirmation else set()
    live_symbols = {row["symbol"] for row in live_open}
    pending_orders = database.get_pending_paper_orders()
    expires_at = session_open(target).isoformat()

    decisions: list[dict[str, Any]] = []
    for name, cfg in strategy_configs.items():
        if not cfg.get("enabled", True):
            continue
        params = cfg.get("params", {})
        watchlist = set(cfg.get("watchlist", []))
        for symbol in dict.fromkeys(cfg.get("universe", []) + list(watchlist)):
            ind = indicators.get(symbol)
            if ind is None:
                decisions.append({
                    "source_session": source, "target_session": target,
                    "strategy": name, "symbol": symbol,
                    "technical_signal": "DATA_MISSING", "eligibility": "DATA_MISSING",
                    "reasons": [errors.get(symbol, "missing market data")],
                    "note": errors.get(symbol, "missing market data"),
                    "expires_at": expires_at,
                })
                continue
            paper_pos = next((p for p in paper_open if p["symbol"] == symbol
                              and p["strategy"] == name), None)
            live_pos = next((p for p in live_open if p["symbol"] == symbol
                             and p["strategy"] == name), None)
            follow_pos = next((p for p in follow_open if p["symbol"] == symbol
                               and p["strategy"] == name), None)
            def state(pos: dict | None) -> dict | None:
                """Adapt a recorded position to the strategy's signal interface."""
                return (
                    {"status": "open", **pos,
                     "entry_date": pos.get("entry_session", pos.get("entry_date", ""))}
                    if pos else None
                )

            # A real trade can be ignored or taken without changing the
            # simulation. Evaluate each ledger against its own position.
            result = _technical_result(
                name, params, symbol, ind, state(live_pos),
                symbol in watchlist, source,
            )
            paper_result = _technical_result(
                name, params, symbol, ind, state(paper_pos),
                symbol in watchlist, source,
            )
            follow_result = _technical_result(
                name, params, symbol, ind, state(follow_pos),
                symbol in watchlist, source,
            )
            technical = result.signal.value
            paper_technical = paper_result.signal.value
            follow_technical = follow_result.signal.value
            row: dict[str, Any] = {
                "source_session": source, "target_session": target,
                "strategy": name, "symbol": symbol,
                "technical_signal": technical, "eligibility": "NOT_APPLICABLE",
                "reasons": [], "details": {**result.details, "paper_signal": paper_technical, "paper_status": "NO_SIGNAL",
                            "follow_signal": follow_technical, "follow_status": "NO_SIGNAL"}, "note": result.notes,
                "score": None, "max_budget_usd": None,
                "indicative_shares": None, "close_price": ind["close"],
                "indicator_value": (
                    ind["rsi2"] if name == "rsi2" else
                    ind["ibs"] if name == "ibs" else
                    float(ind["trading_days_left_in_month"])
                ),
                "expires_at": expires_at,
            }
            if technical == "BUY" or paper_technical == "BUY" or follow_technical == "BUY":
                score, drawdown, count = _score(frames[symbol], name, params, fee_model)
                row["score"] = score
                row["max_drawdown"] = drawdown
                row["historical_trades"] = count
                if technical == "BUY":
                    row["eligibility"] = "CANDIDATE"
            decisions.append(row)

    buys = [row for row in decisions if row["technical_signal"] == "BUY"]
    # A title is a single candidate even when several strategies agree.
    groups: dict[str, list[dict]] = {}
    for row in buys:
        groups.setdefault(row["symbol"], []).append(row)
    representatives: list[dict] = []
    for symbol, group in groups.items():
        ordered = sorted(group, key=lambda r: (
            -(r["score"] if r["score"] is not None else -math.inf),
            r.get("max_drawdown") if r.get("max_drawdown") is not None else math.inf,
            r["strategy"],
        ))
        lead = ordered[0]
        lead["triggered_strategies"] = sorted(r["strategy"] for r in group)
        representatives.append(lead)
        for duplicate in ordered[1:]:
            duplicate["eligibility"] = "MERGED"
            duplicate["reasons"] = [f"combined with {lead['strategy']} on {symbol}"]

    representatives.sort(key=lambda r: (
        -(r["score"] if r["score"] is not None else -math.inf),
        r.get("max_drawdown") if r.get("max_drawdown") is not None else math.inf,
        r["symbol"],
    ))
    winner_chosen = False
    for row in representatives:
        reasons: list[str] = []
        score = row["score"]
        symbol = row["symbol"]

        if errors:
            reasons.append("market data missing for: " + ", ".join(sorted(errors)))
        if is_expired(target, current):
            reasons.append("target market open has passed")
        if not confirmation:
            reasons.append("Saxo cash and holdings not confirmed for this session")
        if live_symbols and not live_symbols.issubset(held_symbols):
            reasons.append("open journal trades disagree with confirmed holdings")
        if symbol in held_symbols:
            reasons.append("title already held at Saxo")
        if live_open:
            reasons.append("one Signal Radar position already open")

        if score is None:
            reasons.append("fewer than 30 completed historical trades")
        elif score <= 0:
            reasons.append("conservative net monthly return is not positive")
        # A new validation and actual Saxo cost reconciliation are prerequisites.
        validation = database.get_score(row["strategy"], symbol, source)
        if not validation or validation["verdict"] != "VALIDATED":
            reasons.append("strategy has no current next-open validation")
        elif (pd.Timestamp(source) - pd.Timestamp(validation["asof_session"])).days > 40:
            reasons.append("next-open validation is older than 40 days")
        if not costs_verified or not validation or not validation["calibrated"]:
            reasons.append("next-open validation and Saxo fees not yet calibrated")
        if winner_chosen:
            reasons.append("higher-ranked eligible candidate has priority")
        budget = min(
            5000.0,
            confirmation["cash_usd"] if confirmation else 0.0,
        )
        row["max_budget_usd"] = round(budget, 2)
        raw_close = float(frames[symbol]["Close"].iloc[-1])
        row["indicative_shares"] = _indicative_shares(budget, raw_close, fee_model)
        if confirmation and (budget <= 0 or row["indicative_shares"] == 0):
            reasons.append("confirmed Saxo cash cannot buy one share")
        row["reasons"] = reasons
        row["eligibility"] = "ELIGIBLE" if not reasons else "BLOCKED"
        if not reasons:
            winner_chosen = True

    # Paper follows its own signals, cash and single-position limit. Saxo
    # holdings, live trades and manual account confirmation never select it.
    # In observation mode, symbols with missing data are excluded from paper
    # selection while every real recommendation remains blocked.
    paper_warning = (
        "Paper universe incomplete; excluded symbols: " + ", ".join(sorted(errors))
        if errors else None
    )
    if paper_warning:
        for row in decisions:
            row.setdefault("details", {})["paper_warnings"] = [paper_warning]
    paper_groups: dict[str, list[dict]] = {}
    for row in decisions:
        if row.get("details", {}).get("paper_signal") == "BUY":
            paper_groups.setdefault(row["symbol"], []).append(row)
    paper_candidates: list[dict] = []
    for symbol, group in paper_groups.items():
        ordered = sorted(group, key=lambda item: (
            -(item["score"] if item["score"] is not None else -math.inf),
            item.get("max_drawdown") if item.get("max_drawdown") is not None else math.inf,
            item["strategy"],
        ))
        lead = ordered[0]
        lead["details"]["paper_triggered_strategies"] = sorted(
            item["strategy"] for item in group
        )
        paper_candidates.append(lead)
        for duplicate in ordered[1:]:
            duplicate["details"]["paper_status"] = "MERGED"
            duplicate["details"]["paper_reasons"] = [
                f"combined with {lead['strategy']} on {symbol}"
            ]
    paper_candidates.sort(key=lambda item: (
        -(item["score"] if item["score"] is not None else -math.inf),
        item.get("max_drawdown") if item.get("max_drawdown") is not None else math.inf,
        item["symbol"],
    ))
    paper_winner_chosen = False
    for row in paper_candidates:
        symbol = row["symbol"]
        own_pending = next((
            order for order in pending_orders
            if order["side"] == "BUY"
            and order["source_session"] == source
            and order["symbol"] == symbol
            and order["strategy"] == row["strategy"]
        ), None)
        if own_pending:
            row["details"]["paper_status"] = "PENDING_BUY"
            row["details"]["paper_budget_usd"] = own_pending["budget_usd"]
            row["details"]["paper_indicative_shares"] = own_pending["indicative_shares"]
            continue
        paper_reasons: list[str] = []
        if is_expired(target, current):
            paper_reasons.append("target market open has passed")
        if paper_open or any(order["side"] == "BUY" for order in pending_orders):
            paper_reasons.append("single paper portfolio already committed")
        if any(order["side"] == "SELL" for order in pending_orders):
            paper_reasons.append("pending paper sale does not release budget")
        score = row["score"]
        if score is None:
            paper_reasons.append("fewer than 30 completed historical trades")
        elif score <= 0:
            paper_reasons.append("conservative net monthly return is not positive")
        if paper_winner_chosen:
            paper_reasons.append("higher-ranked paper candidate has priority")
        paper_budget = min(5000.0, database.get_v2_paper_cash())
        paper_shares = _indicative_shares(
            paper_budget, float(frames[symbol]["Close"].iloc[-1]), fee_model,
        )
        row["details"]["paper_budget_usd"] = round(paper_budget, 2)
        row["details"]["paper_indicative_shares"] = paper_shares
        if paper_shares == 0 and not (paper_open or pending_orders):
            paper_reasons.append("paper portfolio cannot buy one share")
        if paper_reasons:
            row["details"]["paper_status"] = "BLOCKED"
            row["details"]["paper_reasons"] = paper_reasons
            continue
        queued = database.queue_paper_order(
            source, target, row["strategy"], symbol, "BUY",
            paper_budget, paper_shares,
        )
        row["details"]["paper_status"] = "PENDING_BUY" if queued else "BLOCKED"
        if queued:
            paper_winner_chosen = True
        else:
            row["details"]["paper_reasons"] = ["paper order already exists"]

    # Virtual follow-up is a per-strategy, per-title experiment. It does not
    # reserve shared paper cash and never reads Saxo holdings or confirmation.
    for row in decisions:
        detail = row.get("details", {})
        signal = detail.get("follow_signal")
        symbol, strategy = row["symbol"], row["strategy"]
        own_open = next((p for p in follow_open
                         if p["symbol"] == symbol and p["strategy"] == strategy), None)
        own_pending = next((o for o in follow_pending
                            if o["symbol"] == symbol and o["strategy"] == strategy), None)
        if signal == "BUY":
            if own_pending and own_pending["side"] == "BUY":
                detail["follow_status"] = "PENDING_BUY"
            elif is_expired(target, current):
                detail["follow_status"] = "EXPIRED"
            elif row["score"] is None or row["score"] <= 0:
                detail["follow_status"] = "SCORE_NOT_POSITIVE"
            elif _indicative_shares(
                5000.0, float(frames[symbol]["Close"].iloc[-1]), fee_model,
            ) == 0:
                detail["follow_status"] = "NOTIONAL_TOO_SMALL"
            elif database.queue_follow_order(
                source, target, strategy, symbol, "BUY",
            ):
                detail["follow_status"] = "PENDING_BUY"
            else:
                detail["follow_status"] = "ALREADY_TRACKED"
        elif signal in {"SELL", "SAFETY_EXIT"} and own_open:
            if own_pending and own_pending["side"] == "SELL":
                detail["follow_status"] = "PENDING_SELL"
            elif database.queue_follow_order(
                source, target, strategy, symbol, "SELL",
                position_id=own_open["id"],
            ):
                detail["follow_status"] = "PENDING_SELL"
            else:
                detail["follow_status"] = "HOLD"
        elif own_open:
            detail["follow_status"] = "HOLD"

    for row in decisions:
        paper_signal = row.get("details", {}).get("paper_signal")
        if paper_signal in {"SELL", "SAFETY_EXIT"}:
            if any(pos["symbol"] == row["symbol"] and pos["strategy"] == row["strategy"]
                   for pos in paper_open):
                database.queue_paper_order(
                    source, target, row["strategy"], row["symbol"], "SELL",
                )
                row["details"]["paper_status"] = "PENDING_SELL"
        elif paper_signal == "HOLD":
            row["details"]["paper_status"] = "HOLD"
        if row["technical_signal"] in {"SELL", "SAFETY_EXIT"}:
            row["eligibility"] = "EXIT_SIGNAL"
        database.upsert_decision(row)

    database.upsert_scanner_session(
        source, target, "complete" if not errors else "data_missing",
        "; ".join(f"{symbol}: {message}" for symbol, message in errors.items()) or None,
    )
    _, saved = database.get_latest_decisions()
    def stable(rows: list[dict]) -> list[dict]:
        """Ignore storage timestamps when deciding whether to notify again."""
        return [{key: value for key, value in row.items() if key != "updated_at"}
                for row in rows]

    if prior_session != source or stable(prior_rows) != stable(saved):
        from engine.notifier import send_telegram

        buy_groups: dict[str, list[str]] = {}
        for row in saved:
            if row["technical_signal"] == "BUY":
                buy_groups.setdefault(row["symbol"], []).append(row["strategy"].upper())
        buy_text = "; ".join(
            f"{symbol} ({', '.join(sorted(strategies))})"
            for symbol, strategies in sorted(buy_groups.items())
        ) or "aucun"
        exits = sorted(
            f"{row['symbol']} ({row['strategy'].upper()})"
            for row in saved
            if row["technical_signal"] in {"SELL", "SAFETY_EXIT"}
        )
        paper_buys = [r["symbol"] for r in saved
                      if r["details"].get("paper_status") == "PENDING_BUY"]
        paper_sells = [r["symbol"] for r in saved
                       if r["details"].get("paper_status") == "PENDING_SELL"]
        summary = (
            f"Signal Radar {source} → ouverture {target}\n"
            f"Signaux techniques d'achat: {buy_text}\n"
            f"Sorties par stratégie: {', '.join(exits) or 'aucune'}\n"
            f"Simulation papier: achat {', '.join(paper_buys) or 'aucun'} ; "
            f"vente {', '.join(paper_sells) or 'aucune'}\n"
            f"Données manquantes: {len(errors)}. "
            "Validation récente, frais réels et conditions Saxo à vérifier. "
            "Aucune capacité d'achat réelle calculée."
        )
        send_telegram(summary)
    return {
        "source_session": source, "target_session": target,
        "errors": errors, "decisions": saved,
    }
