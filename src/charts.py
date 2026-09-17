"""
Turn a ChartPlan + query result into a Plotly figure (or None).

Kept as a pure function of (result, plan) -> Figure|None so it's easy
to unit test without a live LLM or database.
"""

import pandas as pd
import plotly.express as px


def create_chart(result: dict, plan: dict):
    if not plan or not plan.get("chart_needed"):
        return None

    rows = result.get("rows", [])
    if not rows:
        return None

    df = pd.DataFrame(rows)

    chart_type = plan.get("chart_type")
    x = plan.get("x_column")
    y = plan.get("y_column")
    color = plan.get("color_column")
    title = plan.get("title", "")

    if x not in df.columns:
        return None

    if y and y not in df.columns:
        return None

    if color and color not in df.columns:
        color = None

    if chart_type == "line":
        return px.line(df, x=x, y=y, color=color, title=title, markers=True)

    if chart_type == "bar":
        return px.bar(df, x=x, y=y, color=color, title=title)

    if chart_type == "scatter":
        return px.scatter(df, x=x, y=y, color=color, title=title)

    if chart_type == "area":
        return px.area(df, x=x, y=y, color=color, title=title)

    if chart_type == "pie":
        return px.pie(df, names=x, values=y, title=title)

    return None
