from datetime import date

from tests.conftest import sign_up

TODAY = date.today()


def add(client, headers, description, amount, type="expense", when=None, **extra):
    body = {"description": description, "amount": amount, "type": type, **extra}
    if when:
        body["transaction_date"] = str(when)
    return client.post("/transactions", headers=headers, json=body)


def summary(client, headers, query=""):
    return client.get(f"/summary{query}", headers=headers).json()


def test_empty_month_is_all_zero(client, headers):
    body = summary(client, headers)
    assert body["total_income"] == 0 and body["total_expense"] == 0
    assert body["categories"] == [] and body["alerts"] == []
    assert body["savings_rate_percent"] == 0


def test_totals_and_savings(client, headers):
    add(client, headers, "Salary", 1000, "income")
    add(client, headers, "Swiggy", 200)
    add(client, headers, "Uber", 100)
    body = summary(client, headers)
    assert body["total_income"] == 1000
    assert body["total_expense"] == 300
    assert body["savings"] == 700
    assert body["savings_rate_percent"] == 70


def test_period_matches_the_month_asked_for(client, headers):
    body = summary(client, headers, "?year=2020&month=3")
    assert body["period"] == "2020-03"


def test_other_months_are_left_out(client, headers):
    add(client, headers, "Swiggy", 200, when=date(2020, 3, 10))
    add(client, headers, "Swiggy", 50)
    assert summary(client, headers, "?year=2020&month=3")["total_expense"] == 200
    assert summary(client, headers)["total_expense"] == 50


def test_year_without_month_gives_400(client, headers):
    assert client.get("/summary?year=2026", headers=headers).status_code == 400


def test_categories_are_sorted_biggest_first(client, headers, category_ids):
    add(client, headers, "Salary", 1000, "income")
    add(client, headers, "Uber", 50)
    add(client, headers, "Swiggy", 300)
    names = [c["category"] for c in summary(client, headers)["categories"]]
    assert names == ["Food", "Transport"]


def test_uncategorised_spending_is_shown_as_uncategorized(client, headers):
    add(client, headers, "asdf qwer", 80)
    assert summary(client, headers)["categories"][0]["category"] == "Uncategorized"


def budget(client, headers, category_id, ratio):
    client.post("/budgets", headers=headers, json={"category_id": category_id, "ratio_percent": ratio})


def test_no_budget_status(client, headers, category_ids):
    add(client, headers, "Salary", 1000, "income")
    add(client, headers, "Swiggy", 100)
    assert summary(client, headers)["categories"][0]["status"] == "no_budget"


def test_budget_ok_warning_and_over(client, headers, category_ids):
    add(client, headers, "Salary", 1000, "income")
    budget(client, headers, category_ids["Food"], 20)            # limit: 200 of 1000

    add(client, headers, "Swiggy", 100)                           # 10%
    assert summary(client, headers)["categories"][0]["status"] == "ok"

    add(client, headers, "Zomato", 70)                            # 17% = 85% of the limit
    body = summary(client, headers)
    assert body["categories"][0]["status"] == "warning"
    assert body["alerts"][0]["level"] == "warning"

    add(client, headers, "Dominos", 100)                          # 27% > 20%
    body = summary(client, headers)
    assert body["categories"][0]["status"] == "over"
    assert body["alerts"][0]["level"] == "over"


def test_budget_without_income_says_no_income(client, headers, category_ids):
    budget(client, headers, category_ids["Food"], 20)
    add(client, headers, "Swiggy", 100)
    body = summary(client, headers)
    assert body["categories"][0]["status"] == "no_income"
    assert any(a["level"] == "info" for a in body["alerts"])


def test_savings_goal_appears_in_the_summary(client, headers):
    add(client, headers, "Salary", 1000, "income")
    add(client, headers, "Swiggy", 900)
    client.put("/savings-goal", headers=headers, json={"ratio_percent": 20})
    body = summary(client, headers)
    assert body["savings_goal"]["status"] == "over"
    assert body["savings_goal"]["max_spend"] == 800
    assert any(a["level"] == "over" for a in body["alerts"])


def test_no_goal_means_null(client, headers):
    assert summary(client, headers)["savings_goal"] is None


def test_summary_is_private(client):
    first = sign_up(client, "a@x.com")
    second = sign_up(client, "b@x.com")
    add(client, first, "Salary", 5000, "income")
    assert summary(client, second)["total_income"] == 0


def test_summary_needs_login(client):
    assert client.get("/summary").status_code == 401


# ---------- trend ----------
def test_trend_has_one_point_per_month_oldest_first(client, headers):
    points = client.get("/trend?months=3", headers=headers).json()
    assert len(points) == 3
    assert [p["month"] for p in points] == sorted(p["month"] for p in points)
    assert points[-1]["month"] == f"{TODAY.year}-{TODAY.month:02d}"


def test_trend_adds_up_income_and_expense(client, headers):
    add(client, headers, "Salary", 1000, "income")
    add(client, headers, "Swiggy", 200)
    add(client, headers, "Uber", 50)
    this_month = client.get("/trend?months=2", headers=headers).json()[-1]
    assert this_month["income"] == 1000 and this_month["expense"] == 250


def test_trend_limits(client, headers):
    assert client.get("/trend?months=0", headers=headers).status_code == 422
    assert client.get("/trend?months=25", headers=headers).status_code == 422