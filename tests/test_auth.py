from datetime import datetime, timedelta, timezone

from jose import jwt

from app import auth, ratelimit
from tests.conftest import sign_up


def register(client, email="user@x.com", password="password123"):
    return client.post("/register", json={"email": email, "password": password})


def login(client, email="user@x.com", password="password123"):
    return client.post("/login", json={"email": email, "password": password})


# ---------- registering ----------
def test_register_works_and_hides_the_password(client):
    response = register(client)
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "user@x.com"
    assert "password" not in body and "hashed_password" not in body


def test_same_email_cannot_register_twice(client):
    register(client)
    response = register(client)
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]


def test_email_capitals_do_not_make_a_second_account(client):
    register(client, "user@x.com")
    assert register(client, "USER@X.COM").status_code == 400


def test_short_password_is_rejected(client):
    assert register(client, password="short").status_code == 422


def test_password_over_72_bytes_is_rejected(client):
    assert register(client, password="a" * 73).status_code == 422


def test_bad_email_is_rejected(client):
    assert register(client, email="not-an-email").status_code == 422


# ---------- logging in ----------
def test_login_returns_a_token(client):
    register(client)
    response = login(client)
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


def test_wrong_password_gives_401(client):
    register(client)
    assert login(client, password="wrongpass1").status_code == 401


def test_unknown_email_gives_401(client):
    assert login(client, email="nobody@x.com").status_code == 401


def test_login_ignores_email_capitals(client):
    register(client, "user@x.com")
    assert login(client, "User@X.com").status_code == 200


# ---------- protected routes ----------
def test_me_needs_a_token(client):
    assert client.get("/me").status_code == 401


def test_me_returns_the_logged_in_user(client):
    headers = sign_up(client)
    assert client.get("/me", headers=headers).json()["email"] == "user@x.com"


def test_fake_token_is_refused(client):
    assert client.get("/me", headers={"Authorization": "Bearer abc.def.ghi"}).status_code == 401


def test_expired_token_is_refused(client):
    register(client)
    expired = jwt.encode(
        {"sub": "user@x.com", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        auth.SECRET_KEY, algorithm=auth.ALGORITHM,
    )
    assert client.get("/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401


def test_token_for_a_deleted_user_is_refused(client):
    headers = sign_up(client)
    client.request("DELETE", "/me", headers=headers, json={"password": "password123"})
    assert client.get("/me", headers=headers).status_code == 401


# ---------- deleting an account ----------
def test_delete_account_needs_the_right_password(client):
    headers = sign_up(client)
    response = client.request("DELETE", "/me", headers=headers, json={"password": "wrongpass1"})
    assert response.status_code == 400
    assert client.get("/me", headers=headers).status_code == 200


def test_delete_account_removes_the_user_and_their_data(client):
    headers = sign_up(client)
    client.post("/transactions", headers=headers, json={"description": "x", "amount": 5, "type": "expense"})
    response = client.request("DELETE", "/me", headers=headers, json={"password": "password123"})
    assert response.status_code == 200
    assert login(client).status_code == 401


def test_delete_account_leaves_other_users_alone(client):
    first = sign_up(client, "a@x.com")
    second = sign_up(client, "b@x.com")
    client.post("/transactions", headers=second, json={"description": "keep me", "amount": 5, "type": "expense"})
    client.request("DELETE", "/me", headers=first, json={"password": "password123"})
    assert len(client.get("/transactions", headers=second).json()) == 1


# ---------- too many wrong passwords ----------
def test_five_wrong_passwords_lock_the_email_for_a_while(client):
    register(client)
    for _ in range(ratelimit.MAX_FAILURES):
        assert login(client, password="wrongpass1").status_code == 401
    # even the RIGHT password is refused now
    response = login(client)
    assert response.status_code == 429
    assert "Retry-After" in response.headers


def test_a_good_login_resets_the_counter(client):
    register(client)
    for _ in range(ratelimit.MAX_FAILURES - 1):
        login(client, password="wrongpass1")
    assert login(client).status_code == 200
    for _ in range(ratelimit.MAX_FAILURES - 1):
        assert login(client, password="wrongpass1").status_code == 401   # not locked yet


def test_lock_applies_per_email(client):
    register(client, "a@x.com")
    register(client, "b@x.com")
    for _ in range(ratelimit.MAX_FAILURES):
        login(client, "a@x.com", "wrongpass1")
    assert login(client, "b@x.com").status_code == 200