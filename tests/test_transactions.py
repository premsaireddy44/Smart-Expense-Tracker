from datetime import date, timedelta

from tests.conftest import sign_up


def add(client, headers, description="Swiggy dinner", amount=250, type="expense", **extra):
    body = {"description": description, "amount": amount, "type": type}
    body.update(extra)
    return client.post("/transactions", headers=headers, json=body)


# ---------- creating ----------
def test_create_transaction(client, headers):
    response = add(client, headers)
    assert response.status_code == 200
    data = response.json()
    assert data["description"] == "Swiggy dinner"
    assert data["amount"] == 250
    assert data["type"] == "expense"


def test_category_is_picked_automatically(client, headers, category_ids):
    response = add(client, headers, "Zomato lunch")
    assert response.json()["category_id"] == category_ids["Food"]


def test_income_gets_an_income_category(client, headers, category_ids):
    response = add(client, headers, "Salary", 50000, "income")
    assert response.json()["category_id"] == category_ids["Salary"]


def test_unknown_description_is_left_without_category(client, headers):
    response = add(client, headers, "asdf qwer")
    assert response.json()["category_id"] is None


def test_chosen_category_is_not_overwritten(client, headers, category_ids):
    response = add(client, headers, "Swiggy dinner", category_id=category_ids["Travel"])
    assert response.json()["category_id"] == category_ids["Travel"]


def test_category_that_does_not_exist_gives_404(client, headers):
    assert add(client, headers, category_id=9999).status_code == 404


def test_amount_must_be_above_zero(client, headers):
    assert add(client, headers, amount=0).status_code == 422
    assert add(client, headers, amount=-5).status_code == 422


def test_description_cannot_be_blank(client, headers):
    assert add(client, headers, description="   ").status_code == 422


def test_wrong_type_is_rejected(client, headers):
    assert add(client, headers, type="gift").status_code == 422


def test_date_can_be_in_the_past(client, headers):
    last_week = str(date.today() - timedelta(days=7))
    response = add(client, headers, transaction_date=last_week)
    assert response.status_code == 200
    assert response.json()["created_at"].startswith(last_week)


def test_date_far_in_the_future_is_rejected(client, headers):
    far_future = str(date.today() + timedelta(days=5))
    assert add(client, headers, transaction_date=far_future).status_code == 422


def test_tomorrow_is_allowed_for_timezone_differences(client, headers):
    tomorrow = str(date.today() + timedelta(days=1))
    assert add(client, headers, transaction_date=tomorrow).status_code == 200


# ---------- listing ----------
def test_list_shows_newest_first(client, headers):
    old_day = str(date.today() - timedelta(days=10))
    add(client, headers, "Old one", transaction_date=old_day)
    add(client, headers, "New one")
    names = [t["description"] for t in client.get("/transactions", headers=headers).json()]
    assert names == ["New one", "Old one"]


def test_filter_by_type(client, headers):
    add(client, headers, "Swiggy", 100, "expense")
    add(client, headers, "Salary", 5000, "income")
    rows = client.get("/transactions?type=income", headers=headers).json()
    assert [r["description"] for r in rows] == ["Salary"]


def test_filter_by_category(client, headers, category_ids):
    add(client, headers, "Swiggy")
    add(client, headers, "Uber ride")
    rows = client.get(f"/transactions?category_id={category_ids['Transport']}", headers=headers).json()
    assert [r["description"] for r in rows] == ["Uber ride"]


def test_filter_by_month(client, headers):
    this_month = date.today()
    long_ago = date(2020, 3, 10)
    add(client, headers, "Recent")
    add(client, headers, "Ancient", transaction_date=str(long_ago))

    rows = client.get("/transactions?year=2020&month=3", headers=headers).json()
    assert [r["description"] for r in rows] == ["Ancient"]
    rows = client.get(f"/transactions?year={this_month.year}&month={this_month.month}", headers=headers).json()
    assert [r["description"] for r in rows] == ["Recent"]


def test_year_without_month_gives_400(client, headers):
    assert client.get("/transactions?year=2026", headers=headers).status_code == 400


def test_paging_with_skip_and_limit(client, headers):
    for number in range(5):
        add(client, headers, f"Item {number}", 10 + number)
    first_page = client.get("/transactions?limit=2", headers=headers).json()
    second_page = client.get("/transactions?limit=2&skip=2", headers=headers).json()
    assert len(first_page) == 2 and len(second_page) == 2
    assert {t["id"] for t in first_page}.isdisjoint({t["id"] for t in second_page})


def test_limit_above_100_is_rejected(client, headers):
    assert client.get("/transactions?limit=500", headers=headers).status_code == 422


# ---------- changing and deleting ----------
def test_update_transaction(client, headers, category_ids):
    created = add(client, headers).json()
    changed = {"description": "Dominos", "amount": 400, "type": "expense", "category_id": category_ids["Food"]}
    response = client.put(f"/transactions/{created['id']}", headers=headers, json=changed)
    assert response.status_code == 200
    assert response.json()["description"] == "Dominos"
    assert response.json()["amount"] == 400


def test_update_unknown_id_gives_404(client, headers):
    body = {"description": "x", "amount": 1, "type": "expense"}
    assert client.put("/transactions/9999", headers=headers, json=body).status_code == 404


def test_delete_transaction(client, headers):
    created = add(client, headers).json()
    assert client.delete(f"/transactions/{created['id']}", headers=headers).status_code == 200
    assert client.get("/transactions", headers=headers).json() == []


def test_delete_unknown_id_gives_404(client, headers):
    assert client.delete("/transactions/9999", headers=headers).status_code == 404


# ---------- privacy between users ----------
def test_users_cannot_see_each_others_transactions(client):
    first = sign_up(client, "a@x.com")
    second = sign_up(client, "b@x.com")
    add(client, first, "Private thing")
    assert client.get("/transactions", headers=second).json() == []


def test_user_cannot_change_or_delete_someone_elses_transaction(client):
    first = sign_up(client, "a@x.com")
    second = sign_up(client, "b@x.com")
    created = add(client, first).json()

    body = {"description": "Hacked", "amount": 1, "type": "expense"}
    assert client.put(f"/transactions/{created['id']}", headers=second, json=body).status_code == 403
    assert client.delete(f"/transactions/{created['id']}", headers=second).status_code == 403
    assert client.get("/transactions", headers=first).json()[0]["description"] == "Swiggy dinner"