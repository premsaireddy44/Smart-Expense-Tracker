def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_categories_need_login(client):
    assert client.get("/categories").status_code == 401


def test_categories_are_listed_alphabetically_with_a_kind(client, headers, category_ids):
    rows = client.get("/categories", headers=headers).json()
    names = [r["name"] for r in rows]
    assert names == sorted(names)
    kinds = {r["name"]: r["kind"] for r in rows}
    assert kinds["Salary"] == "income" and kinds["Food"] == "expense"


def test_suggest_needs_login(client):
    assert client.get("/categories/suggest?description=swiggy").status_code == 401


def test_suggest_finds_a_known_word(client, headers, category_ids):
    body = client.get("/categories/suggest?description=swiggy dinner", headers=headers).json()
    assert body["category_name"] == "Food"
    assert body["category_id"] == category_ids["Food"]


def test_suggest_respects_income(client, headers, category_ids):
    body = client.get("/categories/suggest?description=salary credited&type=income", headers=headers).json()
    assert body["category_name"] == "Salary"


def test_suggest_with_junk_gives_nothing(client, headers, category_ids):
    body = client.get("/categories/suggest?description=asdf qwer", headers=headers).json()
    assert body["category_id"] is None and body["category_name"] is None


def test_suggest_needs_a_description(client, headers):
    assert client.get("/categories/suggest?description=", headers=headers).status_code == 422


def test_login_page_is_served(client):
    response = client.get("/")
    assert response.status_code == 200 and "Smart Expense Tracker" in response.text


def test_dashboard_page_is_served(client):
    assert client.get("/app.html").status_code == 200


def test_privacy_page_is_served(client):
    assert client.get("/privacy.html").status_code == 200


def test_unknown_page_is_404(client):
    assert client.get("/nothing-here.html").status_code == 404


def test_model_and_source_files_are_not_public(client):
    for path in ["/ml/model.joblib", "/app/main.py", "/.env", "/train_model.py", "/../.env"]:
        assert client.get(path).status_code == 404


def test_pages_are_never_served_from_an_old_browser_copy(client):
    assert client.get("/js/common.js").headers["cache-control"] == "no-cache"
    assert client.get("/css/style.css").headers["cache-control"] == "no-cache"