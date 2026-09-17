import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set -- skipping live database tests.",
)


def test_connection_succeeds():
    from src.database import test_connection

    assert test_connection() is True


def test_execute_read_query_shape():
    from src.database import execute_read_query

    result = execute_read_query("SELECT 1 AS one")
    assert result["columns"] == ["one"]
    assert result["rows"] == [{"one": 1}]
    assert result["row_count"] == 1


def test_row_cap_is_enforced():
    from src.config import settings
    from src.database import execute_read_query

    result = execute_read_query(
        f"SELECT generate_series(1, {settings.max_query_rows * 2}) AS n"
    )
    assert result["row_count"] <= settings.max_query_rows
