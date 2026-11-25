"""Tests for the pandas analytics: pure functions first, then the route."""
from datetime import date, timedelta

import pandas as pd

from app import analytics
from tests.conftest import sign_up

TODAY = date(2026, 10, 20)


def table(rows):
    df = pd.DataFrame(rows, columns=["date", "amount", "type", "category", "description"])
    df["date"] = pd.to_datetime(df["date"])
    df["category_source"] = "accepted"
    df["suggested_category_id"] = 1
    return df


def test_empty_data_gives_zeros_not_errors():
    result = analytics.build_analytics(pd.DataFrame(), TODAY)
    assert len(result["months"]) == 12
    assert all(m["expense"] == 0 for m in result["months"])
    assert result["suggestion_accuracy"]["percent"] is None
    assert result["insights"]


def test_months_and_savings():
    df = table([("2026-10-01", 1000, "income", "Salary", "pay"), ("2026-10-05", 400, "expense", "Food", "swiggy")])
    this_month = analytics.build_analytics(df, TODAY)["months"][-1]
    assert this_month == {"month": "2026-10", "income": 1000.0, "expense": 400.0, "savings": 600.0}


def test_category_change_vs_last_month():
    df = table([("2026-09-10", 100, "expense", "Food", "a"), ("2026-10-10", 150, "expense", "Food", "b")])
    change = analytics.build_analytics(df, TODAY)["category_changes"][0]
    assert change["change_percent"] == 50.0


def test_financial_year_start_dates():
    df = table([("2026-04-01", 100, "expense", "Food", "a"), ("2026-04-10", 200, "expense", "Food", "b")])
    assert analytics.financial_year(df, TODAY, "uk")["expense"] == 200      # UK year starts 6 April
    assert analytics.financial_year(df, TODAY, "india")["expense"] == 300   # India starts 1 April
    assert analytics.financial_year(df, date(2026, 3, 1), "uk")["label"] == "2025/26"


def test_unusual_spending_needs_enough_history():
    few = table([("2026-10-10", 5000, "expense", "Food", "big")] + [("2026-10-01", 100, "expense", "Food", "x")] * 2)
    assert analytics.build_analytics(few, TODAY)["unusual"] == []

    many = table([(f"2026-09-{d:02d}", 100 + d % 3, "expense", "Food", "lunch") for d in range(1, 11)]
                 + [("2026-10-15", 5000, "expense", "Food", "wedding dinner")])
    found = analytics.build_analytics(many, TODAY)["unusual"]
    assert found and found[0]["description"] == "wedding dinner"


def test_month_end_estimate():
    df = table([("2026-10-05", 200, "expense", "Food", "a")])
    est = analytics.month_end_estimate(df, TODAY)       # 200 over 20 days -> 31 days
    assert est["estimate"] == 310.0 and est["days_left"] == 11


def test_suggestion_accuracy():
    df = table([("2026-10-01", 10, "expense", "Food", "a")] * 3)
    df.loc[0, "category_source"] = "user"
    assert analytics.suggestion_accuracy(df) == {"checked": 3, "kept": 2, "percent": 67}


def test_route_needs_login(client):
    assert client.get("/analytics").status_code == 401


def test_route_returns_numbers_for_my_data_only(client, headers, category_ids):
    client.post("/transactions", json={"description": "swiggy", "amount": 250, "type": "expense"}, headers=headers)
    other = sign_up(client, "other@x.com")
    client.post("/transactions", json={"description": "pizza", "amount": 9000, "type": "expense"}, headers=other)

    result = client.get("/analytics", headers=headers).json()
    assert result["months"][-1]["expense"] == 250
    assert result["category_changes"][0]["category"] == "Food"
    assert result["month_end"]["spent_so_far"] == 250


def test_bad_financial_year_is_rejected(client, headers):
    assert client.get("/analytics?fy=mars", headers=headers).status_code == 422