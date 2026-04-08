"""
Database Manager — PostgreSQL backend via SQLAlchemy engine.

Provides the same execute_query / execute_one / execute_insert / execute_update
API that every module in the project already uses, but routes queries through
a SQLAlchemy connection pool targeting PostgreSQL instead of SQLite.

SQLite → PostgreSQL translation (?, DATE('now'), sqlite_master, etc.) is
handled automatically so callers do not need any changes.
"""
import re
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────
# SQL TRANSLATION HELPERS
# ──────────────────────────────────────────────────────────────────

def _sqlite_to_pg(sql):
    """Convert SQLite-flavoured SQL to PostgreSQL dialect."""

    # 1. Positional placeholders: ? → %s
    sql = re.sub(r'\?', '%s', sql)

    # 2. DATE('now', '-N days') → CURRENT_DATE - INTERVAL 'N days'
    sql = re.sub(
        r"DATE\s*\(\s*'now'\s*,\s*'(-\d+)\s+days?'\s*\)",
        lambda m: f"CURRENT_DATE - INTERVAL '{abs(int(m.group(1)))} days'",
        sql,
        flags=re.IGNORECASE,
    )

    # 3. DATE('now') → CURRENT_DATE
    sql = re.sub(r"DATE\s*\(\s*'now'\s*\)", 'CURRENT_DATE', sql, flags=re.IGNORECASE)

    # 4. DATE(expr) → (expr)::date
    sql = re.sub(r'\bDATE\s*\(([^)]+)\)', r'(\1)::date', sql, flags=re.IGNORECASE)

    # 5. sqlite_master table check → information_schema
    sql = sql.replace(
        "sqlite_master WHERE type='table' AND name",
        "information_schema.tables WHERE table_schema='public' AND table_name",
    )

    return sql


def _to_named(pg_sql, params):
    """Replace %s with :p0, :p1, … and return (named_sql, param_dict)."""
    if not params:
        return pg_sql, {}
    counter = [0]

    def _replacer(_m):
        idx = counter[0]
        counter[0] += 1
        return f':p{idx}'

    named_sql = re.sub(r'%s', _replacer, pg_sql)
    param_dict = {f'p{i}': v for i, v in enumerate(params)}
    return named_sql, param_dict


# ──────────────────────────────────────────────────────────────────
# DATABASE MANAGER
# ──────────────────────────────────────────────────────────────────

class DatabaseManager:
    """Drop-in replacement for the original SQLite DatabaseManager.

    Every module calls:
        db.execute_query(sql, params)     → list[dict]
        db.execute_one(sql, params)       → dict | None
        db.execute_insert(sql, params)    → int  (new row id)
        db.execute_update(sql, params)    → None
    """

    def __init__(self, database_url):
        self.database_url = database_url
        try:
            self.engine = create_engine(
                database_url,
                poolclass=QueuePool,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10,
                connect_args={'connect_timeout': 5}
            )
            # Test connection immediately
            with self.engine.connect() as conn:
                pass
            logger.info("DatabaseManager successfully connected to PostgreSQL")
        except Exception as e:
            logger.error(f"FATAL: Could not connect to PostgreSQL. Is the server running? Error: {e}")
            # Keep engine object active so app doesn't immediately crash, but queries will fail gracefully
            self.engine = create_engine(database_url)

    # Keep legacy get_db() for code that calls it directly
    def get_db(self):
        return self.engine.connect()

    # ── SELECT (many rows) ────────────────────────────────────────
    def execute_query(self, query, params=()):
        """Execute a SELECT and return list of dicts."""
        try:
            pg_sql = _sqlite_to_pg(query)
            named_sql, pdict = _to_named(pg_sql, params)
            with self.engine.connect() as conn:
                result = conn.execute(text(named_sql), pdict)
                rows = result.mappings().all()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Query error: {e}\n  SQL: {query}")
            return []

    # ── SELECT (single row) ───────────────────────────────────────
    def execute_one(self, query, params=()):
        """Execute a SELECT and return first row as dict, or None."""
        try:
            pg_sql = _sqlite_to_pg(query)
            named_sql, pdict = _to_named(pg_sql, params)
            with self.engine.connect() as conn:
                result = conn.execute(text(named_sql), pdict)
                row = result.mappings().first()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Query one error: {e}\n  SQL: {query}")
            return None

    # ── INSERT ────────────────────────────────────────────────────
    def execute_insert(self, query, params=()):
        """Execute an INSERT and return the new row id.

        Auto-appends ``RETURNING id`` for PostgreSQL when not already present.
        """
        try:
            pg_sql = _sqlite_to_pg(query)
            # Append RETURNING id for INSERT statements
            trimmed = pg_sql.strip().rstrip(';')
            if trimmed.upper().startswith('INSERT') and 'RETURNING' not in trimmed.upper():
                pg_sql = trimmed + ' RETURNING id'
            named_sql, pdict = _to_named(pg_sql, params)
            with self.engine.connect() as conn:
                result = conn.execute(text(named_sql), pdict)
                conn.commit()
                row = result.fetchone()
                return row[0] if row else None
        except Exception as e:
            logger.error(f"Insert error: {e}\n  SQL: {query}")
            raise

    # ── UPDATE / DELETE ───────────────────────────────────────────
    def execute_update(self, query, params=()):
        """Execute UPDATE / DELETE / any non-SELECT statement."""
        try:
            pg_sql = _sqlite_to_pg(query)
            named_sql, pdict = _to_named(pg_sql, params)
            with self.engine.connect() as conn:
                conn.execute(text(named_sql), pdict)
                conn.commit()
        except Exception as e:
            logger.error(f"Update error: {e}\n  SQL: {query}")
            raise
