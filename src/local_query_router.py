import re


def normalize_question(question: str) -> str:
    question = question.lower().strip()
    question = re.sub(r"[?!.]", "", question)
    question = re.sub(r"\s+", " ", question)
    return question


def local_sql_for_question(question: str) -> str | None:
    q = normalize_question(question)

    # Customer count
    if (
        ("how many" in q or "count" in q or "number of" in q)
        and "customer" in q
    ):
        return """
        SELECT COUNT(*) AS total_customers
        FROM customers
        """

    # Category count
    if (
        ("how many" in q or "count" in q or "number of" in q)
        and "categor" in q
    ):
        return """
        SELECT COUNT(*) AS total_categories
        FROM categories
        """

    # Product count
    if (
        ("how many" in q or "count" in q or "number of" in q)
        and "product" in q
    ):
        return """
        SELECT COUNT(*) AS total_products
        FROM products
        """

    # Order count
    if (
        ("how many" in q or "count" in q or "number of" in q)
        and "order" in q
    ):
        return """
        SELECT COUNT(*) AS total_orders
        FROM orders
        """

    # Total revenue
    if "total revenue" in q or "revenue generated" in q:
        return """
        SELECT COALESCE(SUM(total_amount), 0) AS total_revenue
        FROM orders
        """

    # Average order value
    if "average order value" in q or "average order amount" in q:
        return """
        SELECT COALESCE(AVG(total_amount), 0) AS average_order_value
        FROM orders
        """

    # Highest order value
    if (
        "highest order" in q
        or "maximum order" in q
        or "largest order" in q
    ):
        return """
        SELECT MAX(total_amount) AS highest_order_value
        FROM orders
        """

    # Lowest order value
    if (
        "lowest order" in q
        or "minimum order" in q
        or "smallest order" in q
    ):
        return """
        SELECT MIN(total_amount) AS lowest_order_value
        FROM orders
        """

    return None