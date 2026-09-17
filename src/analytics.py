"""
Deterministic numeric calculations done in Python, not by the LLM.

Architectural principle (see project blueprint section 34): never ask
an LLM to compute a percentage change or ranking -- compute it here,
then let the LLM explain the already-correct number. This is the
single biggest lever for reducing hallucinated statistics.
"""

import pandas as pd


def rows_to_dataframe(result: dict) -> pd.DataFrame:
    return pd.DataFrame(result.get("rows", []))


def percent_change(old, new):
    if old in (0, None) or old != old:  # NaN-safe
        return None
    return ((new - old) / old) * 100


def basic_numeric_summary(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}

    numeric = df.select_dtypes(include="number")

    if numeric.empty:
        return {}

    return numeric.describe().to_dict()


def rank_rows(df: pd.DataFrame, value_column: str, ascending: bool = False, top_n: int = 5) -> pd.DataFrame:
    if df.empty or value_column not in df.columns:
        return df

    return df.sort_values(value_column, ascending=ascending).head(top_n)


def month_over_month_changes(df: pd.DataFrame, date_column: str, value_column: str) -> pd.DataFrame:
    """Given a dataframe with one row per period, add a pct_change column."""
    if df.empty or date_column not in df.columns or value_column not in df.columns:
        return df

    sorted_df = df.sort_values(date_column).copy()
    sorted_df["pct_change"] = sorted_df[value_column].pct_change() * 100
    return sorted_df


def numeric_summary_to_text(summary: dict) -> str:
    if not summary:
        return "No numeric columns in result."

    lines = []
    for column, stats in summary.items():
        lines.append(f"{column}: {stats}")
    return "\n".join(lines)
