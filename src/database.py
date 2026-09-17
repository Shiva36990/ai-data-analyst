"""
Database engine and safe, read-only query execution.

IMPORTANT SECURITY NOTE:
DATABASE_URL should point at a restricted, read-only PostgreSQL role
(see scripts/init_db.sql for how to create one). This module adds a
second layer of protection (statement timeout + row cap + read-only
transaction) on top of that, but it does NOT replace database-level
permissions. Never point this at a superuser account.
"""

from sqlalchemy import create_engine, text
from src.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)


def test_connection() -> bool:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        return result.scalar() == 1


def execute_read_query(sql: str) -> dict:
    """Execute a single read-only SQL statement and return a JSON-safe dict.

    Only ever call this on SQL that has already passed
    src.sql_guard.validate_sql — this function does not itself
    re-validate the query text.
    """
    with engine.connect() as conn:
        # Belt-and-suspenders: even if guardrails upstream were somehow
        # bypassed, mark this transaction read-only at the database level.
        conn.execute(text("SET TRANSACTION READ ONLY"))
        conn.execute(text(f"SET statement_timeout = {settings.sql_timeout_ms}"))

        result = conn.execute(text(sql))

        columns = list(result.keys())
        rows = result.fetchmany(settings.max_query_rows)

        data = [dict(zip(columns, row)) for row in rows]

        # Don't leave a lingering open transaction on a read-only query.
        conn.rollback()

        return {
            "columns": columns,
            "rows": data,
            "row_count": len(data),
        }
