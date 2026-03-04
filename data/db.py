"""Base SQLite unique pour signal-radar.

Stocke les prix OHLCV et tous les resultats d'analyse.
Un seul fichier : data/signal_radar.db

Usage:
    from data.db import SignalRadarDB

    db = SignalRadarDB()

    # Prix
    db.save_ohlcv("AAPL", df)
    db.get_ohlcv("AAPL", "2005-01-01", "2025-01-01")
    db.has_ohlcv("AAPL")
    db.ohlcv_date_range("AAPL")

    # Resultats
    db.save_screen(strategy, universe, results)
    db.save_validation(report)
    db.get_best_assets(strategy, min_pf=1.2)
    db.compare_strategies(["rsi2", "ibs"], "us_stocks_large")
    db.get_cross_strategy("META")

    # Gestion
    db.list_assets()
    db.clear_ohlcv("AAPL")
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).parent / "signal_radar.db"

# SQLite timeout (seconds) — avoids instant OperationalError when another
# process holds the write lock (e.g. scanner + API writing concurrently).
SQLITE_TIMEOUT = 30


class SignalRadarDB:
    """Base de donnees SQLite unique : prix OHLCV + resultats."""

    def __init__(self, db_path: Path | str = DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        """Create a new SQLite connection with proper timeout."""
        return sqlite3.connect(self.db_path, timeout=SQLITE_TIMEOUT)

    def _init_db(self) -> None:
        """Cree les tables si elles n'existent pas."""
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
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol
                ON ohlcv(symbol)
            """)

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

            # -- T-test poole --
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pooled_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    universe TEXT NOT NULL,
                    result_type TEXT NOT NULL,
                    total_trades INTEGER,
                    t_stat REAL,
                    p_value REAL,
                    n_validated INTEGER,
                    n_conditional INTEGER,
                    n_rejected INTEGER,
                    UNIQUE(strategy, universe, result_type, timestamp)
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
                    UNIQUE(strategy, symbol, entry_date)
                )
            """)

            # -- Signal log (audit trail) --
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

            # Migration : ajouter details_json si absent (tables existantes)
            try:
                conn.execute(
                    "ALTER TABLE signal_log ADD COLUMN details_json TEXT"
                )
            except sqlite3.OperationalError:
                pass  # colonne deja existante

            # Migration : ajouter notes a paper_positions si absent
            try:
                conn.execute(
                    "ALTER TABLE paper_positions ADD COLUMN notes TEXT DEFAULT ''"
                )
            except sqlite3.OperationalError:
                pass  # colonne deja existante

            # -- Live trades (real trades logged by user) --
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
                    paper_position_id INTEGER,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    UNIQUE(strategy, symbol, entry_date)
                )
            """)

            # -- Indexes for query performance --
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_signal_log_timestamp
                ON signal_log(timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_signal_log_symbol_ts
                ON signal_log(symbol, timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_paper_positions_status_strategy
                ON paper_positions(status, strategy)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_live_trades_status_strategy
                ON live_trades(status, strategy)
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

    def save_asset_metadata(self, symbol: str, name: str, logo_url: str | None = None) -> None:
        """Enregistre ou met à jour les métadonnées d'un actif."""
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO asset_metadata (symbol, name, logo_url, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (symbol, name, logo_url))

    def get_asset_metadata(self, symbol: str) -> dict | None:
        """Récupère les métadonnées d'un actif."""
        return self._query_one("SELECT * FROM asset_metadata WHERE symbol = ?", (symbol,))

    def get_all_metadata(self) -> dict[str, dict]:
        """Récupère toutes les métadonnées indexées par symbole."""
        rows = self._query("SELECT * FROM asset_metadata")
        return {r["symbol"]: r for r in rows}

    # ------------------------------------------------------------------ #
    # OHLCV
    # ------------------------------------------------------------------ #

    def save_ohlcv(self, symbol: str, df: pd.DataFrame) -> None:
        """Sauvegarde un DataFrame OHLCV dans la DB.

        Le DataFrame doit avoir un DatetimeIndex et des colonnes
        Open, High, Low, Close, Volume (Adj_Close optionnel).
        INSERT OR REPLACE -- les donnees existantes sont ecrasees.
        """
        if df.empty:
            return

        records = []
        for date, row in df.iterrows():
            date_str = pd.Timestamp(date).strftime("%Y-%m-%d")
            records.append((
                symbol, date_str,
                float(row["Open"]), float(row["High"]),
                float(row["Low"]), float(row["Close"]),
                float(row.get("Volume", 0)),
            ))

        with self._connect() as conn:
            conn.executemany("""
                INSERT OR REPLACE INTO ohlcv
                (symbol, date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, records)

    def get_ohlcv(
        self, symbol: str, start: str | None = None, end: str | None = None,
    ) -> pd.DataFrame:
        """Recupere les donnees OHLCV depuis la DB.

        Returns:
            DataFrame avec colonnes Open, High, Low, Close, Adj_Close, Volume.
            Index: DatetimeIndex nomme "Date".
            Vide si le symbol n'existe pas.
        """
        query = "SELECT date, open, high, low, close, volume FROM ohlcv WHERE symbol = ?"
        params: list = [symbol]

        if start:
            query += " AND date >= ?"
            params.append(start)
        if end:
            query += " AND date <= ?"
            params.append(end)

        query += " ORDER BY date"

        with self._connect() as conn:
            df = pd.read_sql_query(query, conn, params=params)

        if df.empty:
            return pd.DataFrame()

        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        df.index.name = "Date"
        df.columns = ["Open", "High", "Low", "Close", "Volume"]
        # Adj_Close = Close (donnees deja ajustees pour splits)
        df["Adj_Close"] = df["Close"]
        return df

    def has_ohlcv(self, symbol: str) -> bool:
        """Verifie si un symbol a des donnees en DB."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM ohlcv WHERE symbol = ?", (symbol,)
            ).fetchone()
            return row[0] > 0

    def ohlcv_date_range(self, symbol: str) -> tuple[str, str] | None:
        """Retourne (min_date, max_date) pour un symbol. None si absent."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT MIN(date), MAX(date) FROM ohlcv WHERE symbol = ?",
                (symbol,),
            ).fetchone()
            if row[0] is None:
                return None
            return (row[0], row[1])

    def list_assets(self) -> list[dict]:
        """Liste tous les assets en DB avec metadata."""
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT symbol, COUNT(*) as rows,
                       MIN(date) as start, MAX(date) as end
                FROM ohlcv
                GROUP BY symbol
                ORDER BY symbol
            """).fetchall()
            return [
                {"symbol": r[0], "rows": r[1], "start": r[2], "end": r[3]}
                for r in rows
            ]

    def clear_ohlcv(self, symbol: str | None = None) -> None:
        """Supprime les donnees OHLCV. Sans argument = tout."""
        with self._connect() as conn:
            if symbol:
                conn.execute("DELETE FROM ohlcv WHERE symbol = ?", (symbol,))
            else:
                conn.execute("DELETE FROM ohlcv")

    # ------------------------------------------------------------------ #
    # SCREENS
    # ------------------------------------------------------------------ #

    def save_screen(
        self,
        strategy_name: str,
        universe_name: str,
        results: list[dict],
        timestamp: str | None = None,
    ) -> None:
        """Sauvegarde les resultats d'un screening.

        Args:
            strategy_name: Nom de la strategie
            universe_name: Nom de l'univers
            results: Liste de dicts avec symbol, n_trades, win_rate,
                     profit_factor, sharpe, net_return_pct
            timestamp: Timestamp ISO (auto si None)
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        with self._connect() as conn:
            for r in results:
                conn.execute("""
                    INSERT OR REPLACE INTO screens
                    (timestamp, strategy, universe, symbol, n_trades,
                     win_rate, profit_factor, sharpe, net_return_pct)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    timestamp,
                    strategy_name,
                    universe_name,
                    r["symbol"],
                    r["n_trades"],
                    r["win_rate"],
                    r["profit_factor"],
                    r["sharpe"],
                    r["net_return_pct"],
                ))

    # ------------------------------------------------------------------ #
    # VALIDATIONS
    # ------------------------------------------------------------------ #

    def save_validation(self, report: object) -> None:
        """Sauvegarde un ValidationReport complet.

        Args:
            report: ValidationReport (from validation.report)
        """
        timestamp = report.timestamp  # type: ignore[attr-defined]
        with self._connect() as conn:
            for a in report.assets:  # type: ignore[attr-defined]
                conn.execute("""
                    INSERT OR REPLACE INTO validations
                    (timestamp, strategy, universe, symbol, n_trades, win_rate,
                     profit_factor, sharpe, net_return_pct, robustness_pct,
                     stable, ttest_p, verdict)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    timestamp,
                    report.strategy_name,  # type: ignore[attr-defined]
                    report.universe_name,  # type: ignore[attr-defined]
                    a.symbol,
                    a.oos_result.n_trades,
                    a.oos_result.win_rate,
                    a.oos_result.profit_factor,
                    a.oos_result.sharpe,
                    a.oos_result.net_return_pct,
                    a.robustness.pct_profitable,
                    1 if a.sub_periods.stable else 0,
                    a.ttest.p_value,
                    a.verdict.value,
                ))

            # Pooled results
            pt = report.pooled_ttest  # type: ignore[attr-defined]
            if pt is not None:
                conn.execute("""
                    INSERT OR REPLACE INTO pooled_results
                    (timestamp, strategy, universe, result_type, total_trades,
                     t_stat, p_value, n_validated, n_conditional, n_rejected)
                    VALUES (?, ?, ?, 'validation', ?, ?, ?, ?, ?, ?)
                """, (
                    timestamp,
                    report.strategy_name,  # type: ignore[attr-defined]
                    report.universe_name,  # type: ignore[attr-defined]
                    pt.n_trades,
                    pt.t_stat,
                    pt.p_value,
                    len(report.validated),  # type: ignore[attr-defined]
                    len(report.conditional),  # type: ignore[attr-defined]
                    len(report.rejected),  # type: ignore[attr-defined]
                ))

    # ------------------------------------------------------------------ #
    # REQUETES
    # ------------------------------------------------------------------ #

    def get_best_assets(
        self,
        strategy: str,
        universe: str | None = None,
        min_pf: float = 1.0,
        source: str = "screens",
    ) -> list[dict]:
        """Assets avec PF > min_pf, tries par PF desc."""
        table = "screens" if source == "screens" else "validations"

        query = f"""
            SELECT symbol, universe, n_trades, win_rate, profit_factor,
                   sharpe, net_return_pct
            FROM {table} t
            WHERE strategy = ? AND profit_factor >= ?
            AND timestamp = (
                SELECT MAX(timestamp) FROM {table} t2
                WHERE t2.strategy = t.strategy
                AND t2.universe = t.universe
                AND t2.symbol = t.symbol
            )
        """
        params: list = [strategy, min_pf]

        if universe:
            query += " AND universe = ?"
            params.append(universe)

        query += " ORDER BY profit_factor DESC"

        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(query, params).fetchall()]

    def compare_strategies(
        self,
        strategies: list[str],
        universe: str,
        source: str = "screens",
    ) -> list[dict]:
        """Tableau croise symbol x strategie (PF)."""
        table = "screens" if source == "screens" else "validations"
        results: dict[str, dict] = {}

        with self._connect() as conn:
            conn.row_factory = sqlite3.Row

            for strat in strategies:
                rows = conn.execute(f"""
                    SELECT symbol, profit_factor, win_rate
                    FROM {table} t
                    WHERE strategy = ? AND universe = ?
                    AND timestamp = (
                        SELECT MAX(timestamp) FROM {table} t2
                        WHERE t2.strategy = t.strategy
                        AND t2.universe = t.universe
                        AND t2.symbol = t.symbol
                    )
                """, (strat, universe)).fetchall()

                for row in rows:
                    symbol = row["symbol"]
                    if symbol not in results:
                        results[symbol] = {"symbol": symbol}
                    results[symbol][f"{strat}_pf"] = row["profit_factor"]
                    results[symbol][f"{strat}_wr"] = row["win_rate"]

        return sorted(
            results.values(),
            key=lambda x: sum(v for k, v in x.items() if k.endswith("_pf")),
            reverse=True,
        )

    def get_cross_strategy(self, symbol: str) -> list[dict]:
        """Tous les resultats (screen + validation) pour un symbol."""
        results: list[dict] = []

        with self._connect() as conn:
            conn.row_factory = sqlite3.Row

            for table, src_label in [("screens", "screen"), ("validations", "validation")]:
                extra = ""
                if table == "validations":
                    extra = ", verdict"

                rows = conn.execute(f"""
                    SELECT strategy, universe, n_trades, win_rate,
                           profit_factor, sharpe, net_return_pct{extra}
                    FROM {table} t
                    WHERE symbol = ?
                    AND timestamp = (
                        SELECT MAX(timestamp) FROM {table} t2
                        WHERE t2.strategy = t.strategy
                        AND t2.universe = t.universe
                        AND t2.symbol = t.symbol
                    )
                    ORDER BY strategy, universe
                """, (symbol,)).fetchall()

                for row in rows:
                    d = dict(row)
                    d["source"] = src_label
                    results.append(d)

        return results

    def get_strategies(self, source: str = "screens") -> list[str]:
        """Liste les strategies ayant des resultats."""
        table = "screens" if source == "screens" else "validations"
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT DISTINCT strategy FROM {table} ORDER BY strategy"
            ).fetchall()
            return [r[0] for r in rows]

    def get_universes(self, source: str = "screens") -> list[str]:
        """Liste les univers ayant des resultats."""
        table = "screens" if source == "screens" else "validations"
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT DISTINCT universe FROM {table} ORDER BY universe"
            ).fetchall()
            return [r[0] for r in rows]

    def count(self, source: str = "screens") -> int:
        """Nombre de lignes dans une table."""
        table = "screens" if source == "screens" else "validations"
        with self._connect() as conn:
            return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    # ------------------------------------------------------------------ #
    # PAPER TRADING
    # ------------------------------------------------------------------ #

    def open_paper_position(
        self,
        strategy: str,
        symbol: str,
        entry_date: str,
        entry_price: float,
        shares: float,
    ) -> bool:
        """Ouvre une position paper. Retourne False si deja ouverte.

        Uses BEGIN EXCLUSIVE to prevent TOCTOU race conditions when
        two scanner processes run concurrently.
        """
        conn = self._connect()
        try:
            conn.execute("BEGIN EXCLUSIVE")
            existing = conn.execute(
                "SELECT id FROM paper_positions "
                "WHERE strategy = ? AND symbol = ? AND status = 'open'",
                (strategy, symbol),
            ).fetchone()
            if existing:
                conn.rollback()
                return False
            conn.execute(
                """
                INSERT INTO paper_positions
                (strategy, symbol, entry_date, entry_price, shares, status)
                VALUES (?, ?, ?, ?, ?, 'open')
                """,
                (strategy, symbol, entry_date, entry_price, shares),
            )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def close_paper_position(
        self,
        strategy: str,
        symbol: str,
        exit_date: str,
        exit_price: float,
    ) -> dict | None:
        """Ferme une position paper. Retourne le trade info ou None.

        Uses BEGIN EXCLUSIVE for atomicity (prevents concurrent close).
        """
        conn = self._connect()
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("BEGIN EXCLUSIVE")
            row = conn.execute(
                "SELECT * FROM paper_positions "
                "WHERE strategy = ? AND symbol = ? AND status = 'open'",
                (strategy, symbol),
            ).fetchone()
            if row is None:
                conn.rollback()
                return None

            entry_price = row["entry_price"]
            shares = row["shares"]
            pnl_dollars = (exit_price - entry_price) * shares
            pnl_pct = (
                (exit_price - entry_price) / entry_price * 100
                if entry_price > 0
                else 0.0
            )

            conn.execute(
                """
                UPDATE paper_positions
                SET status = 'closed', exit_date = ?, exit_price = ?,
                    pnl_dollars = ?, pnl_pct = ?
                WHERE id = ?
                """,
                (exit_date, exit_price, round(pnl_dollars, 2), round(pnl_pct, 2), row["id"]),
            )
            conn.commit()

            return {
                "strategy": strategy,
                "symbol": symbol,
                "entry_date": row["entry_date"],
                "entry_price": entry_price,
                "exit_date": exit_date,
                "exit_price": exit_price,
                "shares": shares,
                "pnl_dollars": round(pnl_dollars, 2),
                "pnl_pct": round(pnl_pct, 2),
            }
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_open_positions(self, strategy: str | None = None) -> list[dict]:
        """Retourne les positions paper ouvertes."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            if strategy:
                rows = conn.execute(
                    "SELECT * FROM paper_positions "
                    "WHERE status = 'open' AND strategy = ? "
                    "ORDER BY entry_date",
                    (strategy,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM paper_positions "
                    "WHERE status = 'open' ORDER BY strategy, entry_date"
                ).fetchall()
            return [dict(r) for r in rows]

    def get_closed_trades(
        self,
        strategy: str | None = None,
        symbol: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Retourne les trades paper fermes (plus recents en premier)."""
        query = "SELECT * FROM paper_positions WHERE status = 'closed'"
        params: list = []
        if strategy:
            query += " AND strategy = ?"
            params.append(strategy)
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        query += " ORDER BY exit_date DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(query, params).fetchall()]

    def get_paper_summary(self) -> dict:
        """Resume du paper trading : PnL total, win rate, par strategie."""
        with self._connect() as conn:
            # Global aggregation
            row = conn.execute("""
                SELECT COUNT(*) as n,
                       COALESCE(SUM(CASE WHEN pnl_dollars > 0 THEN 1 ELSE 0 END), 0) as wins,
                       COALESCE(SUM(pnl_dollars), 0.0) as total_pnl
                FROM paper_positions WHERE status = 'closed'
            """).fetchone()
            n_trades, wins, total_pnl = row[0], row[1], row[2]

            # Per-strategy aggregation
            strat_rows = conn.execute("""
                SELECT strategy,
                       COUNT(*) as trades,
                       SUM(CASE WHEN pnl_dollars > 0 THEN 1 ELSE 0 END) as wins,
                       COALESCE(SUM(pnl_dollars), 0.0) as pnl
                FROM paper_positions WHERE status = 'closed'
                GROUP BY strategy
            """).fetchall()
            by_strategy = {
                r[0]: {"trades": r[1], "wins": r[2], "pnl": round(r[3], 2)}
                for r in strat_rows
            }

            n_open = conn.execute(
                "SELECT COUNT(*) FROM paper_positions WHERE status = 'open'"
            ).fetchone()[0]

            return {
                "n_trades": n_trades,
                "n_wins": wins,
                "win_rate": round(wins / n_trades * 100, 1) if n_trades > 0 else 0.0,
                "total_pnl": round(total_pnl, 2),
                "n_open": n_open,
                "by_strategy": by_strategy,
            }

    def clear_paper_positions(self, strategy: str | None = None) -> int:
        """Supprime les positions paper ouvertes. Retourne le nombre supprime."""
        with self._connect() as conn:
            if strategy:
                cur = conn.execute(
                    "DELETE FROM paper_positions "
                    "WHERE status = 'open' AND strategy = ?",
                    (strategy,),
                )
            else:
                cur = conn.execute(
                    "DELETE FROM paper_positions WHERE status = 'open'"
                )
            return cur.rowcount

    # ------------------------------------------------------------------ #
    # SIGNAL LOG
    # ------------------------------------------------------------------ #

    def log_signal(
        self,
        timestamp: str,
        strategy: str,
        symbol: str,
        signal: str,
        close_price: float | None = None,
        indicator_value: float | None = None,
        notes: str = "",
        details_json: str | None = None,
    ) -> None:
        """Log un signal dans la table signal_log."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO signal_log
                (timestamp, strategy, symbol, signal, close_price,
                 indicator_value, notes, details_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (timestamp, strategy, symbol, signal, close_price,
                 indicator_value, notes, details_json),
            )

    # ------------------------------------------------------------------ #
    # API QUERY METHODS
    # ------------------------------------------------------------------ #

    def get_latest_signals(
        self, strategy: str | None = None
    ) -> tuple[str | None, list[dict]]:
        """Retourne (timestamp, signaux) du dernier run du scanner.

        Trouve le MAX(timestamp) dans signal_log, puis retourne
        tous les signaux de ce timestamp.
        Returns (None, []) si pas de signaux.
        """
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row

            row = conn.execute(
                "SELECT MAX(timestamp) as ts FROM signal_log"
            ).fetchone()
            if not row or not row["ts"]:
                return None, []

            latest_ts = row["ts"]
            query = "SELECT * FROM signal_log WHERE timestamp = ?"
            params: list = [latest_ts]

            if strategy:
                query += " AND strategy = ?"
                params.append(strategy)

            query += " ORDER BY strategy, symbol"
            return latest_ts, [dict(r) for r in conn.execute(query, params).fetchall()]

    def get_signal_history(
        self,
        strategy: str | None = None,
        symbol: str | None = None,
        signal_type: str | None = None,
        days: int = 7,
    ) -> list[dict]:
        """Retourne l'historique des signaux sur N jours."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row

            query = "SELECT * FROM signal_log WHERE 1=1"
            params: list = []

            if strategy:
                query += " AND strategy = ?"
                params.append(strategy)
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
            if signal_type:
                query += " AND signal = ?"
                params.append(signal_type)
            if days:
                query += " AND timestamp >= datetime('now', ?)"
                params.append(f"-{days} days")

            query += " ORDER BY timestamp DESC"
            return [dict(r) for r in conn.execute(query, params).fetchall()]

    def get_latest_price(self, symbol: str) -> float | None:
        """Retourne le dernier close_price connu pour un symbol (depuis signal_log)."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT close_price FROM signal_log "
                "WHERE symbol = ? AND close_price IS NOT NULL "
                "ORDER BY timestamp DESC LIMIT 1",
                (symbol,),
            ).fetchone()
            return row[0] if row else None

    def get_latest_prices(self, symbols: list[str]) -> dict[str, float]:
        """Retourne les derniers prix connus pour une liste de symbols (batch)."""
        if not symbols:
            return {}
        placeholders = ",".join("?" for _ in symbols)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT symbol, close_price FROM signal_log
                WHERE id IN (
                    SELECT MAX(id) FROM signal_log
                    WHERE symbol IN ({placeholders})
                    AND close_price IS NOT NULL
                    GROUP BY symbol
                )
                """,
                symbols,
            ).fetchall()
            return {row[0]: row[1] for row in rows}

    def get_screens_filtered(
        self,
        strategy: str | None = None,
        universe: str | None = None,
        min_pf: float = 1.0,
    ) -> list[dict]:
        """Retourne les screens filtres, dedupliques (plus recent par strategy+universe+symbol)."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row

            query = """
                SELECT s.* FROM screens s
                INNER JOIN (
                    SELECT strategy, universe, symbol, MAX(timestamp) as max_ts
                    FROM screens
                    GROUP BY strategy, universe, symbol
                ) latest ON s.strategy = latest.strategy
                    AND s.universe = latest.universe
                    AND s.symbol = latest.symbol
                    AND s.timestamp = latest.max_ts
                WHERE s.profit_factor >= ?
            """
            params: list = [min_pf]

            if strategy:
                query += " AND s.strategy = ?"
                params.append(strategy)
            if universe:
                query += " AND s.universe = ?"
                params.append(universe)

            query += " ORDER BY s.profit_factor DESC"
            return [dict(r) for r in conn.execute(query, params).fetchall()]

    def get_validations_filtered(
        self,
        strategy: str | None = None,
        universe: str | None = None,
        verdict: str | None = None,
    ) -> list[dict]:
        """Retourne les validations filtrees, dedupliquees (plus recent par strategy+universe+symbol)."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row

            query = """
                SELECT v.* FROM validations v
                INNER JOIN (
                    SELECT strategy, universe, symbol, MAX(timestamp) as max_ts
                    FROM validations
                    GROUP BY strategy, universe, symbol
                ) latest ON v.strategy = latest.strategy
                    AND v.universe = latest.universe
                    AND v.symbol = latest.symbol
                    AND v.timestamp = latest.max_ts
                WHERE 1=1
            """
            params: list = []

            if strategy:
                query += " AND v.strategy = ?"
                params.append(strategy)
            if universe:
                query += " AND v.universe = ?"
                params.append(universe)
            if verdict:
                query += " AND v.verdict = ?"
                params.append(verdict)

            query += " ORDER BY v.profit_factor DESC"
            return [dict(r) for r in conn.execute(query, params).fetchall()]

    # ------------------------------------------------------------------ #
    # LIVE TRADES
    # ------------------------------------------------------------------ #

    def open_live_trade(
        self,
        strategy: str,
        symbol: str,
        entry_date: str,
        entry_price: float,
        shares: float,
        fees: float = 0,
        notes: str = "",
        paper_position_id: int | None = None,
    ) -> bool:
        """Ouvre un trade live. Retourne True si cree, False si doublon."""
        with self._connect() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO live_trades
                    (strategy, symbol, entry_date, entry_price, shares,
                     fees_entry, notes, paper_position_id, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open')
                    """,
                    (strategy, symbol, entry_date, entry_price, shares,
                     fees, notes, paper_position_id),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def close_live_trade(
        self,
        strategy: str,
        symbol: str,
        exit_date: str,
        exit_price: float,
        fees: float = 0,
    ) -> dict | None:
        """Ferme un trade live. Retourne le trade info avec PnL, ou None."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM live_trades "
                "WHERE strategy = ? AND symbol = ? AND status = 'open'",
                (strategy, symbol),
            ).fetchone()
            if row is None:
                return None

            entry_price = row["entry_price"]
            shares_val = row["shares"]
            fees_entry = row["fees_entry"] or 0
            pnl_dollars = (exit_price - entry_price) * shares_val - fees_entry - fees
            # Net pnl_pct includes fees (consistent with pnl_dollars)
            cost_basis = entry_price * shares_val + fees_entry
            pnl_pct = (
                pnl_dollars / cost_basis * 100
                if cost_basis > 0
                else 0.0
            )

            conn.execute(
                """
                UPDATE live_trades
                SET status = 'closed', exit_date = ?, exit_price = ?,
                    fees_exit = ?, pnl_dollars = ?, pnl_pct = ?
                WHERE id = ?
                """,
                (exit_date, exit_price, fees,
                 round(pnl_dollars, 2), round(pnl_pct, 2), row["id"]),
            )

            return {
                "id": row["id"],
                "strategy": strategy,
                "symbol": symbol,
                "entry_date": row["entry_date"],
                "entry_price": entry_price,
                "exit_date": exit_date,
                "exit_price": exit_price,
                "shares": shares_val,
                "fees_entry": fees_entry,
                "fees_exit": fees,
                "pnl_dollars": round(pnl_dollars, 2),
                "pnl_pct": round(pnl_pct, 2),
            }

    def get_open_live_trades(self, strategy: str | None = None) -> list[dict]:
        """Retourne les trades live ouverts."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            if strategy:
                rows = conn.execute(
                    "SELECT * FROM live_trades "
                    "WHERE status = 'open' AND strategy = ? "
                    "ORDER BY entry_date",
                    (strategy,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM live_trades "
                    "WHERE status = 'open' ORDER BY strategy, entry_date"
                ).fetchall()
            return [dict(r) for r in rows]

    def get_closed_live_trades(
        self,
        strategy: str | None = None,
        symbol: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Retourne les trades live fermes."""
        query = "SELECT * FROM live_trades WHERE status = 'closed'"
        params: list = []
        if strategy:
            query += " AND strategy = ?"
            params.append(strategy)
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        query += " ORDER BY exit_date DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(query, params).fetchall()]

    def delete_live_trade(self, trade_id: int) -> bool:
        """Supprime un live trade (open ou closed) par ID. Retourne True si supprime."""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM live_trades WHERE id = ?", (trade_id,))
            return cur.rowcount > 0

    def get_live_summary(self) -> dict:
        """Resume live : n_trades, win_rate, total_pnl, par strategie."""
        with self._connect() as conn:
            # Global aggregation
            row = conn.execute("""
                SELECT COUNT(*) as n,
                       COALESCE(SUM(CASE WHEN pnl_dollars > 0 THEN 1 ELSE 0 END), 0) as wins,
                       COALESCE(SUM(pnl_dollars), 0.0) as total_pnl
                FROM live_trades WHERE status = 'closed'
            """).fetchone()
            n_trades, wins, total_pnl = row[0], row[1], row[2]

            # Per-strategy aggregation
            strat_rows = conn.execute("""
                SELECT strategy,
                       COUNT(*) as trades,
                       SUM(CASE WHEN pnl_dollars > 0 THEN 1 ELSE 0 END) as wins,
                       COALESCE(SUM(pnl_dollars), 0.0) as pnl
                FROM live_trades WHERE status = 'closed'
                GROUP BY strategy
            """).fetchall()
            by_strategy = {
                r[0]: {"trades": r[1], "wins": r[2], "pnl": round(r[3], 2)}
                for r in strat_rows
            }

            n_open = conn.execute(
                "SELECT COUNT(*) FROM live_trades WHERE status = 'open'"
            ).fetchone()[0]

            return {
                "n_trades": n_trades,
                "n_wins": wins,
                "win_rate": round(wins / n_trades * 100, 1) if n_trades > 0 else 0.0,
                "total_pnl": round(total_pnl, 2),
                "n_open": n_open,
                "by_strategy": by_strategy,
            }

    # ------------------------------------------------------------------ #
    # TRADE JOURNAL
    # ------------------------------------------------------------------ #

    def update_paper_entry(self, id: int, notes: str | None = None, tags: str | None = None, sentiment: str | None = None) -> bool:
        """Update paper position fields (notes, tags, sentiment)."""
        updates = []
        params = []
        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)
        if tags is not None:
            updates.append("tags = ?")
            params.append(tags)
        if sentiment is not None:
            updates.append("sentiment = ?")
            params.append(sentiment)
        
        if not updates:
            return True
            
        params.append(id)
        query = f"UPDATE paper_positions SET {', '.join(updates)} WHERE id = ?"
        with self._connect() as conn:
            cur = conn.execute(query, params)
            return cur.rowcount > 0

    def update_live_entry(self, id: int, notes: str | None = None, tags: str | None = None, sentiment: str | None = None) -> bool:
        """Update live trade fields (notes, tags, sentiment)."""
        updates = []
        params = []
        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)
        if tags is not None:
            updates.append("tags = ?")
            params.append(tags)
        if sentiment is not None:
            updates.append("sentiment = ?")
            params.append(sentiment)
            
        if not updates:
            return True
            
        params.append(id)
        query = f"UPDATE live_trades SET {', '.join(updates)} WHERE id = ?"
        with self._connect() as conn:
            cur = conn.execute(query, params)
            return cur.rowcount > 0

    def update_paper_notes(self, position_id: int, notes: str) -> bool:
        """Met a jour les notes d'une position paper. Retourne True si modifie."""
        return self.update_paper_entry(position_id, notes=notes)

    def update_live_notes(self, trade_id: int, notes: str) -> bool:
        """Met a jour les notes d'un trade live. Retourne True si modifie."""
        return self.update_live_entry(trade_id, notes=notes)

    def get_journal_entries(
        self,
        strategy: str | None = None,
        symbol: str | None = None,
        source: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """Timeline unifiee paper + live trades avec contexte signal.

        Args:
            strategy: Filtre par strategie (rsi2, ibs, tom)
            symbol: Filtre par symbole
            source: "paper", "live", ou None (les deux)
            search: Recherche texte dans les notes
            limit: Nombre max d'entries
            offset: Offset pour pagination

        Returns:
            {"entries": [...], "total": N, "stats": {...}}

        Note: holding_days est en jours calendaires (pas de trading).
        """
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            entries: list[dict] = []

            # -- Paper positions --
            if source is None or source == "paper":
                p_query = "SELECT * FROM paper_positions WHERE 1=1"
                p_params: list = []
                if strategy:
                    p_query += " AND strategy = ?"
                    p_params.append(strategy)
                if symbol:
                    p_query += " AND symbol = ?"
                    p_params.append(symbol)
                for r in conn.execute(p_query, p_params).fetchall():
                    d = dict(r)
                    entries.append({
                        "id": d["id"],
                        "source": "paper",
                        "strategy": d["strategy"],
                        "symbol": d["symbol"],
                        "status": d["status"],
                        "entry_date": d["entry_date"],
                        "entry_price": d["entry_price"],
                        "exit_date": d.get("exit_date"),
                        "exit_price": d.get("exit_price"),
                        "shares": d["shares"],
                        "fees": 0.0,
                        "pnl_dollars": d.get("pnl_dollars"),
                        "pnl_pct": d.get("pnl_pct"),
                        "holding_days": self._holding_days(
                            d["entry_date"], d.get("exit_date")
                        ),
                        "notes": d.get("notes") or "",
                        "tags": d.get("tags") or "",
                        "sentiment": d.get("sentiment") or "",
                        "signal_details": None,
                        "slippage": None,
                    })

            # -- Live trades --
            if source is None or source == "live":
                l_query = "SELECT * FROM live_trades WHERE 1=1"
                l_params: list = []
                if strategy:
                    l_query += " AND strategy = ?"
                    l_params.append(strategy)
                if symbol:
                    l_query += " AND symbol = ?"
                    l_params.append(symbol)
                for r in conn.execute(l_query, l_params).fetchall():
                    d = dict(r)
                    fees_total = (d.get("fees_entry") or 0) + (
                        d.get("fees_exit") or 0
                    )
                    entries.append({
                        "id": d["id"],
                        "source": "live",
                        "strategy": d["strategy"],
                        "symbol": d["symbol"],
                        "status": d["status"],
                        "entry_date": d["entry_date"],
                        "entry_price": d["entry_price"],
                        "exit_date": d.get("exit_date"),
                        "exit_price": d.get("exit_price"),
                        "shares": d["shares"],
                        "fees": round(fees_total, 2),
                        "pnl_dollars": d.get("pnl_dollars"),
                        "pnl_pct": d.get("pnl_pct"),
                        "holding_days": self._holding_days(
                            d["entry_date"], d.get("exit_date")
                        ),
                        "notes": d.get("notes") or "",
                        "tags": d.get("tags") or "",
                        "sentiment": d.get("sentiment") or "",
                        "signal_details": None,
                        "slippage": None,
                        "paper_position_id": d.get("paper_position_id"),
                    })

            # -- Search filter (in Python, post-query) --
            if search:
                search_lower = search.lower()
                entries = [
                    e for e in entries
                    if search_lower in (e["notes"] or "").lower()
                ]

            # -- Attach signal context (batch) --
            self._attach_signal_context(conn, entries)

            # -- Attach slippage for live trades linked to paper --
            self._attach_slippage(conn, entries)

            # -- Stats (computed on filtered set, before pagination) --
            total = len(entries)
            closed = [e for e in entries if e["status"] == "closed"]
            n_open = total - len(closed)
            wins = sum(1 for e in closed if (e["pnl_dollars"] or 0) > 0)
            total_pnl = sum(e["pnl_dollars"] or 0 for e in closed)
            avg_pnl = round(total_pnl / len(closed), 2) if closed else 0.0
            holding_list = [
                e["holding_days"] for e in entries
                if e["holding_days"] is not None
            ]
            avg_holding = (
                round(sum(holding_list) / len(holding_list), 1)
                if holding_list else 0.0
            )

            stats = {
                "total_trades": total,
                "open_trades": n_open,
                "closed_trades": len(closed),
                "win_rate": round(wins / len(closed) * 100, 1) if closed else 0.0,
                "total_pnl": round(total_pnl, 2),
                "avg_pnl": avg_pnl,
                "avg_holding_days": avg_holding,
            }

            # -- Sort: open first, then by entry_date desc --
            entries.sort(
                key=lambda e: (
                    0 if e["status"] == "open" else 1,
                    e["entry_date"],
                ),
                reverse=True,
            )

            # -- Paginate --
            paginated = entries[offset : offset + limit]

            return {"entries": paginated, "total": total, "stats": stats}

    @staticmethod
    def _holding_days(entry_date: str, exit_date: str | None) -> int | None:
        """Jours calendaires entre entry et exit (ou aujourd'hui si open)."""
        try:
            entry_dt = datetime.strptime(entry_date, "%Y-%m-%d")
        except (ValueError, TypeError):
            return None
        if exit_date:
            try:
                exit_dt = datetime.strptime(exit_date, "%Y-%m-%d")
            except (ValueError, TypeError):
                return None
            return (exit_dt - entry_dt).days
        return (datetime.now() - entry_dt).days

    @staticmethod
    def _attach_signal_context(
        conn: sqlite3.Connection, entries: list[dict]
    ) -> None:
        """Attache le details_json du signal_log a chaque entry (batch)."""
        if not entries:
            return
        import json as _json

        seen: dict[tuple[str, str, str], dict | None] = {}
        for e in entries:
            key = (e["strategy"], e["symbol"], e["entry_date"])
            if key in seen:
                e["signal_details"] = seen[key]
                continue
            row = conn.execute(
                """
                SELECT details_json FROM signal_log
                WHERE strategy = ? AND symbol = ?
                AND timestamp >= ? AND timestamp < date(?, '+4 days')
                ORDER BY timestamp LIMIT 1
                """,
                (key[0], key[1], key[2], key[2]),
            ).fetchone()
            detail = None
            if row and row["details_json"]:
                try:
                    detail = _json.loads(row["details_json"])
                except (ValueError, TypeError):
                    pass
            seen[key] = detail
            e["signal_details"] = detail

    @staticmethod
    def _attach_slippage(
        conn: sqlite3.Connection, entries: list[dict]
    ) -> None:
        """Attache le slippage paper vs live pour les live trades lies."""
        paper_ids = [
            e.get("paper_position_id")
            for e in entries
            if e["source"] == "live" and e.get("paper_position_id")
        ]
        if not paper_ids:
            return

        placeholders = ",".join("?" for _ in paper_ids)
        rows = conn.execute(
            f"SELECT * FROM paper_positions WHERE id IN ({placeholders})",
            paper_ids,
        ).fetchall()
        paper_map = {r["id"]: dict(r) for r in rows}

        for e in entries:
            if e["source"] != "live" or not e.get("paper_position_id"):
                continue
            paper = paper_map.get(e["paper_position_id"])
            if not paper:
                continue
            entry_diff = round(e["entry_price"] - paper["entry_price"], 2)
            exit_diff = None
            pnl_diff = None
            if (
                e["exit_price"] is not None
                and paper.get("exit_price") is not None
            ):
                exit_diff = round(e["exit_price"] - paper["exit_price"], 2)
            if (
                e["pnl_dollars"] is not None
                and paper.get("pnl_dollars") is not None
            ):
                pnl_diff = round(e["pnl_dollars"] - paper["pnl_dollars"], 2)
            e["slippage"] = {
                "entry_diff": entry_diff,
                "exit_diff": exit_diff,
                "pnl_diff": pnl_diff,
            }
