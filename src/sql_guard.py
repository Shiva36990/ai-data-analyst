"""
Programmatic SQL safety validation.

This is the second of three defense layers (prompt instructions ->
THIS MODULE -> read-only database role). Never rely on the prompt
alone -- a prompt-injected or hallucinated query must still be caught
here, and even if it somehow isn't, the database role should refuse it.
"""

import re
import sqlglot
from sqlglot import exp

BLOCKED_KEYWORDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "TRUNCATE",
    "CREATE",
    "GRANT",
    "REVOKE",
    "MERGE",
    "CALL",
    "COPY",
    "EXECUTE",
    "VACUUM",
}


class UnsafeSQLError(Exception):
    pass


def validate_sql(sql: str) -> tuple[bool, str]:
    """Return (is_valid, reason). reason is '' when valid."""

    if not sql or not sql.strip():
        return False, "SQL is empty."

    normalized = sql.upper()

    for keyword in BLOCKED_KEYWORDS:
        if re.search(rf"\b{keyword}\b", normalized):
            return False, f"Blocked SQL operation: {keyword}"

    try:
        statements = sqlglot.parse(sql, read="postgres")
    except Exception as exc:
        return False, f"SQL parsing failed: {exc}"

    # sqlglot.parse splits on statement-separating semicolons. A single
    # logical query (including one with a trailing ';') should parse to
    # exactly one non-empty statement.
    statements = [s for s in statements if s is not None]

    if len(statements) != 1:
        return False, "Only one SQL statement is allowed."

    statement = statements[0]

    allowed_root = isinstance(statement, (exp.Select, exp.Union))

    if not allowed_root:
        # A CTE (WITH ... SELECT) parses as exp.Select with a `with`
        # clause attached, so it's already covered above. This is a
        # fallback for shapes we don't explicitly expect.
        if statement.find(exp.Select) is None:
            return False, "Only SELECT queries are allowed."

    return True, "SQL passed validation."
