from datetime import date

from tests.conftest import sign_up

TODAY = date.today()


def add(client, headers, description, amount, type="expense"):
    client.post("/transactions", headers=headers, json={"description": description, "amount": amount, "type": type})


def get_summary(client, headers):
    return client.get("/summary", headers=headers).json()


def test_empty_month(client, headers):
    data = get_summary(client, headers)
    assert data["total_income"] == 0
    assert data["total_expense"] == 0
    assert data["categories"] == []
    assert data["alerts"] == []
    assert data["savings_goal"] is None
    assert data["period"] == f"{TODAY.year}-{TODAY.month:02d}"


def test_totals_and_savings(client, headers):
    add(client, headers, "Salary", 50000, "income")
    add(client, headers, "Swiggy", 3000)
    add(client, headers, "Rent", 15000)
    data = get_summary(client, headers)
    assert data["total_income"] == 50000
    assert data["total_expense"] == 18000
    assert data["savings"] == 32000
    assert data["savings_rate_percent"] == 64.0


def test_categories_are_biggest_first_with_percent_of_income(client, headers):
    add(client, headers, "Salary", 50000, "income")
    add(client, headers, "Swiggy", 3000)
    add(client, headers, "Rent", 15000)
    categories = get_summary(client, headers)["categories"]
    assert [c["category"] for c in categories] == ["Rent", "Food"]
    assert categories[0]["percent_of_income"] == 30.0


def test_uncategorized_spending_is_listed(client, headers):
    add(client, headers, "Salary", 1000, "income")
    add(client, headers, "asdf qwer", 100)
    names = [c["category"] for c in get_summary(client, headers)["categories"]]
    assert "Uncategorized" in names


def test_budget_status_ok_warning_over(client, headers, category_ids):
    add(client, headers, "Salary", 10000, "income")
    for name, ratio in [("Food", 20), ("Rent", 20), ("Transport", 20)]:
        client.post("/budgets", headers=headers, json={"ratio_percent": ratio, "category_id": category_ids[name]})
    add(client, headers, "Swiggy", 500)       # 5% of income, budget 20%  -> ok
    add(client, headers, "Rent", 1700)        # 17% of income, budget 20% -> warning (80% or more)
    add(client, headers, "Uber ride", 2500)   # 25% of income, budget 20% -> over

    status = {c["category"]: c["status"] for c in get_summary(client, headers)["categories"]}
    assert status == {"Food": "ok", "Rent": "warning", "Transport": "over"}


def test_budget_alerts_are_listed(client, headers, category_ids):
    add(client, headers, "Salary", 10000, "income")
    client.post("/budgets", headers=headers, json={"ratio_percent": 10, "category_id": category_ids["Food"]})
    add(client, headers, "Swiggy", 2000)
    alerts = get_summary(client, headers)["alerts"]
    assert alerts[0]["level"] == "over"
    assert "Food" in alerts[0]["message"]


def test_category_without_budget_says_no_budget(client, headers):
    add(client, headers, "Salary", 10000, "income")
    add(client, headers, "Swiggy", 100)
    assert get_summary(client, headers)["categories"][0]["status"] == "no_budget"


def test_info_alert_when_budgets_exist_but_no_income(client, headers, category_ids):
    client.post("/budgets", headers=headers, json={"ratio_percent": 10, "category_id": category_ids["Food"]})
    add(client, headers, "Swiggy", 100)
    alerts = get_summary(client, headers)["alerts"]
    assert alerts[0]["level"] == "info"


def test_savings_goal_appears_in_the_summary(client, headers):
    client.put("/savings-goal", headers=headers, json={"ratio_percent": 20})
    add(client, headers, "Salary", 100000, "income")
    add(client, headers, "Rent", 90000)
    goal = get_summary(client, headers)["savings_goal"]
    assert goal["goal_amount"] == 20000
    assert goal["max_spend"] == 80000
    assert goal["status"] == "over"


def test_going_over_the_savings_goal_gives_an_alert(client, headers):
    client.put("/savings-goal", headers=headers, json={"ratio_percent": 20})
    add(client, headers, "Salary", 100000, "income")
    add(client, headers, "Rent", 90000)
    messages = [a["message"] for a in get_summary(client, headers)["alerts"]]
    assert any("save 20%" in m for m in messages)


def test_staying_within_the_savings_goal_gives_no_alert(client, headers):
    client.put("/savings-goal", headers=headers, json={"ratio_percent": 20})
    add(client, headers, "Salary", 100000, "income")
    add(client, headers, "Swiggy", 1000)
    data = get_summary(client, headers)
    assert data["savings_goal"]["status"] == "ok"
    assert [a for a in data["alerts"] if "save 20%" in a["message"]] == []


def test_summary_for_another_month(client, headers):
    client.post("/transactions", headers=headers, json={
        "description": "Salary", "amount": 777, "type": "income", "transaction_date": "2020-03-10"})
    data = client.get("/summary?year=2020&month=3", headers=headers).json()
    assert data["total_income"] == 777
    assert data["period"] == "2020-03"
    assert get_summary(client, headers)["total_income"] == 0


def test_summary_year_without_month_gives_400(client, headers):
    assert client.get("/summary?year=2026", headers=headers).status_code == 400


def test_summary_only_counts_your_own_money(client):
    first = sign_up(client, "a@x.com")
    second = sign_up(client, "b@x.com")
    add(client, first, "Salary", 50000, "income")
    assert get_summary(client, second)["total_income"] == 0


def test_trend_has_one_point_per_month_oldest_first(client, headers):
    add(client, headers, "Salary", 1000, "income")
    add(client, headers, "Swiggy", 300)
    points = client.get("/trend?months=6", headers=headers).json()
    assert len(points) == 6
    assert points[-1]["month"] == f"{TODAY.year}-{TODAY.month:02d}"
    assert points[-1]["income"] == 1000
    assert points[-1]["expense"] == 300
    assert points[0]["income"] == 0
    assert [p["month"] for p in points] == sorted(p["month"] for p in points)


def test_trend_months_must_be_between_1_and_24(client, headers):
    assert client.get("/trend?months=0", headers=headers).status_code == 422
    assert client.get("/trend?months=25", headers=headers).status_code == 422