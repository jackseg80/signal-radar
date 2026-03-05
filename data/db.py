"""Database management for Signal Radar."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, List, Dict, Optional
import json
from datetime import datetime

import pandas as pd
from loguru import logger

SQLITE_TIMEOUT = 30.0


class SignalRadarDB:
    """Unified SQLite database for OHLCV, backtests, paper and live trading."""

    def __init__(self, db_path: str | Path = "data/signal_radar.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        """Create a new SQLite connection with proper timeout."""
        return sqlite3.connect(self.db_path, timeout=SQLITE_TIMEOUT)

    def _init_db(self) -> None:
        """Cree les tables si elles n'existent pas et execute les migrations."""
        with self._connect() as conn:
            # -- Prix OHLCV --
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ohlcv (
                    symbol TEXT NOT NULL,
                    date TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL,
                    PRIMARY KEY (symbol, date)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol ON ohlcv(symbol)")

            # -- Resultats de validation --
            conn.execute("""
                CREATE TABLE IF NOT EXISTS validations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    universe TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    n_trades INTEGER,
                    win_rate REAL,
                    profit_factor REAL,
                    sharpe REAL,
                    net_return_pct REAL,
                    robustness_pct REAL,
                    stable INTEGER,
                    ttest_p REAL,
                    verdict TEXT,
                    UNIQUE(strategy, universe, symbol, timestamp)
                )
            """)

            # -- Resultats de screening --
            conn.execute("""
                CREATE TABLE IF NOT EXISTS screens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    universe TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    n_trades INTEGER,
                    win_rate REAL,
                    profit_factor REAL,
                    sharpe REAL,
                    net_return_pct REAL,
                    UNIQUE(strategy, universe, symbol, timestamp)
                )
            """)

            # -- Asset Metadata (Names, Logos) --
            conn.execute("""
                CREATE TABLE IF NOT EXISTS asset_metadata (
                    symbol TEXT PRIMARY KEY,
                    name TEXT,
                    logo_url TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # -- Paper trading positions --
            conn.execute("""
                CREATE TABLE IF NOT EXISTS paper_positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    entry_date TEXT NOT NULL,
                    entry_price REAL NOT NULL CHECK(entry_price > 0),
                    shares REAL NOT NULL CHECK(shares > 0),
                    status TEXT NOT NULL DEFAULT 'open',
                    exit_date TEXT,
                    exit_price REAL,
                    pnl_dollars REAL,
                    pnl_pct REAL,
                    notes TEXT DEFAULT '',
                    tags TEXT,
                    sentiment TEXT,
                    UNIQUE(strategy, symbol, entry_date)
                )
            """)

            # -- Live trades --
            conn.execute("""
                CREATE TABLE IF NOT EXISTS live_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL DEFAULT 'long',
                    entry_date TEXT NOT NULL,
                    entry_price REAL NOT NULL CHECK(entry_price > 0),
                    shares REAL NOT NULL CHECK(shares > 0),
                    fees_entry REAL DEFAULT 0 CHECK(fees_entry >= 0),
                    status TEXT NOT NULL DEFAULT 'open',
                    exit_date TEXT,
                    exit_price REAL,
                    fees_exit REAL DEFAULT 0 CHECK(fees_exit >= 0),
                    pnl_dollars REAL,
                    pnl_pct REAL,
                    notes TEXT DEFAULT '',
                    tags TEXT,
                    sentiment TEXT,
                    paper_position_id INTEGER,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    UNIQUE(strategy, symbol, entry_date)
                )
            """)

            # -- Signal log --
            conn.execute("""
                CREATE TABLE IF NOT EXISTS signal_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    signal TEXT NOT NULL,
                    close_price REAL,
                    indicator_value REAL,
                    notes TEXT,
                    details_json TEXT
                )
            """)

            # -- Migrations for existing tables --
            try: conn.execute("ALTER TABLE signal_log ADD COLUMN details_json TEXT")
            except sqlite3.OperationalError: pass
            
            try: conn.execute("ALTER TABLE paper_positions ADD COLUMN notes TEXT DEFAULT ''")
            except sqlite3.OperationalError: pass
            
            try: conn.execute("ALTER TABLE paper_positions ADD COLUMN tags TEXT")
            except sqlite3.OperationalError: pass
            
            try: conn.execute("ALTER TABLE paper_positions ADD COLUMN sentiment TEXT")
            except sqlite3.OperationalError: pass
            
            try: conn.execute("ALTER TABLE live_trades ADD COLUMN tags TEXT")
            except sqlite3.OperationalError: pass
            
            try: conn.execute("ALTER TABLE live_trades ADD COLUMN sentiment TEXT")
            except sqlite3.OperationalError: pass

            # -- Indexes --
            conn.execute("CREATE INDEX IF NOT EXISTS idx_signal_log_timestamp ON signal_log(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_signal_log_symbol_ts ON signal_log(symbol, timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_paper_positions_status_strategy ON paper_positions(status, strategy)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_live_trades_status_strategy ON live_trades(status, strategy)")
            
            conn.commit()

    def _query(self, query: str, params: tuple = ()) -> list[dict]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(query, params)
            return [dict(row) for row in cur.fetchall()]

    def _query_one(self, query: str, params: tuple = ()) -> dict | None:
        rows = self._query(query, params)
        return rows[0] if rows else None

    # -- Metadata --
    def save_asset_metadata(self, symbol: str, name: str, logo_url: str | None = None) -> None:
        with self._connect() as conn:
            conn.execute("INSERT OR REPLACE INTO asset_metadata (symbol, name, logo_url, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)", (symbol, name, logo_url))

    def get_asset_metadata(self, symbol: str) -> dict | None:
        return self._query_one("SELECT * FROM asset_metadata WHERE symbol = ?", (symbol,))

    def get_all_metadata(self) -> dict[str, dict]:
        rows = self._query("SELECT * FROM asset_metadata")
        return {r["symbol"]: r for r in rows}

    # -- OHLCV --
    def save_ohlcv(self, symbol: str, df: pd.DataFrame) -> None:
        if df.empty: return
        records = []
        for date, row in df.iterrows():
            date_str = pd.Timestamp(date).strftime("%Y-%m-%d")
            records.append((symbol, date_str, float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"]), float(row.get("volume", 0))))
        with self._connect() as conn:
            conn.executemany("INSERT OR REPLACE INTO ohlcv (symbol, date, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?)", records)

    def get_ohlcv(self, symbol: str, start: str | None = None, end: str | None = None) -> pd.DataFrame:
        query = "SELECT * FROM ohlcv WHERE symbol = ?"
        params = [symbol]
        if start: query += " AND date >= ?"; params.append(start)
        if end: query += " AND date <= ?"; params.append(end)
        query += " ORDER BY date"
        with self._connect() as conn:
            df = pd.read_sql_query(query, conn, params=params, index_col="date")
            df.index = pd.to_datetime(df.index)
            df.columns = [c.lower() for c in df.columns]
            return df

    def list_assets(self) -> list[dict]:
        return self._query("SELECT symbol, MIN(date) as start, MAX(date) as end, COUNT(*) as rows FROM ohlcv GROUP BY symbol ORDER BY symbol")

    def has_ohlcv(self, symbol: str) -> bool:
        row = self._query_one("SELECT COUNT(*) as count FROM ohlcv WHERE symbol = ?", (symbol,))
        return row["count"] > 0 if row else False

    def ohlcv_date_range(self, symbol: str) -> tuple[str, str] | None:
        row = self._query_one("SELECT MIN(date), MAX(date) FROM ohlcv WHERE symbol = ?", (symbol,))
        return (row["MIN(date)"], row["MAX(date)"]) if row and row["MIN(date)"] else None

    def clear_ohlcv(self, symbol: str | None = None) -> None:
        if symbol: self._query("DELETE FROM ohlcv WHERE symbol = ?", (symbol,))
        else: self._query("DELETE FROM ohlcv")

    # -- Backtest Results --
    def save_screen(self, strategy: str, universe: str, results: list[dict], timestamp: str | None = None) -> None:
        ts = timestamp or datetime.now().isoformat()
        records = [(ts, strategy, universe, r["symbol"], r["n_trades"], r["win_rate"], r["profit_factor"], r["sharpe"], r.get("net_return_pct", 0)) for r in results]
        with self._connect() as conn:
            conn.executemany("INSERT OR REPLACE INTO screens (timestamp, strategy, universe, symbol, n_trades, win_rate, profit_factor, sharpe, net_return_pct) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", records)

    def get_screens_filtered(self, strategy: str | None = None, universe: str | None = None, min_pf: float = 0.0) -> list[dict]:
        query = "SELECT * FROM screens WHERE profit_factor >= ?"
        params = [min_pf]
        if strategy: query += " AND strategy = ?"; params.append(strategy)
        if universe: query += " AND universe = ?"; params.append(universe)
        query += " GROUP BY strategy, symbol HAVING timestamp = MAX(timestamp) ORDER BY profit_factor DESC"
        return self._query(query, params)

    def save_validation(self, strategy: str, universe: str, symbol: str, results: dict, timestamp: str | None = None) -> None:
        ts = timestamp or datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute("INSERT OR REPLACE INTO validations (timestamp, strategy, universe, symbol, n_trades, win_rate, profit_factor, sharpe, net_return_pct, robustness_pct, stable, ttest_p, verdict) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (ts, strategy, universe, symbol, results["n_trades"], results["win_rate"], results["profit_factor"], results["sharpe"], results.get("net_return_pct", 0), results["robustness_pct"], 1 if results["stable"] else 0, results["ttest_p"], results["verdict"]))

    def get_validations_filtered(self, strategy: str | None = None, universe: str | None = None, verdict: str | None = None) -> list[dict]:
        query = "SELECT * FROM validations WHERE 1=1"
        params = []
        if strategy: query += " AND strategy = ?"; params.append(strategy)
        if universe: query += " AND universe = ?"; params.append(universe)
        if verdict: query += " AND verdict = ?"; params.append(verdict)
        query += " GROUP BY strategy, symbol HAVING timestamp = MAX(timestamp) ORDER BY profit_factor DESC"
        return self._query(query, params)

    # -- Paper Trading --
    def open_paper_position(self, strategy: str, symbol: str, date: str, price: float, shares: float) -> bool:
        try:
            with self._connect() as conn:
                conn.execute("INSERT INTO paper_positions (strategy, symbol, entry_date, entry_price, shares, status) VALUES (?, ?, ?, ?, ?, 'open')", (strategy, symbol, date, price, shares))
                return True
        except sqlite3.IntegrityError: return False

    def close_paper_position(self, strategy: str, symbol: str, date: str, price: float) -> dict | None:
        pos = self._query_one("SELECT * FROM paper_positions WHERE strategy = ? AND symbol = ? AND status = 'open'", (strategy, symbol))
        if not pos: return None
        pnl_dollars = (price - pos["entry_price"]) * pos["shares"]
        pnl_pct = (price / pos["entry_price"] - 1) * 100
        with self._connect() as conn:
            conn.execute("UPDATE paper_positions SET exit_date = ?, exit_price = ?, pnl_dollars = ?, pnl_pct = ?, status = 'closed' WHERE id = ?", (date, price, pnl_dollars, pnl_pct, pos["id"]))
        return self._query_one("SELECT * FROM paper_positions WHERE id = ?", (pos["id"],))

    def get_open_positions(self, strategy: str | None = None) -> list[dict]:
        query = "SELECT * FROM paper_positions WHERE status = 'open'"
        params = []
        if strategy: query += " AND strategy = ?"; params.append(strategy)
        return self._query(query, params)

    def get_closed_trades(self, strategy: str | None = None, symbol: str | None = None, limit: int = 50) -> list[dict]:
        query = "SELECT * FROM paper_positions WHERE status = 'closed'"
        params = []
        if strategy: query += " AND strategy = ?"; params.append(strategy)
        if symbol: query += " AND symbol = ?"; params.append(symbol)
        query += " ORDER BY exit_date DESC LIMIT ?"
        params.append(limit)
        return self._query(query, params)

    def get_paper_summary(self) -> dict:
        rows = self._query("SELECT * FROM paper_positions WHERE status = 'closed'")
        n_trades = len(rows)
        wins = sum(1 for r in rows if (r.get("pnl_dollars") or 0) > 0)
        total_pnl = sum(r.get("pnl_dollars") or 0 for r in rows)
        by_strategy = {}
        for r in rows:
            s = r["strategy"]; by_strategy.setdefault(s, {"pnl": 0, "trades": 0, "wins": 0})
            pnl = r.get("pnl_dollars") or 0
            by_strategy[s]["pnl"] += pnl; by_strategy[s]["trades"] += 1
            if pnl > 0: by_strategy[s]["wins"] += 1
        row = self._query_one("SELECT COUNT(*) as count FROM paper_positions WHERE status = 'open'")
        n_open = row["count"] if row else 0
        return {"n_trades": n_trades, "n_wins": wins, "win_rate": round(wins/n_trades*100, 1) if n_trades > 0 else 0.0, "total_pnl": round(total_pnl, 2), "n_open": n_open, "by_strategy": by_strategy}

    # -- Live Trades --
    def open_live_trade(self, strategy: str, symbol: str, entry_date: str, entry_price: float, shares: float, fees: float = 0, paper_position_id: int | None = None) -> bool:
        try:
            with self._connect() as conn:
                conn.execute("INSERT INTO live_trades (strategy, symbol, entry_date, entry_price, shares, fees_entry, paper_position_id, status) VALUES (?, ?, ?, ?, ?, ?, ?, 'open')", (strategy, symbol, entry_date, entry_price, shares, fees, paper_position_id))
                return True
        except sqlite3.IntegrityError: return False

    def close_live_trade(self, strategy: str, symbol: str, exit_date: str, exit_price: float, fees: float = 0) -> dict | None:
        trade = self._query_one("SELECT * FROM live_trades WHERE strategy = ? AND symbol = ? AND status = 'open'", (strategy, symbol))
        if not trade: return None
        pnl_dollars = (exit_price - trade["entry_price"]) * trade["shares"] - trade["fees_entry"] - fees
        pnl_pct = (pnl_dollars / (trade["entry_price"] * trade["shares"])) * 100
        with self._connect() as conn:
            conn.execute("UPDATE live_trades SET exit_date = ?, exit_price = ?, fees_exit = ?, pnl_dollars = ?, pnl_pct = ?, status = 'closed' WHERE id = ?", (exit_date, exit_price, fees, pnl_dollars, pnl_pct, trade["id"]))
        return self._query_one("SELECT * FROM live_trades WHERE id = ?", (trade["id"],))

    def delete_live_trade(self, trade_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM live_trades WHERE id = ?", (trade_id,))
            return cur.rowcount > 0

    def get_open_live_trades(self, strategy: str | None = None) -> list[dict]:
        query = "SELECT * FROM live_trades WHERE status = 'open'"
        params = []
        if strategy: query += " AND strategy = ?"; params.append(strategy)
        return self._query(query, params)

    def get_closed_live_trades(self, limit: int = 50) -> list[dict]:
        return self._query("SELECT * FROM live_trades WHERE status = 'closed' ORDER BY exit_date DESC LIMIT ?", (limit,))

    def get_live_summary(self) -> dict:
        rows = self._query("SELECT * FROM live_trades WHERE status = 'closed'")
        n_trades = len(rows); wins = sum(1 for r in rows if (r.get("pnl_dollars") or 0) > 0); total_pnl = sum(r.get("pnl_dollars") or 0 for r in rows)
        by_strategy = {}
        for r in rows:
            s = r["strategy"]; by_strategy.setdefault(s, {"pnl": 0, "trades": 0, "wins": 0})
            pnl = r.get("pnl_dollars") or 0
            by_strategy[s]["pnl"] += pnl; by_strategy[s]["trades"] += 1
            if pnl > 0: by_strategy[s]["wins"] += 1
        row = self._query_one("SELECT COUNT(*) as count FROM live_trades WHERE status = 'open'")
        n_open = row["count"] if row else 0
        return {"n_trades": n_trades, "n_wins": wins, "win_rate": round(wins/n_trades*100, 1) if n_trades > 0 else 0.0, "total_pnl": round(total_pnl, 2), "n_open": n_open, "by_strategy": by_strategy}

    # -- Logs & Journal --
    def log_signal(self, timestamp: str, strategy: str, symbol: str, signal: str, close_price: float | None = None, indicator_value: float | None = None, notes: str = "", details_json: str | None = None) -> None:
        with self._connect() as conn:
            conn.execute("INSERT INTO signal_log (timestamp, strategy, symbol, signal, close_price, indicator_value, notes, details_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (timestamp, strategy, symbol, signal, close_price, indicator_value, notes, details_json))

    def get_latest_signals(self, strategy: str | None = None) -> tuple[str | None, list[dict]]:
        query = "SELECT MAX(timestamp) FROM signal_log"
        row = self._query_one(query)
        ts = row["MAX(timestamp)"] if row else None
        if not ts: return None, []
        q = "SELECT * FROM signal_log WHERE timestamp = ?"
        p = [ts]
        if strategy: q += " AND strategy = ?"; p.append(strategy)
        return ts, self._query(q, p)

    def get_latest_price(self, symbol: str) -> float | None:
        row = self._query_one("SELECT close_price FROM signal_log WHERE symbol = ? AND close_price IS NOT NULL ORDER BY timestamp DESC LIMIT 1", (symbol,))
        return row["close_price"] if row else None

    def get_latest_prices(self, symbols: list[str]) -> dict[str, float]:
        if not symbols: return {}
        placeholders = ",".join("?" for _ in symbols)
        query = f"SELECT symbol, close_price FROM signal_log WHERE symbol IN ({placeholders}) GROUP BY symbol HAVING timestamp = MAX(timestamp)"
        rows = self._query(query, symbols)
        return {r["symbol"]: r["close_price"] for r in rows}

    def get_signal_history(self, strategy: str | None = None, symbol: str | None = None, signal_type: str | None = None, days: int = 30) -> list[dict]:
        query = "SELECT * FROM signal_log WHERE timestamp >= datetime('now', ?)"
        params = [f"-{days} days"]
        if strategy: query += " AND strategy = ?"; params.append(strategy)
        if symbol: query += " AND symbol = ?"; params.append(symbol)
        if signal_type: query += " AND signal = ?"; params.append(signal_type)
        query += " ORDER BY timestamp DESC"
        return self._query(query, params)

    def update_paper_entry(self, id: int, notes: str | None = None, tags: str | None = None, sentiment: str | None = None) -> bool:
        updates = []; params = []
        if notes is not None: updates.append("notes = ?"); params.append(notes)
        if tags is not None: updates.append("tags = ?"); params.append(tags)
        if sentiment is not None: updates.append("sentiment = ?"); params.append(sentiment)
        if not updates: return True
        params.append(id); query = f"UPDATE paper_positions SET {', '.join(updates)} WHERE id = ?"
        with self._connect() as conn: return conn.execute(query, params).rowcount > 0

    def update_live_entry(self, id: int, notes: str | None = None, tags: str | None = None, sentiment: str | None = None) -> bool:
        updates = []; params = []
        if notes is not None: updates.append("notes = ?"); params.append(notes)
        if tags is not None: updates.append("tags = ?"); params.append(tags)
        if sentiment is not None: updates.append("sentiment = ?"); params.append(sentiment)
        if not updates: return True
        params.append(id); query = f"UPDATE live_trades SET {', '.join(updates)} WHERE id = ?"
        with self._connect() as conn: return conn.execute(query, params).rowcount > 0

    def get_journal_entries(self, strategy: str | None = None, symbol: str | None = None, source: str | None = None, search: str | None = None, limit: int = 50) -> dict:
        entries = []
        with self._connect() as conn:
            # Use query method to get dicts directly
            conn.row_factory = sqlite3.Row
            
            # Fetch paper
            if source != 'live':
                q = "SELECT * FROM paper_positions WHERE 1=1"
                p = []
                if strategy: q += " AND strategy = ?"; p.append(strategy)
                if symbol: q += " AND symbol = ?"; p.append(symbol)
                for d in [dict(r) for r in conn.execute(q, p).fetchall()]:
                    entries.append({"id": d["id"], "source": "paper", "strategy": d["strategy"], "symbol": d["symbol"], "status": d["status"], "entry_date": d["entry_date"], "entry_price": d["entry_price"], "exit_date": d.get("exit_date"), "exit_price": d.get("exit_price"), "shares": d["shares"], "fees": 0, "pnl_dollars": d.get("pnl_dollars"), "pnl_pct": d.get("pnl_pct"), "notes": d.get("notes") or "", "tags": d.get("tags") or "", "sentiment": d.get("sentiment") or "", "holding_days": None, "signal_details": None, "slippage": None})
            
            # Fetch live
            if source != 'paper':
                q = "SELECT * FROM live_trades WHERE 1=1"
                p = []
                if strategy: q += " AND strategy = ?"; p.append(strategy)
                if symbol: q += " AND symbol = ?"; p.append(symbol)
                for d in [dict(r) for r in conn.execute(q, p).fetchall()]:
                    entries.append({"id": d["id"], "source": "live", "strategy": d["strategy"], "symbol": d["symbol"], "status": d["status"], "entry_date": d["entry_date"], "entry_price": d["entry_price"], "exit_date": d.get("exit_date"), "exit_price": d.get("exit_price"), "shares": d["shares"], "fees": (d.get("fees_entry") or 0) + (d.get("fees_exit") or 0), "pnl_dollars": d.get("pnl_dollars"), "pnl_pct": d.get("pnl_pct"), "notes": d.get("notes") or "", "tags": d.get("tags") or "", "sentiment": d.get("sentiment") or "", "paper_position_id": d.get("paper_position_id"), "holding_days": None, "signal_details": None, "slippage": None})
            
            if search:
                s = search.lower()
                entries = [e for e in entries if s in e["symbol"].lower() or s in e["notes"].lower() or (e["tags"] and s in e["tags"].lower())]
            
            entries.sort(key=lambda x: x["entry_date"], reverse=True)
            total = len(entries)
            entries = entries[:limit]
            
            closed = [e for e in entries if e["status"] == "closed"]
            wins = sum(1 for e in closed if (e["pnl_dollars"] or 0) > 0)
            total_pnl = sum(e["pnl_dollars"] or 0 for e in closed)
            
            return {
                "entries": entries, 
                "total": total, 
                "stats": {
                    "total_trades": total, 
                    "open_trades": total - len(closed), 
                    "closed_trades": len(closed), 
                    "wins": wins, 
                    "win_rate": round(wins/len(closed)*100, 1) if closed else 0.0, 
                    "total_pnl": round(total_pnl, 2)
                }
            }
