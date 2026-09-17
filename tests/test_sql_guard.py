from src.sql_guard import validate_sql


def test_select_allowed():
    valid, _ = validate_sql("SELECT * FROM customers LIMIT 10")
    assert valid


def test_select_with_join_allowed():
    valid, _ = validate_sql(
        "SELECT o.order_id, c.customer_name FROM orders o "
        "JOIN customers c ON o.customer_id = c.customer_id LIMIT 5"
    )
    assert valid


def test_cte_allowed():
    valid, _ = validate_sql(
        "WITH monthly AS (SELECT 1 AS x) SELECT * FROM monthly"
    )
    assert valid


def test_delete_blocked():
    valid, _ = validate_sql("DELETE FROM customers")
    assert not valid


def test_update_blocked():
    valid, _ = validate_sql("UPDATE products SET unit_price = 1")
    assert not valid


def test_drop_blocked():
    valid, _ = validate_sql("DROP TABLE customers")
    assert not valid


def test_alter_blocked():
    valid, _ = validate_sql("ALTER TABLE customers ADD COLUMN x INT")
    assert not valid


def test_multiple_statements_blocked():
    valid, _ = validate_sql("SELECT 1; DROP TABLE orders;")
    assert not valid


def test_empty_sql_blocked():
    valid, _ = validate_sql("")
    assert not valid


def test_prompt_injection_in_string_literal_still_blocked():
    # Even if a malicious value tries to sneak a destructive keyword in
    # as a *string literal*, the keyword blocklist still catches it --
    # we intentionally err on the side of over-blocking here.
    valid, _ = validate_sql(
        "SELECT * FROM customers WHERE customer_name = 'DROP TABLE x'"
    )
    assert not valid
