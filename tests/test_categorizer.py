from app.categorizer import suggest_category


def test_swiggy_is_food():
    assert suggest_category("Swiggy dinner", "expense") == "Food"


def test_capital_letters_and_punctuation_do_not_matter():
    assert suggest_category("DOMINO'S pizza!!", "expense") == "Food"


def test_whole_words_only():
    # "tea" is a Food word, but it is hidden inside "steak" and "team".
    assert suggest_category("steak", "expense") is None
    assert suggest_category("team outing", "expense") is None


def test_longest_keyword_wins():
    assert suggest_category("Amazon Prime renewal", "expense") == "Subscriptions"
    assert suggest_category("Train ticket IRCTC", "expense") == "Travel"


def test_amazon_alone_is_shopping():
    assert suggest_category("Amazon order", "expense") == "Shopping"


def test_income_only_matches_income_categories():
    assert suggest_category("Salary credited", "income") == "Salary"
    assert suggest_category("Salary credited", "expense") is None


def test_expense_words_do_not_match_income():
    assert suggest_category("Swiggy", "income") is None


def test_freelance_income():
    assert suggest_category("Freelance project payment", "income") == "Freelance Income"


def test_nothing_matches_returns_none():
    assert suggest_category("asdf qwer", "expense") is None


def test_category_name_itself_works_as_a_keyword():
    assert suggest_category("food", "expense") == "Food"
    assert suggest_category("Travel", "expense") == "Travel"
    assert suggest_category("salary", "income") == "Salary"