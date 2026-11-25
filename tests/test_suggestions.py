"""Tests for the per-user memory and for suggestion tracking."""
from app.suggestions import memory_key
from tests.conftest import sign_up


def add(client, headers, description, category_id=None, amount=10, tx_type="expense"):
    body = {"description": description, "amount": amount, "type": tx_type}
    if category_id is not None:
        body["category_id"] = category_id
    response = client.post("/transactions", json=body, headers=headers)
    assert response.status_code == 200
    return response.json()


def test_memory_key_drops_numbers_and_filler_words():
    assert memory_key("UPI Swiggy order 450") == "swiggy"


def test_suggestion_has_confidence_and_source(client, headers, category_ids):
    found = client.get("/categories/suggest", params={"description": "swiggy"}, headers=headers).json()
    assert found["category_name"] == "Food"
    assert found["source"] in ("model", "rules")
    assert 0 < found["confidence"] <= 1


def test_no_guess_returns_empty_fields(client, headers, category_ids):
    found = client.get("/categories/suggest", params={"description": "xqzv"}, headers=headers).json()
    assert found["category_id"] is None and found["source"] is None


def test_memory_reuses_the_users_own_choice(client, headers, category_ids):
    # This user files "Zorbo Cafe" under Entertainment. Nothing else would guess that.
    add(client, headers, "Zorbo Cafe", category_ids["Entertainment"])
    found = client.get("/categories/suggest", params={"description": "zorbo cafe 250"}, headers=headers).json()
    assert found["category_name"] == "Entertainment"
    assert found["source"] == "memory"


def test_memory_is_private_to_each_user(client, headers, category_ids):
    add(client, headers, "Zorbo Cafe", category_ids["Entertainment"])
    other = sign_up(client, "other@x.com")
    found = client.get("/categories/suggest", params={"description": "zorbo cafe"}, headers=other).json()
    assert found["source"] != "memory"


def test_tracking_when_user_keeps_our_suggestion(client, headers, category_ids):
    tx = add(client, headers, "swiggy", category_ids["Food"])
    assert tx["category_source"] == "accepted"


def test_tracking_when_user_overrides(client, headers, category_ids):
    tx = add(client, headers, "swiggy", category_ids["Shopping"])
    assert tx["category_source"] == "user"


def test_tracking_when_category_left_empty(client, headers, category_ids):
    tx = add(client, headers, "swiggy")
    assert tx["category_id"] == category_ids["Food"]
    assert tx["category_source"] in ("model", "rules")


def test_editing_the_category_marks_it_as_users_choice(client, headers, category_ids):
    tx = add(client, headers, "swiggy")
    body = {"description": "swiggy", "amount": 10, "type": "expense", "category_id": category_ids["Shopping"]}
    edited = client.put(f"/transactions/{tx['id']}", json=body, headers=headers).json()
    assert edited["category_source"] == "user"