from datetime import datetime

from app.main import check_savings_goal
from app.schemas import SavingsGoalOut
from tests.conftest import sign_up


def make_budget(client, headers, category_id, ratio=20):
    return client.post("/budgets", headers=headers, json={"category_id": category_id, "ratio_percent": ratio})


# ---------- budgets ----------
def test_create_and_list_budget(client, headers, category_ids):
    response = make_budget(client, headers, category_ids["Food"], 15)
    assert response.status_code == 200
    assert response.json()["ratio_percent"] == 15
    assert len(client.get("/budgets", headers=headers).json()) == 1


def test_one_budget_per_category(client, headers, category_ids):
    make_budget(client, headers, category_ids["Food"])
    assert make_budget(client, headers, category_ids["Food"]).status_code == 400


def test_ratio_must_be_between_0_and_100(client, headers, category_ids):
    assert make_budget(client, headers, category_ids["Food"], 0).status_code == 422
    assert make_budget(client, headers, category_ids["Food"], 101).status_code == 422
    assert make_budget(client, headers, category_ids["Food"], 100).status_code == 200


def test_budget_for_unknown_category_gives_404(client, headers):
    assert make_budget(client, headers, 9999).status_code == 404


def test_update_budget(client, headers, category_ids):
    created = make_budget(client, headers, category_ids["Food"], 10).json()
    response = client.put(f"/budgets/{created['id']}", headers=headers, json={"ratio_percent": 25})
    assert response.status_code == 200 and response.json()["ratio_percent"] == 25


def test_update_with_bad_ratio_gives_422(client, headers, category_ids):
    created = make_budget(client, headers, category_ids["Food"]).json()
    assert client.put(f"/budgets/{created['id']}", headers=headers, json={"ratio_percent": 500}).status_code == 422


def test_delete_budget(client, headers, category_ids):
    created = make_budget(client, headers, category_ids["Food"]).json()
    assert client.delete(f"/budgets/{created['id']}", headers=headers).status_code == 200
    assert client.get("/budgets", headers=headers).json() == []


def test_unknown_budget_gives_404(client, headers):
    assert client.put("/budgets/9999", headers=headers, json={"ratio_percent": 5}).status_code == 404
    assert client.delete("/budgets/9999", headers=headers).status_code == 404


def test_budgets_are_private(client, category_ids):
    first = sign_up(client, "a@x.com")
    second = sign_up(client, "b@x.com")
    created = make_budget(client, first, category_ids["Food"]).json()
    assert client.get("/budgets", headers=second).json() == []
    assert client.put(f"/budgets/{created['id']}", headers=second, json={"ratio_percent": 5}).status_code == 403
    assert client.delete(f"/budgets/{created['id']}", headers=second).status_code == 403


def test_two_users_can_budget_the_same_category(client, category_ids):
    first = sign_up(client, "a@x.com")
    second = sign_up(client, "b@x.com")
    assert make_budget(client, first, category_ids["Food"]).status_code == 200
    assert make_budget(client, second, category_ids["Food"]).status_code == 200


# ---------- savings goal (the routes) ----------
def test_no_goal_yet_returns_null(client, headers):
    assert client.get("/savings-goal", headers=headers).json() is None


def test_set_then_change_the_goal(client, headers):
    assert client.put("/savings-goal", headers=headers, json={"ratio_percent": 20}).json()["ratio_percent"] == 20
    assert client.put("/savings-goal", headers=headers, json={"ratio_percent": 30}).json()["ratio_percent"] == 30
    assert client.get("/savings-goal", headers=headers).json()["ratio_percent"] == 30


def test_goal_ratio_is_validated(client, headers):
    assert client.put("/savings-goal", headers=headers, json={"ratio_percent": 0}).status_code == 422
    assert client.put("/savings-goal", headers=headers, json={"ratio_percent": 101}).status_code == 422


def test_delete_goal(client, headers):
    client.put("/savings-goal", headers=headers, json={"ratio_percent": 20})
    assert client.delete("/savings-goal", headers=headers).status_code == 200
    assert client.delete("/savings-goal", headers=headers).status_code == 404


def test_goals_are_private(client):
    first = sign_up(client, "a@x.com")
    second = sign_up(client, "b@x.com")
    client.put("/savings-goal", headers=first, json={"ratio_percent": 20})
    assert client.get("/savings-goal", headers=second).json() is None


# ---------- savings goal (the maths) ----------
def goal(ratio):
    return SavingsGoalOut(id=1, ratio_percent=ratio)


def test_goal_ok_when_spending_is_low():
    status, alerts = check_savings_goal(goal(20), 1000, 300, 2020, 1)
    assert status.status == "ok" and alerts == []
    assert status.max_spend == 800 and status.goal_amount == 200 and status.left_to_spend == 500


def test_goal_warns_at_80_percent_of_the_limit():
    status, alerts = check_savings_goal(goal(20), 1000, 700, 2020, 1)   # limit 800, 87% used
    assert status.status == "warning" and alerts[0].level == "warning"


def test_goal_over_when_spending_passes_the_limit():
    status, alerts = check_savings_goal(goal(20), 1000, 900, 2020, 1)
    assert status.status == "over" and alerts[0].level == "over"
    assert status.left_to_spend == -100


def test_goal_without_income():
    status, alerts = check_savings_goal(goal(20), 0, 50, 2020, 1)
    assert status.status == "no_income" and alerts == []


def test_projection_for_the_current_month_warns():
    today = datetime(2026, 10, 10)
    # 400 spent in 10 days -> about 1240 by the end of a 31-day month, above the 800 limit
    status, alerts = check_savings_goal(goal(20), 1000, 400, 2026, 10, today=today)
    assert status.status == "ok"
    assert round(status.projected_spend) == 1240
    assert alerts and "At this pace" in alerts[0].message


def test_no_projection_in_the_first_days_or_other_months():
    early = datetime(2026, 10, 3)
    assert check_savings_goal(goal(20), 1000, 100, 2026, 10, today=early)[0].projected_spend is None
    assert check_savings_goal(goal(20), 1000, 100, 2025, 5, today=datetime(2026, 10, 20))[0].projected_spend is None