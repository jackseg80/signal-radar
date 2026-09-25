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
        self._backup_before_v2()
        self._backup_before_price_basis_upgrade()
        self._init_db()

    def _backup_before_price_basis_upgrade(self) -> None:
        """Snapshot legacy split-adjusted price rows before Yahoo refreshes them."""
        backup_path = self.db_path.with_suffix(
            self.db_path.suffix + ".pre-price-basis.bak"
        )
        if backup_path.exists():
            return
        if not self.db_path.exists() or self.db_path.stat().st_size == 0:
            return
        with sqlite3.connect(self.db_path, timeout=SQLITE_TIMEOUT) as source:
            present = source.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='prices_v2'"
            ).fetchone()
            if not present:
                return
            columns = {
                row[1] for row in source.execute("PRAGMA table_info(prices_v2)")
            }
            legacy_query = (
                "SELECT 1 FROM prices_v2 WHERE price_basis_version<>2 LIMIT 1"
                if "price_basis_version" in columns
                else "SELECT 1 FROM prices_v2 LIMIT 1"
            )
            if source.execute(legacy_query).fetchone():
                with sqlite3.connect(backup_path) as target:
                    source.backup(target)

    def _backup_before_v2(self) -> None:
        """Keep a consistent one-time copy before adding the decision schema."""
        if not self.db_path.exists() or self.db_path.stat().st_size == 0:
            return
        backup_path = self.db_path.with_suffix(self.db_path.suffix + ".pre-v2.bak")
        if backup_path.exists():
            return
        with sqlite3.connect(self.db_path, timeout=SQLITE_TIMEOUT) as source:
            existing = source.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='paper_positions'"
            ).fetchone()
            migrated = source.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='scanner_sessions'"
            ).fetchone()
            if existing and not migrated:
                with sqlite3.connect(backup_path) as target:
                    source.backup(target)

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
            # Version 2 is deliberately separate: historical paper trades stay readable
            # and cannot contaminate the new portfolio's cash or P&L.
            conn.execute("""CREATE TABLE IF NOT EXISTS scanner_sessions (
                source_session TEXT PRIMARY KEY,
                target_session TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                status TEXT NOT NULL,
                error TEXT
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS account_confirmations (
                source_session TEXT PRIMARY KEY,
                confirmed_at TEXT NOT NULL,
                cash_usd REAL NOT NULL CHECK(cash_usd >= 0),
                holdings_json TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT ''
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS signal_decisions (
                source_session TEXT NOT NULL,
                strategy TEXT NOT NULL,
                symbol TEXT NOT NULL,
                target_session TEXT NOT NULL,
                technical_signal TEXT NOT NULL,
                eligibility TEXT NOT NULL,
                reasons_json TEXT NOT NULL,
                details_json TEXT,
                note TEXT,
                score REAL,
                max_budget_usd REAL,
                indicative_shares INTEGER,
                close_price REAL,
                indicator_value REAL,
                expires_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (source_session, strategy, symbol)
            )""")
            for field in ("details_json", "note"):
                try:
                    conn.execute(f"ALTER TABLE signal_decisions ADD COLUMN {field} TEXT")
                except sqlite3.OperationalError:
                    pass
            conn.execute("""CREATE TABLE IF NOT EXISTS paper_orders_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_session TEXT NOT NULL,
                target_session TEXT NOT NULL,
                strategy TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL CHECK(side IN ('BUY', 'SELL')),
                status TEXT NOT NULL DEFAULT 'pending',
                budget_usd REAL,
                indicative_shares INTEGER,
                filled_price REAL,
                filled_shares INTEGER,
                fee_usd REAL,
                reason TEXT NOT NULL DEFAULT '',
                UNIQUE(target_session, symbol, side)
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS paper_positions_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy TEXT NOT NULL,
                symbol TEXT NOT NULL,
                entry_session TEXT NOT NULL,
                entry_price REAL NOT NULL,
                shares INTEGER NOT NULL,
                cost_basis REAL NOT NULL,
                entry_fee REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                exit_session TEXT,
                exit_price REAL,
                exit_fee REAL,
                pnl_dollars REAL,
                dividend_cash REAL NOT NULL DEFAULT 0,
                notes TEXT NOT NULL DEFAULT '',
                tags TEXT,
                sentiment TEXT,
                UNIQUE(strategy, symbol, entry_session)
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS paper_actions_v2 (
                position_id INTEGER NOT NULL,
                session TEXT NOT NULL,
                dividend_cash REAL NOT NULL,
                split REAL NOT NULL,
                PRIMARY KEY(position_id, session)
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS paper_dividend_payments_v2 (
                position_id INTEGER NOT NULL,
                ex_session TEXT NOT NULL,
                pay_session TEXT NOT NULL,
                net_amount_usd REAL NOT NULL CHECK(net_amount_usd >= 0),
                confirmed_at TEXT NOT NULL,
                PRIMARY KEY(position_id, ex_session)
            )""")
            # Independent virtual signal study; never enters paper or Saxo cash.
            conn.execute("""CREATE TABLE IF NOT EXISTS signal_follow_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_session TEXT NOT NULL,
                target_session TEXT NOT NULL,
                strategy TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL CHECK(side IN ('BUY','SELL')),
                position_id INTEGER,
                status TEXT NOT NULL DEFAULT 'pending',
                notional_usd REAL NOT NULL DEFAULT 5000,
                filled_price REAL,
                filled_shares INTEGER,
                fee_usd REAL,
                reason TEXT NOT NULL DEFAULT '',
                UNIQUE(source_session,strategy,symbol,side)
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS signal_follow_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy TEXT NOT NULL,
                symbol TEXT NOT NULL,
                source_session TEXT NOT NULL,
                entry_session TEXT NOT NULL,
                entry_price REAL NOT NULL,
                shares REAL NOT NULL,
                cost_basis REAL NOT NULL,
                entry_fee REAL NOT NULL,
                dividend_cash REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'open',
                exit_session TEXT,
                exit_price REAL,
                exit_fee REAL,
                pnl_dollars REAL,
                UNIQUE(strategy,symbol,source_session)
            )""")
            conn.execute("""CREATE UNIQUE INDEX IF NOT EXISTS
                idx_signal_follow_one_open ON signal_follow_positions(strategy,symbol)
                WHERE status='open'""")
            conn.execute("""CREATE TABLE IF NOT EXISTS signal_follow_actions (
                position_id INTEGER NOT NULL,
                session TEXT NOT NULL,
                dividend_cash REAL NOT NULL,
                split REAL NOT NULL,
                PRIMARY KEY(position_id,session)
            )""")
            for field, sql_type in (
                ("notes", "TEXT NOT NULL DEFAULT ''"),
                ("tags", "TEXT"), ("sentiment", "TEXT"),
            ):
                try:
                    conn.execute(f"ALTER TABLE paper_positions_v2 ADD COLUMN {field} {sql_type}")
                except sqlite3.OperationalError:
                    pass
            conn.execute("""CREATE TABLE IF NOT EXISTS prices_v2 (
                symbol TEXT NOT NULL,
                date TEXT NOT NULL,
                raw_open REAL NOT NULL,
                raw_high REAL NOT NULL,
                raw_low REAL NOT NULL,
                raw_close REAL NOT NULL,
                adj_open REAL NOT NULL,
                adj_high REAL NOT NULL,
                adj_low REAL NOT NULL,
                adj_close REAL NOT NULL,
                volume REAL NOT NULL,
                dividend REAL NOT NULL DEFAULT 0,
                split REAL NOT NULL DEFAULT 0,
                price_basis_version INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY(symbol, date)
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS price_repairs_v2 (
                symbol TEXT NOT NULL,
                date TEXT NOT NULL,
                source_url TEXT NOT NULL,
                verified_at TEXT NOT NULL,
                previous_close REAL NOT NULL,
                next_close REAL NOT NULL,
                raw_open REAL NOT NULL,
                raw_high REAL NOT NULL,
                raw_low REAL NOT NULL,
                raw_close REAL NOT NULL,
                volume REAL NOT NULL,
                applied_at TEXT NOT NULL,
                PRIMARY KEY(symbol,date)
            )""")
            try:
                conn.execute("ALTER TABLE prices_v2 ADD COLUMN price_basis_version INTEGER NOT NULL DEFAULT 1")
            except sqlite3.OperationalError:
                pass
            conn.execute("""CREATE TABLE IF NOT EXISTS strategy_scores (
                strategy TEXT NOT NULL,
                symbol TEXT NOT NULL,
                asof_session TEXT NOT NULL,
                n_trades INTEGER NOT NULL,
                monthly_lower_bound REAL,
                max_drawdown REAL,
                calibrated INTEGER NOT NULL DEFAULT 0,
                verdict TEXT NOT NULL DEFAULT 'PENDING',
                train_p_adjusted REAL,
                holdout_monthly_return REAL,
                scope TEXT NOT NULL DEFAULT 'production',
                PRIMARY KEY(strategy, symbol, asof_session)
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS observation_period (
                id INTEGER PRIMARY KEY CHECK(id=1),
                start_session TEXT NOT NULL,
                started_at TEXT NOT NULL
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS observation_checks (
                source_session TEXT NOT NULL,
                symbol TEXT NOT NULL,
                saxo_open REAL NOT NULL CHECK(saxo_open>0),
                execution_price REAL CHECK(execution_price>0),
                actual_fees_usd REAL CHECK(actual_fees_usd>=0),
                notes TEXT NOT NULL DEFAULT '',
                confirmed_at TEXT NOT NULL,
                PRIMARY KEY(source_session,symbol)
            )""")
            for field, sql_type in (
                ("verdict", "TEXT NOT NULL DEFAULT 'PENDING'"),
                ("train_p_adjusted", "REAL"),
                ("holdout_monthly_return", "REAL"),
                ("scope", "TEXT NOT NULL DEFAULT 'production'"),
            ):
                try:
                    conn.execute(f"ALTER TABLE strategy_scores ADD COLUMN {field} {sql_type}")
                except sqlite3.OperationalError:
                    pass
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
        # Case-insensitive column access
        df_cols = {c.lower(): c for c in df.columns}
        def get_val(row, col_name):
            real_col = df_cols.get(col_name.lower())
            return float(row[real_col]) if real_col else 0.0

        records = []
        for date, row in df.iterrows():
            date_str = pd.Timestamp(date).strftime("%Y-%m-%d")
            records.append((
                symbol, 
                date_str, 
                get_val(row, "open"), 
                get_val(row, "high"), 
                get_val(row, "low"), 
                get_val(row, "close"), 
                get_val(row, "volume")
            ))
        with self._connect() as conn:
            conn.executemany("INSERT OR REPLACE INTO ohlcv (symbol, date, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?)", records)

    def get_ohlcv(self, symbol: str, start: str | None = None, end: str | None = None) -> pd.DataFrame:
        query = "SELECT open as Open, high as High, low as Low, close as Close, volume as Volume FROM ohlcv WHERE symbol = ?"
        params = [symbol]
        if start: query += " AND date >= ?"; params.append(start)
        if end: query += " AND date <= ?"; params.append(end)
        query += " ORDER BY date"
        with self._connect() as conn:
            df = pd.read_sql_query(query, conn, params=params, index_col=None)
            # Fetch date separately to avoid index name issues or just re-read with index
            df = pd.read_sql_query(query.replace("open as", "date, open as"), conn, params=params, index_col="date")
            df.index = pd.to_datetime(df.index)
            df["Adj_Close"] = df["Close"]
            return df[["Open", "High", "Low", "Close", "Volume", "Adj_Close"]]

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

    def get_best_assets(self, strategy: str, universe: str | None = None, min_pf: float = 0.0, source: str = "screens") -> list[dict]:
        table = "screens" if source == "screens" else "validations"
        query = f"SELECT * FROM {table} WHERE strategy = ? AND profit_factor >= ?"
        params = [strategy, min_pf]
        if universe: query += " AND universe = ?"; params.append(universe)
        query += " GROUP BY symbol HAVING timestamp = MAX(timestamp) ORDER BY profit_factor DESC"
        return self._query(query, params)

    def get_strategies(self, source: str = "screens") -> list[str]:
        table = "screens" if source == "screens" else "validations"
        rows = self._query(f"SELECT DISTINCT strategy FROM {table}")
        return [r["strategy"] for r in rows]

    def get_universes(self, source: str = "screens") -> list[str]:
        table = "screens" if source == "screens" else "validations"
        rows = self._query(f"SELECT DISTINCT universe FROM {table}")
        return [r["universe"] for r in rows]

    def compare_strategies(self, strategies: list[str], universe: str | None = None, source: str = "screens") -> list[dict]:
        if not strategies: return []
        table = "screens" if source == "screens" else "validations"
        # Get all symbols for these strategies/universe
        query = f"SELECT DISTINCT symbol FROM {table} WHERE strategy IN ({','.join('?' for _ in strategies)})"
        params = list(strategies)
        if universe: query += " AND universe = ?"; params.append(universe)
        symbols = [r["symbol"] for r in self._query(query, params)]
        
        results = []
        for sym in symbols:
            r = {"symbol": sym}
            for s in strategies:
                row = self._query_one(f"SELECT profit_factor FROM {table} WHERE strategy = ? AND symbol = ? ORDER BY timestamp DESC LIMIT 1", (s, sym))
                if row: r[f"{s}_pf"] = row["profit_factor"]
            results.append(r)
        return sorted(results, key=lambda x: sum(1 for s in strategies if x.get(f"{s}_pf", 0) > 1.2), reverse=True)

    def get_cross_strategy(self, symbol: str) -> list[dict]:
        screens = self._query("SELECT *, 'screens' as source FROM screens WHERE symbol = ? GROUP BY strategy HAVING timestamp = MAX(timestamp)", (symbol,))
        validations = self._query("SELECT *, 'validations' as source FROM validations WHERE symbol = ? GROUP BY strategy HAVING timestamp = MAX(timestamp)", (symbol,))
        return sorted(screens + validations, key=lambda x: x["profit_factor"], reverse=True)

    def count(self, table: str = "screens") -> int:
        if table not in ["screens", "validations", "ohlcv", "signal_log"]: return 0
        row = self._query_one(f"SELECT COUNT(*) as count FROM {table}")
        return row["count"] if row else 0

    # -- Paper Trading --
    def open_paper_position(self, strategy: str, symbol: str, date: str, price: float, shares: float) -> bool:
        # Business logic: only one open position per strategy/symbol
        existing = self._query_one("SELECT id FROM paper_positions WHERE strategy = ? AND symbol = ? AND status = 'open'", (strategy, symbol))
        if existing: return False
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

    def clear_paper_positions(self, strategy: str | None = None) -> int:
        query = "DELETE FROM paper_positions WHERE status = 'open'"
        params = []
        if strategy: query += " AND strategy = ?"; params.append(strategy)
        with self._connect() as conn:
            cur = conn.execute(query, params)
            return cur.rowcount

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
    def open_live_trade(self, strategy: str, symbol: str, entry_date: str, entry_price: float, shares: float, fees: float = 0, notes: str = "", paper_position_id: int | None = None) -> bool:
        try:
            with self._connect() as conn:
                conn.execute("INSERT INTO live_trades (strategy, symbol, entry_date, entry_price, shares, fees_entry, notes, paper_position_id, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open')", (strategy, symbol, entry_date, entry_price, shares, fees, notes, paper_position_id))
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

    def get_closed_live_trades(self, strategy: str | None = None, symbol: str | None = None, limit: int = 50) -> list[dict]:
        query = "SELECT * FROM live_trades WHERE status = 'closed'"
        params = []
        if strategy: query += " AND strategy = ?"; params.append(strategy)
        if symbol: query += " AND symbol = ?"; params.append(symbol)
        query += " ORDER BY exit_date DESC LIMIT ?"
        params.append(limit)
        return self._query(query, params)

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
        source, decisions = self.get_latest_decisions()
        if source is not None:
            from engine.trading_calendar import is_expired

            rows = []
            for item in decisions:
                if strategy and item["strategy"] != strategy:
                    continue
                expired = is_expired(item["target_session"])
                technical = item["technical_signal"]
                actionable = item["eligibility"] == "ELIGIBLE" and not expired
                signal = (
                    "BUY" if technical == "BUY" and actionable else
                    "SKIP" if technical == "BUY" or technical == "DATA_MISSING" else
                    technical
                )
                reasons = list(item["reasons"])
                if expired and technical == "BUY":
                    reasons.append("target opening has passed")
                rows.append({
                    "timestamp": source, "strategy": item["strategy"],
                    "symbol": item["symbol"], "signal": signal,
                    "close_price": item["close_price"],
                    "indicator_value": item["indicator_value"],
                    "notes": "; ".join(reasons) or item.get("note") or "",
                    "details_json": json.dumps(item["details"]),
                    "source_session": source,
                    "target_session": item["target_session"],
                    "technical_signal": technical,
                    "eligibility": "EXPIRED" if expired and technical == "BUY" else item["eligibility"],
                    "reasons": reasons,
                    "expires_at": item["expires_at"],
                    "max_budget_usd": item["max_budget_usd"],
                    "indicative_shares": item["indicative_shares"],
                    "score": item["score"],
                    "paper_signal": item["details"].get("paper_signal"),
                    "paper_status": item["details"].get("paper_status"),
                    "follow_signal": item["details"].get("follow_signal"),
                    "follow_status": item["details"].get("follow_status"),
                    "paper_reasons": item["details"].get("paper_reasons", []),
                    "paper_warnings": item["details"].get("paper_warnings", []),
                    "paper_budget_usd": item["details"].get("paper_budget_usd"),
                    "paper_indicative_shares": item["details"].get("paper_indicative_shares"),
                })
            return source, rows
        query = "SELECT MAX(timestamp) FROM signal_log"
        row = self._query_one(query)
        ts = row["MAX(timestamp)"] if row else None
        if not ts: return None, []
        q = "SELECT * FROM signal_log WHERE timestamp = ?"
        p = [ts]
        if strategy: q += " AND strategy = ?"; p.append(strategy)
        legacy_rows = self._query(q, p)
        for item in legacy_rows:
            item["technical_signal"] = item["signal"]
            if item["signal"] == "BUY":
                item["signal"] = "SKIP"
                item["notes"] = "Ancien modèle non vérifié ; achat bloqué"
                item["eligibility"] = "LEGACY"
        return ts, legacy_rows

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
        rows = self._query(query, params)
        for item in rows:
            item["technical_signal"] = item["signal"]
            item["series"] = "ancien modèle"
            if item["signal"] == "BUY":
                item["signal"] = "SKIP"
                item["eligibility"] = "LEGACY"
        return rows

    def update_paper_entry(self, id: int, notes: str | None = None, tags: str | None = None, sentiment: str | None = None) -> bool:
        updates = []; params = []
        if notes is not None: updates.append("notes = ?"); params.append(notes)
        if tags is not None: updates.append("tags = ?"); params.append(tags)
        if sentiment is not None: updates.append("sentiment = ?"); params.append(sentiment)
        if not updates: return True
        params.append(id); query = f"UPDATE paper_positions SET {', '.join(updates)} WHERE id = ?"
        with self._connect() as conn: return conn.execute(query, params).rowcount > 0

    def update_paper_notes(self, id: int, notes: str) -> bool:
        return self.update_paper_entry(id, notes=notes)

    def update_live_entry(self, id: int, notes: str | None = None, tags: str | None = None, sentiment: str | None = None) -> bool:
        updates = []; params = []
        if notes is not None: updates.append("notes = ?"); params.append(notes)
        if tags is not None: updates.append("tags = ?"); params.append(tags)
        if sentiment is not None: updates.append("sentiment = ?"); params.append(sentiment)
        if not updates: return True
        params.append(id); query = f"UPDATE live_trades SET {', '.join(updates)} WHERE id = ?"
        with self._connect() as conn: return conn.execute(query, params).rowcount > 0

    def update_live_notes(self, id: int, notes: str) -> bool:
        return self.update_live_entry(id, notes=notes)

    def get_journal_entries(self, strategy: str | None = None, symbol: str | None = None, source: str | None = None, search: str | None = None, limit: int = 50) -> dict:
        entries = []
        with self._connect() as conn:
            # Use query method to get dicts directly
            conn.row_factory = sqlite3.Row
            
            # Fetch paper
            if source in (None, 'legacy_paper'):
                q = "SELECT * FROM paper_positions WHERE 1=1"
                p = []
                if strategy: q += " AND strategy = ?"; p.append(strategy)
                if symbol: q += " AND symbol = ?"; p.append(symbol)
                for d in [dict(r) for r in conn.execute(q, p).fetchall()]:
                    # Attach latest signal log context
                    sig = self._query_one("SELECT details_json FROM signal_log WHERE strategy = ? AND symbol = ? ORDER BY timestamp DESC LIMIT 1", (d["strategy"], d["symbol"]))
                    signal_details = json.loads(sig["details_json"]) if sig and sig["details_json"] else None
                    entries.append({"id": d["id"], "source": "legacy_paper", "series": "ancien modèle", "read_only": True, "strategy": d["strategy"], "symbol": d["symbol"], "status": d["status"], "entry_date": d["entry_date"], "entry_price": d["entry_price"], "exit_date": d.get("exit_date"), "exit_price": d.get("exit_price"), "shares": d["shares"], "fees": 0, "pnl_dollars": d.get("pnl_dollars"), "pnl_pct": d.get("pnl_pct"), "notes": d.get("notes") or "", "tags": d.get("tags") or "", "sentiment": d.get("sentiment") or "", "holding_days": None, "signal_details": signal_details, "slippage": None})
            
            # New paper series remains separate from the read-only archive.
            if source in (None, 'paper'):
                q = "SELECT * FROM paper_positions_v2 WHERE 1=1"
                p = []
                if strategy: q += " AND strategy = ?"; p.append(strategy)
                if symbol: q += " AND symbol = ?"; p.append(symbol)
                for d in [dict(r) for r in conn.execute(q, p).fetchall()]:
                    pnl = d.get("pnl_dollars")
                    entries.append({
                        "id": d["id"], "source": "paper", "series": "next_open_v2",
                        "read_only": False, "strategy": d["strategy"],
                        "symbol": d["symbol"], "status": d["status"],
                        "entry_date": d["entry_session"],
                        "entry_price": d["entry_price"],
                        "exit_date": d.get("exit_session"),
                        "exit_price": d.get("exit_price"),
                        "shares": d["shares"],
                        "fees": d["entry_fee"] + (d.get("exit_fee") or 0),
                        "pnl_dollars": pnl,
                        "pnl_pct": 100 * pnl / d["cost_basis"] if pnl is not None else None,
                        "notes": d.get("notes") or "",
                        "tags": d.get("tags") or "",
                        "sentiment": d.get("sentiment") or "",
                        "holding_days": None, "signal_details": None,
                        "slippage": None,
                    })

            # Fetch live
            if source != 'paper':
                q = "SELECT * FROM live_trades WHERE 1=1"
                p = []
                if strategy: q += " AND strategy = ?"; p.append(strategy)
                if symbol: q += " AND symbol = ?"; p.append(symbol)
                for d in [dict(r) for r in conn.execute(q, p).fetchall()]:
                    # Attach latest signal log context
                    sig = self._query_one("SELECT details_json FROM signal_log WHERE strategy = ? AND symbol = ? ORDER BY timestamp DESC LIMIT 1", (d["strategy"], d["symbol"]))
                    signal_details = json.loads(sig["details_json"]) if sig and sig["details_json"] else None
                    entries.append({"id": d["id"], "source": "live", "strategy": d["strategy"], "symbol": d["symbol"], "status": d["status"], "entry_date": d["entry_date"], "entry_price": d["entry_price"], "exit_date": d.get("exit_date"), "exit_price": d.get("exit_price"), "shares": d["shares"], "fees": (d.get("fees_entry") or 0) + (d.get("fees_exit") or 0), "pnl_dollars": d.get("pnl_dollars"), "pnl_pct": d.get("pnl_pct"), "notes": d.get("notes") or "", "tags": d.get("tags") or "", "sentiment": d.get("sentiment") or "", "paper_position_id": d.get("paper_position_id"), "holding_days": None, "signal_details": signal_details, "slippage": None})
            
            if search:
                s = search.lower()
                entries = [e for e in entries if s in e["symbol"].lower() or s in e["notes"].lower() or (e["tags"] and s in e["tags"].lower())]
            
            entries.sort(key=lambda x: x["entry_date"], reverse=True)
            total = len(entries)
            entries = entries[:limit]
            
            current_entries = [e for e in entries if e["source"] != "legacy_paper"]
            closed = [e for e in current_entries if e["status"] == "closed"]
            wins = sum(1 for e in closed if (e["pnl_dollars"] or 0) > 0)
            total_pnl = sum(e["pnl_dollars"] or 0 for e in closed)
            
            return {
                "entries": entries, 
                "total": total, 
                "stats": {
                    "total_trades": len(current_entries),
                    "open_trades": len(current_entries) - len(closed),
                    "closed_trades": len(closed), 
                    "wins": wins, 
                    "win_rate": round(wins/len(closed)*100, 1) if closed else 0.0, 
                    "total_pnl": round(total_pnl, 2)
                },
                "legacy_stats": {
                    "total_trades": sum(e["source"] == "legacy_paper" for e in entries),
                    "total_pnl": round(sum(e["pnl_dollars"] or 0 for e in entries
                                           if e["source"] == "legacy_paper"), 2),
                },
            }

    # -- Decision and paper portfolio v2 --
    def confirm_account(
        self, source_session: str, cash_usd: float, holdings: list[str], note: str = "",
    ) -> dict:
        """Record a dated, explicit Saxo cash and holdings confirmation."""
        if cash_usd < 0:
            raise ValueError("cash_usd must be non-negative")
        normalized = sorted({s.strip().upper() for s in holdings if s.strip()})
        now = datetime.now().astimezone().isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO account_confirmations VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(source_session) DO UPDATE SET confirmed_at=excluded.confirmed_at, "
                "cash_usd=excluded.cash_usd, holdings_json=excluded.holdings_json, note=excluded.note",
                (source_session, now, cash_usd, json.dumps(normalized), note),
            )
        return self.get_account_confirmation(source_session) or {}

    def get_account_confirmation(self, source_session: str) -> dict | None:
        """Get only the confirmation for the exact signal session."""
        row = self._query_one(
            "SELECT * FROM account_confirmations WHERE source_session = ?", (source_session,)
        )
        if row:
            row["holdings"] = json.loads(row.pop("holdings_json"))
        return row

    def upsert_scanner_session(
        self, source_session: str, target_session: str, status: str,
        error: str | None = None,
    ) -> None:
        """Keep one scanner run record per exchange session."""
        now = datetime.now().astimezone().isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO scanner_sessions VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(source_session) DO UPDATE SET target_session=excluded.target_session, "
                "completed_at=excluded.completed_at, status=excluded.status, error=excluded.error",
                (source_session, target_session, now, now if status != "running" else None,
                 status, error),
            )

    def upsert_decision(self, row: dict) -> None:
        """Store a technical signal and its independently audited eligibility."""
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO signal_decisions
                (source_session, strategy, symbol, target_session, technical_signal,
                 eligibility, reasons_json, details_json, note, score, max_budget_usd, indicative_shares,
                 close_price, indicator_value, expires_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_session, strategy, symbol) DO UPDATE SET
                 technical_signal=excluded.technical_signal,
                 eligibility=excluded.eligibility, reasons_json=excluded.reasons_json,
                 details_json=excluded.details_json, note=excluded.note,
                 score=excluded.score, max_budget_usd=excluded.max_budget_usd,
                 indicative_shares=excluded.indicative_shares,
                 close_price=excluded.close_price,
                 indicator_value=excluded.indicator_value,
                 expires_at=excluded.expires_at, updated_at=excluded.updated_at""",
                (row["source_session"], row["strategy"], row["symbol"],
                 row["target_session"], row["technical_signal"], row["eligibility"],
                 json.dumps(row.get("reasons", [])), json.dumps(row.get("details", {})),
                 row.get("note"), row.get("score"),
                 row.get("max_budget_usd"), row.get("indicative_shares"),
                 row.get("close_price"), row.get("indicator_value"),
                 row["expires_at"], datetime.now().astimezone().isoformat()),
            )

    def get_latest_decisions(self) -> tuple[str | None, list[dict]]:
        """Read the latest exchange session, not the latest individual timestamp."""
        row = self._query_one("SELECT MAX(source_session) AS session FROM scanner_sessions")
        session = row["session"] if row else None
        if session is None:
            return None, []
        rows = self._query(
            "SELECT * FROM signal_decisions WHERE source_session=? ORDER BY strategy, symbol",
            (session,),
        )
        for item in rows:
            item["reasons"] = json.loads(item.pop("reasons_json"))
            item["details"] = json.loads(item.pop("details_json") or "{}")
        return session, rows

    def get_v2_open_positions(self) -> list[dict]:
        """Return only positions of the new single paper portfolio."""
        return self._query("SELECT * FROM paper_positions_v2 WHERE status='open'")

    def get_v2_closed_trades(self, limit: int = 1000) -> list[dict]:
        """Return closed trades of the new portfolio only."""
        return self._query(
            "SELECT * FROM paper_positions_v2 WHERE status='closed' "
            "ORDER BY exit_session DESC LIMIT ?", (limit,),
        )

    def get_v2_paper_summary(self) -> dict:
        """Aggregate only next-open v2 trades and show reserved cash."""
        rows = self.get_v2_closed_trades()
        wins = sum((row["pnl_dollars"] or 0) > 0 for row in rows)
        by_strategy: dict[str, dict] = {}
        for row in rows:
            item = by_strategy.setdefault(
                row["strategy"], {"pnl": 0.0, "trades": 0, "wins": 0}
            )
            item["pnl"] += row["pnl_dollars"] or 0.0
            item["trades"] += 1
            item["wins"] += int((row["pnl_dollars"] or 0) > 0)
        pending_dividends = self._query_one(
            """SELECT COALESCE(SUM(a.dividend_cash),0) AS amount
            FROM paper_actions_v2 a LEFT JOIN paper_dividend_payments_v2 p
            ON p.position_id=a.position_id AND p.ex_session=a.session
            WHERE p.position_id IS NULL"""
        )
        payments = self._query(
            """SELECT p.net_amount_usd, x.strategy FROM paper_dividend_payments_v2 p
            JOIN paper_positions_v2 x ON x.id=p.position_id"""
        )
        for payment in payments:
            by_strategy.setdefault(
                payment["strategy"], {"pnl": 0.0, "trades": 0, "wins": 0}
            )["pnl"] += payment["net_amount_usd"]
        paid_total = sum(p["net_amount_usd"] for p in payments)
        return {
            "series": "next_open_v2", "initial_capital": 5000.0,
            "cash_available": round(self.get_v2_paper_cash(), 2),
            "n_trades": len(rows), "n_wins": wins,
            "win_rate": round(100 * wins / len(rows), 1) if rows else 0.0,
            "total_pnl": round(sum(row["pnl_dollars"] or 0 for row in rows) + paid_total, 2),
            "confirmed_dividends_usd": round(paid_total, 2),
            "n_open": len(self.get_v2_open_positions()),
            "pending_dividend_entitlements_usd": round(pending_dividends["amount"], 2),
            "by_strategy": by_strategy,
        }

    def update_v2_paper_entry(
        self, position_id: int, notes: str | None = None,
        tags: str | None = None, sentiment: str | None = None,
    ) -> bool:
        """Edit only the new paper series; legacy rows remain untouched."""
        updates: list[str] = []
        values: list[Any] = []
        for field, value in (("notes", notes), ("tags", tags),
                             ("sentiment", sentiment)):
            if value is not None:
                updates.append(f"{field}=?")
                values.append(value)
        if not updates:
            return True
        values.append(position_id)
        with self._connect() as conn:
            return conn.execute(
                f"UPDATE paper_positions_v2 SET {', '.join(updates)} WHERE id=?",
                values,
            ).rowcount > 0

    def get_pending_paper_orders(self) -> list[dict]:
        """Return queued orders that have not reached their target open."""
        return self._query(
            "SELECT * FROM paper_orders_v2 WHERE status='pending' ORDER BY target_session, id"
        )

    def get_v2_paper_cash(self) -> float:
        """Cash available after all filled entries, exits and pending buy reserves."""
        closed = self._query_one(
            "SELECT COALESCE(SUM(pnl_dollars), 0) AS amount FROM paper_positions_v2 "
            "WHERE status='closed'"
        )
        invested = self._query_one(
            "SELECT COALESCE(SUM(cost_basis + entry_fee), 0) AS amount "
            "FROM paper_positions_v2 WHERE status='open'"
        )
        reserved = self._query_one(
            "SELECT COALESCE(SUM(budget_usd), 0) AS amount FROM paper_orders_v2 "
            "WHERE side='BUY' AND status='pending'"
        )
        paid = self._query_one(
            "SELECT COALESCE(SUM(net_amount_usd),0) AS amount FROM paper_dividend_payments_v2"
        )
        return max(0.0, 5000.0 + closed["amount"] + paid["amount"]
                   - invested["amount"] - reserved["amount"])

    def confirm_paper_dividend(
        self, position_id: int, ex_session: str, pay_session: str,
        net_amount_usd: float,
    ) -> bool:
        """Credit a dividend only after its Saxo payment is manually confirmed."""
        if net_amount_usd < 0:
            raise ValueError("net_amount_usd must be non-negative")
        from engine.trading_calendar import last_completed_session

        if pay_session < ex_session or pay_session > last_completed_session():
            raise ValueError("pay_session must be a completed date after ex-date")
        entitlement = self._query_one(
            "SELECT dividend_cash FROM paper_actions_v2 WHERE position_id=? AND session=?",
            (position_id, ex_session),
        )
        if not entitlement or net_amount_usd > entitlement["dividend_cash"]:
            return False
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO paper_dividend_payments_v2
                VALUES (?,?,?,?,?) ON CONFLICT(position_id,ex_session) DO UPDATE SET
                pay_session=excluded.pay_session,net_amount_usd=excluded.net_amount_usd,
                confirmed_at=excluded.confirmed_at""",
                (position_id, ex_session, pay_session, net_amount_usd,
                 datetime.now().astimezone().isoformat()),
            )
        return True

    def get_pending_dividends(self) -> list[dict]:
        """Return entitlements withheld from tradable paper cash."""
        return self._query(
            """SELECT a.position_id, a.session AS ex_session, a.dividend_cash,
            x.symbol FROM paper_actions_v2 a JOIN paper_positions_v2 x ON x.id=a.position_id
            LEFT JOIN paper_dividend_payments_v2 p
            ON p.position_id=a.position_id AND p.ex_session=a.session
            WHERE a.dividend_cash>0 AND p.position_id IS NULL"""
        )

    def get_confirmed_dividend_payments(self) -> list[dict]:
        """Return paid net dividends with their actual cash date."""
        return self._query(
            """SELECT p.pay_session, p.net_amount_usd, x.symbol, x.strategy
            FROM paper_dividend_payments_v2 p
            JOIN paper_positions_v2 x ON x.id=p.position_id
            ORDER BY p.pay_session"""
        )

    def queue_paper_order(
        self, source_session: str, target_session: str, strategy: str,
        symbol: str, side: str, budget_usd: float = 0,
        indicative_shares: int = 0,
    ) -> bool:
        """Idempotently queue an order for the next opening auction."""
        if side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        try:
            with self._connect() as conn:
                conn.execute(
                    """INSERT INTO paper_orders_v2
                    (source_session, target_session, strategy, symbol, side,
                     budget_usd, indicative_shares)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (source_session, target_session, strategy, symbol, side,
                     budget_usd, indicative_shares),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def get_score(self, strategy: str, symbol: str, asof_session: str) -> dict | None:
        """Use only a validated score whose cutoff predates the signal."""
        return self._query_one(
            "SELECT * FROM strategy_scores WHERE strategy=? AND symbol=? "
            "AND asof_session<=? ORDER BY asof_session DESC LIMIT 1",
            (strategy, symbol, asof_session),
        )

    def upsert_score(self, result: dict) -> None:
        """Write an observational validation without granting trade approval."""
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO strategy_scores
                (strategy,symbol,asof_session,n_trades,monthly_lower_bound,
                 max_drawdown,calibrated,verdict,train_p_adjusted,
                 holdout_monthly_return,scope)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(strategy,symbol,asof_session) DO UPDATE SET
                 n_trades=excluded.n_trades,
                 monthly_lower_bound=excluded.monthly_lower_bound,
                 max_drawdown=excluded.max_drawdown,
                 calibrated=excluded.calibrated, verdict=excluded.verdict,
                 train_p_adjusted=excluded.train_p_adjusted,
                 holdout_monthly_return=excluded.holdout_monthly_return,
                 scope=excluded.scope""",
                (result["strategy"], result["symbol"], result["asof_session"],
                 result["n_trades"], result["monthly_lower_bound"],
                 result["max_drawdown"], int(result["calibrated"]), result["verdict"],
                 result["train_p_adjusted"],
                 result["holdout_monthly_return"], result["scope"]),
            )

    def get_latest_v2_scores(self) -> list[dict]:
        """Return the most recent next-open validation for each pair."""
        return self._query(
            """SELECT s.* FROM strategy_scores s
            WHERE s.asof_session=(SELECT MAX(t.asof_session) FROM strategy_scores t
                                  WHERE t.strategy=s.strategy AND t.symbol=s.symbol)
            ORDER BY s.strategy, s.symbol"""
        )

    def start_observation(self, start_session: str) -> dict:
        """Start one fixed 20-session observation period without auto-promotion."""
        from engine.trading_calendar import XNYS

        if not XNYS.is_session(pd.Timestamp(start_session)):
            raise ValueError("start_session must be an XNYS session")
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO observation_period VALUES (1, ?, ?)",
                (start_session, datetime.now().astimezone().isoformat()),
            )
        return self._query_one("SELECT * FROM observation_period WHERE id=1") or {}

    def log_observation_check(
        self, source_session: str, symbol: str, saxo_open: float,
        execution_price: float | None = None,
        actual_fees_usd: float | None = None, notes: str = "",
    ) -> bool:
        """Record the broker reference and optional real fill for one candidate."""
        if saxo_open <= 0 or (execution_price is not None and execution_price <= 0):
            raise ValueError("prices must be positive")
        if actual_fees_usd is not None and actual_fees_usd < 0:
            raise ValueError("fees must be non-negative")
        period = self._query_one("SELECT * FROM observation_period WHERE id=1")
        from engine.trading_calendar import XNYS

        candidate = self._query_one(
            "SELECT 1 FROM signal_decisions WHERE source_session=? AND symbol=? "
            "AND technical_signal='BUY'",
            (source_session, symbol.upper()),
        )
        if not period or source_session < period["start_session"] or not candidate:
            return False
        sessions = XNYS.sessions_in_range(
            pd.Timestamp(period["start_session"]), pd.Timestamp(source_session),
        )
        if len(sessions) > 20 or not XNYS.is_session(pd.Timestamp(source_session)):
            return False
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO observation_checks VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(source_session,symbol) DO UPDATE SET
                saxo_open=excluded.saxo_open,
                execution_price=excluded.execution_price,
                actual_fees_usd=excluded.actual_fees_usd,
                notes=excluded.notes,confirmed_at=excluded.confirmed_at""",
                (source_session, symbol.upper(), saxo_open, execution_price,
                 actual_fees_usd, notes, datetime.now().astimezone().isoformat()),
            )
        return True

    def get_observation_status(self, asof_session: str) -> dict:
        """Report progress and broker-open gaps, never promote a strategy."""
        from engine.trading_calendar import XNYS

        period = self._query_one("SELECT * FROM observation_period WHERE id=1")
        if not period:
            return {"status": "NOT_STARTED", "target_sessions": 20}
        sessions = (
            XNYS.sessions_in_range(
                pd.Timestamp(period["start_session"]), pd.Timestamp(asof_session),
            )[:20]
            if asof_session >= period["start_session"] else []
        )
        end_session = str(sessions[-1].date()) if len(sessions) else period["start_session"]
        scanned = self._query(
            "SELECT source_session,status,error FROM scanner_sessions WHERE source_session>=?",
            (period["start_session"],),
        )
        scanned_by_session = {row["source_session"]: row for row in scanned}
        completed = sum(scanned_by_session.get(str(day.date()), {}).get("status") == "complete"
                        for day in sessions)
        candidates = self._query(
            """SELECT DISTINCT source_session,symbol FROM signal_decisions
            WHERE source_session>=? AND source_session<=? AND technical_signal='BUY'
            ORDER BY source_session,symbol""",
            (period["start_session"], end_session),
        )
        checks = {
            (row["source_session"], row["symbol"]): row
            for row in self._query("SELECT * FROM observation_checks")
        }
        comparisons = []
        for candidate in candidates:
            key = (candidate["source_session"], candidate["symbol"])
            check = checks.get(key)
            target = self._query_one(
                "SELECT target_session FROM signal_decisions WHERE source_session=? "
                "AND symbol=? LIMIT 1", key,
            )
            order = self._query_one(
                """SELECT filled_price,filled_shares,fee_usd,status
                FROM paper_orders_v2 WHERE source_session=? AND symbol=? AND side='BUY'""",
                key,
            )
            paper_open = order["filled_price"] if order else None
            simulated_open = (
                self.get_raw_open(candidate["symbol"], target["target_session"])
                if target else None
            )
            saxo_open = check["saxo_open"] if check else None
            comparisons.append({
                **candidate,
                "target_session": target["target_session"] if target else None,
                "paper_open": paper_open,
                "simulated_open": simulated_open,
                "paper_status": order["status"] if order else None,
                "saxo_open": saxo_open,
                "execution_price": check["execution_price"] if check else None,
                "actual_fees_usd": check["actual_fees_usd"] if check else None,
                "open_gap_pct": (
                    100 * (saxo_open / simulated_open - 1)
                    if saxo_open and simulated_open else None
                ),
            })
        missing = sum(item["saxo_open"] is None for item in comparisons)
        status = (
            "IN_PROGRESS" if len(sessions) < 20 else
            "REVIEW_READY" if completed == 20 and missing == 0 and comparisons else
            "INSUFFICIENT_EVIDENCE"
        )
        return {
            "status": status, "start_session": period["start_session"],
            "target_sessions": 20, "sessions_elapsed": len(sessions),
            "sessions_scanned": completed, "candidate_count": len(comparisons),
            "missing_broker_checks": missing,
            "comparisons": comparisons,
            "automatic_promotion": False,
        }

    def save_prices_v2(
        self, symbol: str, df: pd.DataFrame,
        repairs: list[dict] | None = None,
    ) -> None:
        """Persist raw/adjusted OHLC and any audited fallback in one transaction."""
        records = []
        for session, row in df.iterrows():
            records.append((
                symbol, str(pd.Timestamp(session).date()),
                float(row["Open"]), float(row["High"]), float(row["Low"]),
                float(row["Close"]), float(row["Adj_Open"]),
                float(row["Adj_High"]), float(row["Adj_Low"]),
                float(row["Adj_Close"]), float(row["Volume"]),
                float(row.get("Dividends", 0)), float(row.get("Stock Splits", 0)),
            ))
        with self._connect() as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO prices_v2
                (symbol,date,raw_open,raw_high,raw_low,raw_close,adj_open,
                 adj_high,adj_low,adj_close,volume,dividend,split,price_basis_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 2)""", records,
            )
            for repair in repairs or []:
                conn.execute(
                    """INSERT INTO price_repairs_v2
                    (symbol,date,source_url,verified_at,previous_close,next_close,
                     raw_open,raw_high,raw_low,raw_close,volume,applied_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(symbol,date) DO UPDATE SET
                    source_url=excluded.source_url,
                    verified_at=excluded.verified_at,
                    previous_close=excluded.previous_close,
                    next_close=excluded.next_close,
                    raw_open=excluded.raw_open,raw_high=excluded.raw_high,
                    raw_low=excluded.raw_low,raw_close=excluded.raw_close,
                    volume=excluded.volume,applied_at=excluded.applied_at""",
                    (repair["symbol"], repair["session"], repair["source_url"],
                     repair["verified_at"], repair["previous_close"],
                     repair["next_close"], repair["open"], repair["high"],
                     repair["low"], repair["close"], repair["volume"],
                     datetime.now().astimezone().isoformat()),
                )

    def get_price_repair(self, symbol: str, session: str) -> dict | None:
        """Retrieve one previously audited fallback for a missing Yahoo bar."""
        return self._query_one(
            "SELECT * FROM price_repairs_v2 WHERE symbol=? AND date=?",
            (symbol, session),
        )

    def get_price_repairs(self) -> list[dict]:
        """List exchange-sourced repaired bars for data-quality reporting."""
        return self._query(
            "SELECT * FROM price_repairs_v2 ORDER BY date DESC,symbol"
        )

    def has_legacy_prices_v2(self, symbol: str, start: str, end: str) -> bool:
        """Detect Yahoo split-adjusted bars saved before price-basis version 2."""
        row = self._query_one(
            """SELECT 1 AS legacy FROM prices_v2
            WHERE symbol=? AND date>=? AND date<? AND price_basis_version<>2 LIMIT 1""",
            (symbol, start, end),
        )
        return row is not None

    def get_prices_v2(
        self, symbol: str, start: str | None = None, end: str | None = None,
    ) -> pd.DataFrame:
        """Read raw and adjusted OHLC without borrowing the legacy cache."""
        query = "SELECT * FROM prices_v2 WHERE symbol=?"
        params: list[str] = [symbol]
        if start:
            query += " AND date>=?"
            params.append(start)
        if end:
            query += " AND date<=?"
            params.append(end)
        query += " ORDER BY date"
        rows = self._query(query, tuple(params))
        names = {
            "raw_open": "Open", "raw_high": "High", "raw_low": "Low",
            "raw_close": "Close", "adj_open": "Adj_Open",
            "adj_high": "Adj_High", "adj_low": "Adj_Low",
            "adj_close": "Adj_Close", "volume": "Volume",
            "dividend": "Dividends", "split": "Stock Splits",
        }
        if not rows:
            return pd.DataFrame(columns=list(names.values()))
        df = pd.DataFrame(rows).rename(columns=names).set_index("date")
        return df.drop(columns=["symbol", "price_basis_version"]).set_axis(pd.to_datetime(df.index))

    def get_raw_open(self, symbol: str, session: str) -> float | None:
        """Return a tradable opening price only for the exact session."""
        row = self._query_one(
            "SELECT raw_open FROM prices_v2 WHERE symbol=? AND date=? AND price_basis_version=2", (symbol, session)
        )
        return float(row["raw_open"]) if row else None

    def get_follow_positions(self, status: str = "open") -> list[dict]:
        """Read an independent virtual study of every positive signal."""
        if status not in {"open", "closed"}:
            raise ValueError("invalid position status")
        return self._query(
            "SELECT * FROM signal_follow_positions WHERE status=? "
            "ORDER BY entry_session DESC, symbol, strategy", (status,),
        )

    def get_follow_orders(self, status: str = "pending") -> list[dict]:
        """Read virtual orders without mixing them with portfolio orders."""
        if status not in {"pending", "filled", "skipped"}:
            raise ValueError("invalid order status")
        return self._query(
            "SELECT * FROM signal_follow_orders WHERE status=? "
            "ORDER BY target_session, id", (status,),
        )

    def queue_follow_order(
        self, source_session: str, target_session: str, strategy: str,
        symbol: str, side: str, position_id: int | None = None,
        notional_usd: float = 5000.0,
    ) -> bool:
        """Queue one virtual next-open fill per strategy/title/session."""
        if side not in {"BUY", "SELL"} or notional_usd <= 0:
            raise ValueError("invalid virtual order")
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            open_pos = conn.execute(
                "SELECT id FROM signal_follow_positions "
                "WHERE strategy=? AND symbol=? AND status='open'",
                (strategy, symbol),
            ).fetchone()
            pending_buy = conn.execute(
                "SELECT 1 FROM signal_follow_orders WHERE strategy=? AND symbol=? "
                "AND side='BUY' AND status='pending'", (strategy, symbol),
            ).fetchone()
            if side == "BUY" and (open_pos or pending_buy):
                return False
            if side == "SELL" and (
                not open_pos or open_pos["id"] != position_id
            ):
                return False
            try:
                conn.execute(
                    """INSERT INTO signal_follow_orders
                    (source_session,target_session,strategy,symbol,side,
                     position_id,notional_usd) VALUES (?,?,?,?,?,?,?)""",
                    (source_session, target_session, strategy, symbol, side,
                     position_id, notional_usd),
                )
            except sqlite3.IntegrityError:
                return False
        return True

    def apply_follow_actions(self, through_session: str) -> None:
        """Apply verified Yahoo ex-date splits and dividends once per virtual lot."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            positions = conn.execute(
                "SELECT * FROM signal_follow_positions WHERE status='open'"
            ).fetchall()
            for pos in positions:
                actions = conn.execute(
                    """SELECT date,dividend,split FROM prices_v2
                    WHERE symbol=? AND date>? AND date<=?
                    AND price_basis_version=2 AND (dividend>0 OR split>0)
                    ORDER BY date""",
                    (pos["symbol"], pos["entry_session"], through_session),
                ).fetchall()
                for action in actions:
                    if conn.execute(
                        "SELECT 1 FROM signal_follow_actions "
                        "WHERE position_id=? AND session=?",
                        (pos["id"], action["date"]),
                    ).fetchone():
                        continue
                    current = conn.execute(
                        "SELECT shares FROM signal_follow_positions WHERE id=?",
                        (pos["id"],),
                    ).fetchone()["shares"]
                    shares = current * (action["split"] if action["split"] > 0 else 1)
                    dividend = shares * action["dividend"]
                    conn.execute(
                        "UPDATE signal_follow_positions "
                        "SET shares=?,dividend_cash=dividend_cash+? WHERE id=?",
                        (shares, dividend, pos["id"]),
                    )
                    conn.execute(
                        "INSERT INTO signal_follow_actions VALUES (?,?,?,?)",
                        (pos["id"], action["date"], dividend, action["split"]),
                    )

    def fill_due_follow_orders(self, through_session: str, fee_model: Any) -> list[dict]:
        """Fill each independent signal at its exact next raw open."""
        orders = self._query(
            "SELECT * FROM signal_follow_orders "
            "WHERE status='pending' AND target_session<=? "
            "ORDER BY target_session, CASE side WHEN 'SELL' THEN 0 ELSE 1 END, id",
            (through_session,),
        )
        processed: list[dict] = []
        for order in orders:
            older_pending = self._query_one(
                """SELECT 1 AS pending FROM signal_follow_orders
                WHERE strategy=? AND symbol=? AND status='pending'
                AND (target_session<? OR (target_session=? AND id<?))
                LIMIT 1""",
                (order["strategy"], order["symbol"], order["target_session"],
                 order["target_session"], order["id"]),
            )
            if older_pending:
                continue
            price = self.get_raw_open(order["symbol"], order["target_session"])
            if price is None:
                continue
            self.apply_follow_actions(order["target_session"])
            shares = 0
            fee = 0.0
            reason = ""
            status = "filled"
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                if order["side"] == "BUY":
                    existing = conn.execute(
                        "SELECT 1 FROM signal_follow_positions "
                        "WHERE strategy=? AND symbol=? AND status='open'",
                        (order["strategy"], order["symbol"]),
                    ).fetchone()
                    if existing:
                        status, reason = "skipped", "virtual position already open"
                    else:
                        shares = max(0, int(order["notional_usd"] // price))
                        while shares and (
                            shares * price + fee_model.total_entry_cost(shares * price)
                            > order["notional_usd"]
                        ):
                            shares -= 1
                        if shares:
                            fee = fee_model.total_entry_cost(shares * price)
                            conn.execute(
                                """INSERT INTO signal_follow_positions
                                (strategy,symbol,source_session,entry_session,
                                 entry_price,shares,cost_basis,entry_fee)
                                VALUES (?,?,?,?,?,?,?,?)""",
                                (order["strategy"], order["symbol"],
                                 order["source_session"], order["target_session"],
                                 price, shares, shares * price, fee),
                            )
                        else:
                            status, reason = "skipped", "opening price exceeds virtual notional"
                else:
                    pos = conn.execute(
                        "SELECT * FROM signal_follow_positions "
                        "WHERE id=? AND status='open'",
                        (order["position_id"],),
                    ).fetchone()
                    if pos:
                        shares = pos["shares"]
                        fee = fee_model.total_exit_cost(price * shares)
                        pnl = (price * shares - fee + pos["dividend_cash"]
                               - pos["cost_basis"] - pos["entry_fee"])
                        conn.execute(
                            """UPDATE signal_follow_positions
                            SET status='closed',exit_session=?,exit_price=?,
                            exit_fee=?,pnl_dollars=? WHERE id=?""",
                            (order["target_session"], price, fee, pnl, pos["id"]),
                        )
                    else:
                        status, reason = "skipped", "virtual position already closed"
                conn.execute(
                    """UPDATE signal_follow_orders
                    SET status=?,filled_price=?,filled_shares=?,fee_usd=?,reason=?
                    WHERE id=?""",
                    (status, price, shares, fee, reason, order["id"]),
                )
            processed.append(self._query_one(
                "SELECT * FROM signal_follow_orders WHERE id=?", (order["id"],)
            ))
        self.apply_follow_actions(through_session)
        return processed

    def apply_paper_actions(self, through_session: str) -> None:
        """Apply each ex-date split/dividend to a held v2 position once."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            positions = conn.execute(
                "SELECT * FROM paper_positions_v2 WHERE status='open'"
            ).fetchall()
            for pos in positions:
                actions = conn.execute(
                    """SELECT date, dividend, split FROM prices_v2
                    WHERE symbol=? AND date>? AND date<=?
                    AND (dividend>0 OR split>0) ORDER BY date""",
                    (pos["symbol"], pos["entry_session"], through_session),
                ).fetchall()
                for action in actions:
                    existing = conn.execute(
                        "SELECT 1 FROM paper_actions_v2 WHERE position_id=? AND session=?",
                        (pos["id"], action["date"]),
                    ).fetchone()
                    if existing:
                        continue
                    current = conn.execute(
                        "SELECT shares FROM paper_positions_v2 WHERE id=?", (pos["id"],)
                    ).fetchone()[0]
                    shares = current * (action["split"] if action["split"] > 0 else 1)
                    dividend_cash = shares * action["dividend"]
                    conn.execute(
                        "UPDATE paper_positions_v2 SET shares=?, dividend_cash=dividend_cash+? WHERE id=?",
                        (shares, dividend_cash, pos["id"]),
                    )
                    conn.execute(
                        "INSERT INTO paper_actions_v2 VALUES (?, ?, ?, ?)",
                        (pos["id"], action["date"], dividend_cash, action["split"]),
                    )

    def fill_due_paper_orders(self, through_session: str, fee_model: Any) -> list[dict]:
        """Fill queued orders at their exact target raw open, never at signal close."""
        orders = self._query(
            "SELECT * FROM paper_orders_v2 WHERE status='pending' AND target_session<=? "
            "ORDER BY target_session, CASE side WHEN 'SELL' THEN 0 ELSE 1 END, id",
            (through_session,),
        )
        filled: list[dict] = []
        sale_sessions = {o["target_session"] for o in orders if o["side"] == "SELL"}
        missing_earlier_open = False
        for order in orders:
            # Process the historical timeline in order. Applying actions all the
            # way to through_session before an overdue fill would give a sale
            # future splits or leave a delayed purchase without its later splits.
            self.apply_paper_actions(order["target_session"])
            price = self.get_raw_open(order["symbol"], order["target_session"])
            if price is None:
                missing_earlier_open = True
                break
            if order["side"] == "BUY":
                if order["target_session"] in sale_sessions or self.get_v2_open_positions():
                    status, reason = "skipped", "single-position or same-open sale constraint"
                    shares, fee = 0, 0.0
                else:
                    closed = self._query_one(
                        "SELECT COALESCE(SUM(pnl_dollars),0) AS pnl FROM paper_positions_v2 "
                        "WHERE status='closed' AND exit_session<?",
                        (order["target_session"],),
                    )
                    budget = min(5000.0 + closed["pnl"], order["budget_usd"], 5000.0)
                    shares = max(0, int(budget // price))
                    while shares and shares * price + fee_model.total_entry_cost(shares * price) > budget:
                        shares -= 1
                    fee = fee_model.total_entry_cost(shares * price) if shares else 0.0
                    status = "filled" if shares else "skipped"
                    reason = "" if shares else "opening gap or fees leave no affordable share"
                with self._connect() as conn:
                    if shares:
                        conn.execute(
                            """INSERT INTO paper_positions_v2
                            (strategy,symbol,entry_session,entry_price,shares,cost_basis,entry_fee)
                            VALUES (?,?,?,?,?,?,?)""",
                            (order["strategy"], order["symbol"], order["target_session"],
                             price, shares, price * shares, fee),
                        )
                    conn.execute(
                        "UPDATE paper_orders_v2 SET status=?,filled_price=?,filled_shares=?,fee_usd=?,reason=? WHERE id=?",
                        (status, price, shares, fee, reason, order["id"]),
                    )
            else:
                pos = self._query_one(
                    "SELECT * FROM paper_positions_v2 WHERE symbol=? AND status='open'",
                    (order["symbol"],),
                )
                if pos:
                    shares = pos["shares"]
                    fee = fee_model.total_exit_cost(price * shares)
                    pnl = (price * shares - fee
                           - pos["cost_basis"] - pos["entry_fee"])
                    with self._connect() as conn:
                        conn.execute(
                            """UPDATE paper_positions_v2 SET status='closed', exit_session=?,
                            exit_price=?, exit_fee=?, pnl_dollars=? WHERE id=?""",
                            (order["target_session"], price, fee, pnl, pos["id"]),
                        )
                        conn.execute(
                            "UPDATE paper_orders_v2 SET status='filled',filled_price=?,filled_shares=?,fee_usd=? WHERE id=?",
                            (price, shares, fee, order["id"]),
                        )
                else:
                    with self._connect() as conn:
                        conn.execute(
                            "UPDATE paper_orders_v2 SET status='skipped',reason='no open position' WHERE id=?",
                            (order["id"],),
                        )
            filled.append(self._query_one("SELECT * FROM paper_orders_v2 WHERE id=?", (order["id"],)))
        if not missing_earlier_open:
            self.apply_paper_actions(through_session)
        return filled
