import pandas as pd

from src.analytics import (
    rows_to_dataframe,
    percent_change,
    basic_numeric_summary,
    rank_rows,
)


def test_rows_to_dataframe():
    result = {"columns": ["a", "b"], "rows": [{"a": 1, "b": 2}]}
    df = rows_to_dataframe(result)
    assert list(df.columns) == ["a", "b"]
    assert len(df) == 1


def test_percent_change_basic():
    assert round(percent_change(100, 120), 2) == 20.0


def test_percent_change_decline():
    assert round(percent_change(100, 80), 2) == -20.0


def test_percent_change_zero_old_returns_none():
    assert percent_change(0, 50) is None


def test_percent_change_none_old_returns_none():
    assert percent_change(None, 50) is None


def test_basic_numeric_summary_empty_df():
    assert basic_numeric_summary(pd.DataFrame()) == {}


def test_basic_numeric_summary_no_numeric_columns():
    df = pd.DataFrame({"name": ["a", "b"]})
    assert basic_numeric_summary(df) == {}


def test_rank_rows_top_n():
    df = pd.DataFrame({"category": ["a", "b", "c"], "revenue": [10, 30, 20]})
    top = rank_rows(df, "revenue", ascending=False, top_n=2)
    assert list(top["category"]) == ["b", "c"]
