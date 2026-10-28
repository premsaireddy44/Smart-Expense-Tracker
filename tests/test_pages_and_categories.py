def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_login_page_is_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Smart Expense Tracker" in response.text


def test_dashboard_and_privacy_pages_are_served(client):
    assert client.get("/app.html").status_code == 200
    assert client.get("/privacy.html").status_code == 200


def test_api_docs_still_work_next_to_the_website(client):
    assert client.get("/docs").status_code == 200


def test_categories_have_a_kind(client, headers):
    kinds = {c["name"]: c["kind"] for c in client.get("/categories", headers=headers).json()}
    assert kinds["Salary"] == "income"
    assert kinds["Food"] == "expense"


def test_suggest_endpoint(client, headers, category_ids):
    data = client.get("/categories/suggest?description=Swiggy 250", headers=headers).json()
    assert data == {"category_id": category_ids["Food"], "category_name": "Food"}


def test_suggest_for_income(client, headers):
    data = client.get("/categories/suggest?description=Salary credited&type=income", headers=headers).json()
    assert data["category_name"] == "Salary"


def test_suggest_with_no_match_returns_nulls(client, headers):
    data = client.get("/categories/suggest?description=asdf qwer", headers=headers).json()
    assert data == {"category_id": None, "category_name": None}


def test_suggest_needs_a_description(client, headers):
    assert client.get("/categories/suggest", headers=headers).status_code == 422