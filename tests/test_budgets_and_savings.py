from datetime import datetime
from types import SimpleNamespace

from app.main import check_savings_goal
from tests.conftest import sign_up


# ---------- budgets ----------
def test_create_and_list_budget(client, headers, category_ids):
    response = client.post("/budgets", headers=headers, json={"ratio_percent": 30, "category_id": category_ids["Food"]})
    assert response.status_code == 200
    rows = client.get("/budgets", headers=headers).json()
    assert len(rows) == 1 and rows[0]["ratio_percent"] == 30


def test_one_budget_per_category(client, headers, category_ids):
    body = {"ratio_percent": 30, "category_id": category_ids["Food"]}
    client.post("/budgets", headers=headers, json=body)
    assert client.post("/budgets", headers=headers, json=body).status_code == 400


def test_budget_ratio_must_be_between_0_and_100(client, headers, category_ids):
    for bad in [0, -5, 101]:
        response = client.post("/budgets", headers=headers, json={"ratio_percent": bad, "category_id": category_ids["Food"]})
        assert response.status_code == 422, bad


def test_budget_for_missing_category_gives_404(client, headers):
    assert client.post("/budgets", headers=headers, json={"ratio_percent": 10, "category_id": 9999}).status_code == 404


def test_update_and_delete_budget(client, headers, category_ids):
    created = client.post("/budgets", headers=headers, json={"ratio_percent": 30, "category_id": category_ids["Food"]}).json()
    changed = client.put(f"/budgets/{created['id']}", headers=headers, json={"ratio_percent": 15})
    assert changed.json()["ratio_percent"] == 15
    assert client.delete(f"/budgets/{created['id']}", headers=headers).status_code == 200
    assert client.get("/budgets", headers=headers).json() == []


def test_user_cannot_touch_someone_elses_budget(client, category_ids):
    first = sign_up(client, "a@x.com")
    second = sign_up(client, "b@x.com")
    created = client.post("/budgets", headers=first, json={"ratio_percent": 30, "category_id": category_ids["Food"]}).json()
    assert client.put(f"/budgets/{created['id']}", headers=second, json={"ratio_percent": 1}).status_code == 403
    assert client.delete(f"/budgets/{created['id']}", headers=second).status_code == 403
    assert client.get("/budgets", headers=second).json() == []


# ---------- savings goal: the endpoints ----------
def test_no_goal_at_first(client, headers):
    assert client.get("/savings-goal", headers=headers).json() is None


def test_set_goal_then_change_it(client, headers):
    first = client.put("/savings-goal", headers=headers, json={"ratio_percent": 20})
    assert first.status_code == 200 and first.json()["ratio_percent"] == 20

    second = client.put("/savings-goal", headers=headers, json={"ratio_percent": 35})
    assert second.json()["ratio_percent"] == 35
    assert second.json()["id"] == first.json()["id"]          # changed, not duplicated
    assert client.get("/savings-goal", headers=headers).json()["ratio_percent"] == 35


def test_goal_ratio_must_be_between_0_and_100(client, headers):
    for bad in [0, -1, 150]:
        assert client.put("/savings-goal", headers=headers, json={"ratio_percent": bad}).status_code == 422, bad


def test_delete_goal(client, headers):
    client.put("/savings-goal", headers=headers, json={"ratio_percent": 20})
    assert client.delete("/savings-goal", headers=headers).status_code == 200
    assert client.get("/savings-goal", headers=headers).json() is None
    assert client.delete("/savings-goal", headers=headers).status_code == 404


def test_each_user_has_their_own_goal(client):
    first = sign_up(client, "a@x.com")
    second = sign_up(client, "b@x.com")
    client.put("/savings-goal", headers=first, json={"ratio_percent": 20})
    assert client.get("/savings-goal", headers=second).json() is None


# ---------- savings goal: the maths and the alerts ----------
# income 100,000 and a 20% goal means you may spend 80,000.
GOAL = SimpleNamespace(ratio_percent=20)
MID_MONTH = datetime(2026, 10, 15)


def test_plenty_of_room_is_ok():
    status, alerts = check_savings_goal(GOAL, 100000, 20000, 2026, 10, today=MID_MONTH)
    assert status.status == "ok"
    assert status.goal_amount == 20000
    assert status.max_spend == 80000
    assert status.left_to_spend == 60000
    assert alerts == []


def test_getting_close_gives_a_warning():
    status, alerts = check_savings_goal(GOAL, 100000, 70000, 2026, 10, today=MID_MONTH)
    assert status.status == "warning"
    assert alerts[0].level == "warning"
    assert "10,000 left" in alerts[0].message


def test_going_over_gives_a_red_alert():
    status, alerts = check_savings_goal(GOAL, 100000, 85000, 2026, 10, today=MID_MONTH)
    assert status.status == "over"
    assert status.left_to_spend == -5000
    assert alerts[0].level == "over"
    assert "5,000 more" in alerts[0].message


def test_no_income_means_it_cannot_be_checked():
    status, alerts = check_savings_goal(GOAL, 0, 500, 2026, 10, today=MID_MONTH)
    assert status.status == "no_income"
    assert alerts == []


def test_pace_alert_when_spending_too_fast():
    # 15 days in, 45,000 spent. At that pace: 45,000 / 15 * 31 = 93,000, above the 80,000 limit.
    status, alerts = check_savings_goal(GOAL, 100000, 45000, 2026, 10, today=MID_MONTH)
    assert status.status == "ok"
    assert status.projected_spend == 93000
    assert len(alerts) == 1
    assert "At this pace" in alerts[0].message


def test_no_pace_alert_when_pace_is_fine():
    status, alerts = check_savings_goal(GOAL, 100000, 20000, 2026, 10, today=MID_MONTH)
    assert status.projected_spend == 41333.33
    assert alerts == []


def test_no_pace_guess_in_the_first_days_of_the_month():
    # 2 days of data is too little to guess from.
    status, alerts = check_savings_goal(GOAL, 100000, 30000, 2026, 10, today=datetime(2026, 10, 2))
    assert status.projected_spend is None
    assert alerts == []


def test_no_pace_guess_for_past_months():
    status, alerts = check_savings_goal(GOAL, 100000, 30000, 2026, 9, today=MID_MONTH)
    assert status.projected_spend is None