"""Currency profile and exchange rates. The live rate service is replaced by a fake one."""
from app import rates
from tests.conftest import sign_up


def test_sign_up_with_a_currency(client):
    client.post("/register", json={"email": "g@x.com", "password": "password123", "currency": "gbp"})
    token = client.post("/login", json={"email": "g@x.com", "password": "password123"}).json()["access_token"]
    me = client.get("/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["living_currency"] == "GBP" and me["home_currency"] == "GBP"


def test_currency_defaults_to_rupees(client, headers):
    assert client.get("/me", headers=headers).json()["living_currency"] == "INR"


def test_unknown_currency_is_rejected_at_sign_up(client):
    r = client.post("/register", json={"email": "z@x.com", "password": "password123", "currency": "XYZ"})
    assert r.status_code == 422


def test_change_profile(client, headers):
    r = client.put("/me/profile", json={"living_currency": "GBP", "home_currency": "INR"}, headers=headers)
    assert r.status_code == 200
    me = client.get("/me", headers=headers).json()
    assert (me["living_currency"], me["home_currency"]) == ("GBP", "INR")


def test_profile_needs_login_and_valid_codes(client, headers):
    assert client.put("/me/profile", json={"living_currency": "GBP", "home_currency": "INR"}).status_code == 401
    assert client.put("/me/profile", json={"living_currency": "XXX", "home_currency": "INR"}, headers=headers).status_code == 422


def test_rate_converts_an_amount(client, headers, monkeypatch):
    monkeypatch.setattr(rates, "get_rate", lambda base, target: (0.0092, "2026-11-24"))
    body = client.get("/rates?from=INR&to=GBP&amount=10000", headers=headers).json()
    assert body["rate"] == 0.0092 and body["converted"] == 92.0 and body["date"] == "2026-11-24"


def test_rate_service_down_gives_503(client, headers, monkeypatch):
    def broken(base, target):
        raise rates.RatesUnavailable()
    monkeypatch.setattr(rates, "get_rate", broken)
    assert client.get("/rates?from=INR&to=GBP", headers=headers).status_code == 503


def test_rate_rejects_unknown_currency_and_needs_login(client, headers):
    assert client.get("/rates?from=INR&to=ABC", headers=headers).status_code == 422
    assert client.get("/rates?from=INR&to=GBP").status_code == 401


def test_same_currency_needs_no_lookup():
    assert rates.get_rate("INR", "INR") == (1.0, None)