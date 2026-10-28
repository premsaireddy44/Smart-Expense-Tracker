from app import auth, models
from tests.conftest import sign_up


def test_register_works(client):
    response = client.post("/register", json={"email": "a@x.com", "password": "password1"})
    assert response.status_code == 200
    assert response.json()["email"] == "a@x.com"


def test_register_never_returns_the_password(client):
    response = client.post("/register", json={"email": "a@x.com", "password": "password1"})
    assert "password" not in response.text


def test_register_short_password_is_rejected(client):
    response = client.post("/register", json={"email": "a@x.com", "password": "short"})
    assert response.status_code == 422


def test_register_bad_email_is_rejected(client):
    response = client.post("/register", json={"email": "not-an-email", "password": "password1"})
    assert response.status_code == 422


def test_same_email_twice_gives_400_and_a_message(client):
    client.post("/register", json={"email": "a@x.com", "password": "password1"})
    response = client.post("/register", json={"email": "a@x.com", "password": "password1"})
    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"


def test_same_email_with_capital_letters_is_still_a_duplicate(client):
    client.post("/register", json={"email": "prem@example.com", "password": "password1"})
    response = client.post("/register", json={"email": "PREM@Example.com", "password": "password1"})
    assert response.status_code == 400


def test_login_works_with_capital_letters(client):
    client.post("/register", json={"email": "prem@example.com", "password": "password1"})
    response = client.post("/login", json={"email": "Prem@Example.com", "password": "password1"})
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_old_account_saved_with_capitals_can_still_log_in(client, session_factory):
    db = session_factory()
    db.add(models.User(email="Old@X.com", hashed_password=auth.hash_password("password1")))
    db.commit()
    db.close()

    response = client.post("/login", json={"email": "old@x.com", "password": "password1"})
    assert response.status_code == 200


def test_wrong_password_gives_401(client):
    client.post("/register", json={"email": "a@x.com", "password": "password1"})
    response = client.post("/login", json={"email": "a@x.com", "password": "wrong-password"})
    assert response.status_code == 401


def test_unknown_email_gives_401(client):
    response = client.post("/login", json={"email": "nobody@x.com", "password": "password1"})
    assert response.status_code == 401


def test_me_returns_the_logged_in_user(client, headers):
    assert client.get("/me", headers=headers).json()["email"] == "a@x.com"


def test_routes_need_a_token(client):
    for path in ["/me", "/transactions", "/budgets", "/summary", "/trend", "/categories", "/savings-goal"]:
        assert client.get(path).status_code == 401, path


def test_garbage_token_is_rejected(client):
    response = client.get("/me", headers={"Authorization": "Bearer abc"})
    assert response.status_code == 401


def test_delete_account_needs_the_right_password(client, headers):
    response = client.request("DELETE", "/me", headers=headers, json={"password": "wrong-password"})
    assert response.status_code == 400
    assert client.get("/me", headers=headers).status_code == 200   # still there


def test_delete_account_removes_everything(client, session_factory, category_ids):
    headers = sign_up(client)
    client.post("/transactions", headers=headers, json={"description": "Swiggy", "amount": 100, "type": "expense"})
    client.post("/budgets", headers=headers, json={"ratio_percent": 10, "category_id": category_ids["Food"]})
    client.put("/savings-goal", headers=headers, json={"ratio_percent": 20})

    response = client.request("DELETE", "/me", headers=headers, json={"password": "password1"})
    assert response.status_code == 200

    db = session_factory()
    assert db.query(models.User).count() == 0
    assert db.query(models.Transaction).count() == 0
    assert db.query(models.Budget).count() == 0
    assert db.query(models.SavingsGoal).count() == 0
    db.close()

    # the old token and the old password no longer work
    assert client.get("/me", headers=headers).status_code == 401
    login = client.post("/login", json={"email": "a@x.com", "password": "password1"})
    assert login.status_code == 401


def test_deleting_one_account_keeps_other_peoples_data(client):
    first = sign_up(client, "a@x.com")
    second = sign_up(client, "b@x.com")
    client.post("/transactions", headers=second, json={"description": "Zomato", "amount": 50, "type": "expense"})

    client.request("DELETE", "/me", headers=first, json={"password": "password1"})

    assert len(client.get("/transactions", headers=second).json()) == 1