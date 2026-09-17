from src.charts import create_chart


def make_result():
    return {
        "columns": ["month", "revenue"],
        "rows": [
            {"month": "2025-01", "revenue": 100},
            {"month": "2025-02", "revenue": 120},
        ],
        "row_count": 2,
    }


def test_no_chart_when_not_needed():
    plan = {"chart_needed": False}
    assert create_chart(make_result(), plan) is None


def test_no_chart_when_no_rows():
    plan = {"chart_needed": True, "chart_type": "line", "x_column": "month", "y_column": "revenue"}
    empty_result = {"columns": ["month", "revenue"], "rows": []}
    assert create_chart(empty_result, plan) is None


def test_line_chart_created():
    plan = {
        "chart_needed": True,
        "chart_type": "line",
        "x_column": "month",
        "y_column": "revenue",
        "title": "Revenue by month",
    }
    fig = create_chart(make_result(), plan)
    assert fig is not None


def test_missing_x_column_returns_none():
    plan = {
        "chart_needed": True,
        "chart_type": "bar",
        "x_column": "does_not_exist",
        "y_column": "revenue",
    }
    assert create_chart(make_result(), plan) is None


def test_unknown_chart_type_returns_none():
    plan = {
        "chart_needed": True,
        "chart_type": "none",
        "x_column": "month",
        "y_column": "revenue",
    }
    assert create_chart(make_result(), plan) is None
