"""
Semantic layer: canonical metric and dimension definitions.

Feeding these into prompts (rather than letting the model invent its
own definition of "revenue" every time) is what keeps answers
consistent across different phrasings of the same underlying question.
"""

METRICS = {
    "revenue": {
        "description": "Revenue after item-level discounts.",
        "formula": "SUM(quantity * unit_price * (1 - discount / 100.0))",
    },
    "gross_profit": {
        "description": "Revenue minus product cost.",
        "formula": "revenue - SUM(quantity * cost_price)",
    },
    "aov": {
        "description": "Average order value: revenue divided by distinct completed orders.",
        "formula": "revenue / NULLIF(COUNT(DISTINCT orders.order_id), 0)",
    },
    "active_customer": {
        "description": (
            "A customer with at least one completed order within the "
            "requested period."
        ),
        "formula": "EXISTS (completed order in period)",
    },
}

DIMENSIONS = {
    "region": "orders.shipping_state",
    "category": "categories.category_name",
    "channel": "orders.sales_channel",
    "segment": "customers.customer_segment",
}


def metrics_to_text() -> str:
    lines = []
    for name, meta in METRICS.items():
        lines.append(f"{name}:")
        lines.append(f"  Description: {meta['description']}")
        lines.append(f"  Formula: {meta['formula']}")
    return "\n".join(lines)
