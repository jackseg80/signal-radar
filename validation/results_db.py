"""Base SQLite pour les resultats de validation et screening.

Tables:
    validations -- resultats de validation complete par asset
    screens -- resultats de screening rapide
    pooled_results -- t-test poole par (strategy, universe)

Usage:
    from validation.results_db import ResultsDB

    db = ResultsDB()
    db.save_screen("rsi2", "us_stocks_large", results)
    db.get_best_assets("rsi2", min_pf=1.2)
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("validation_results") / "results.db"


class ResultsDB:
    """Base de donnees SQLite pour les resultats."""

    def __init__(self, db_path: Path | str = DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Cree les tables si elles n'existent pas."""
        with sqlite3.connect(self.db_path) as conn:
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

    def save_validation(self, report: object) -> None:
        """Sauvegarde un ValidationReport complet.

        Args:
            report: ValidationReport (from validation.report)
        """
        timestamp = report.timestamp  # type: ignore[attr-defined]
        with sqlite3.connect(self.db_path) as conn:
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

        with sqlite3.connect(self.db_path) as conn:
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

    # ---- Requetes ----

    def get_best_assets(
        self,
        strategy: str,
        universe: str | None = None,
        min_pf: float = 1.0,
        source: str = "screens",
    ) -> list[dict]:
        """Assets avec PF > min_pf, tries par PF desc.

        Args:
            strategy: Nom de la strategie
            universe: Filtrer par univers (None = tous)
            min_pf: Profit factor minimum
            source: 'screens' ou 'validations'

        Returns:
            Liste de dicts avec symbol, n_trades, win_rate, etc.
        """
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

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(query, params).fetchall()]

    def compare_strategies(
        self,
        strategies: list[str],
        universe: str,
        source: str = "screens",
    ) -> list[dict]:
        """Tableau croise symbol x strategie (PF).

        Returns:
            Liste de dicts : {symbol, strat1_pf, strat1_wr, strat2_pf, ...}
        """
        table = "screens" if source == "screens" else "validations"
        results: dict[str, dict] = {}

        with sqlite3.connect(self.db_path) as conn:
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

        with sqlite3.connect(self.db_path) as conn:
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
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                f"SELECT DISTINCT strategy FROM {table} ORDER BY strategy"
            ).fetchall()
            return [r[0] for r in rows]

    def get_universes(self, source: str = "screens") -> list[str]:
        """Liste les univers ayant des resultats."""
        table = "screens" if source == "screens" else "validations"
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                f"SELECT DISTINCT universe FROM {table} ORDER BY universe"
            ).fetchall()
            return [r[0] for r in rows]

    def count(self, source: str = "screens") -> int:
        """Nombre de lignes dans une table."""
        table = "screens" if source == "screens" else "validations"
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
