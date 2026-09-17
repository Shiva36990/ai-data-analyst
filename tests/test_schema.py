import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set -- skipping live schema tests.",
)


def test_schema_contains_expected_tables():
    from src.schema_service import get_database_schema

    schema = get_database_schema()
    for table in ("customers", "orders", "order_items", "products", "categories"):
        assert table in schema


def test_schema_excludes_non_allowed_tables():
    from src.schema_service import get_database_schema

    schema = get_database_schema()
    assert "agent_query_logs" not in schema


def test_schema_to_text_includes_foreign_keys():
    from src.schema_service import get_database_schema, schema_to_text

    schema = get_database_schema()
    text = schema_to_text(schema)
    assert "FOREIGN KEY" in text
