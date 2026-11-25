import pytest

from app.ml_categorizer import MODEL_FILE, predict, smart_suggest

# These tests need the trained model. Create it once with:  python train_model.py
pytestmark = pytest.mark.skipif(not MODEL_FILE.exists(), reason="run train_model.py first")


def test_model_understands_a_typo():
    assert smart_suggest("swigy order", "expense") == "Food"


def test_model_picks_income_category_for_income():
    assert smart_suggest("monthly pay from company", "income") == "Salary"


def test_income_never_gets_an_expense_category():
    result = predict("pizza night", "income")
    assert result is None or result[0] in {"Salary", "Freelance Income", "Investments"}


def test_junk_and_names_get_no_guess():
    for text in ["asdf qwer", "qzxv wplk", "Ramesh", "John Smith"]:
        assert smart_suggest(text, "expense") is None


def test_vague_words_get_no_guess():
    assert smart_suggest("payment", "expense") is None


def test_rules_still_work_as_backup():
    assert smart_suggest("tesco", "expense") == "Groceries"