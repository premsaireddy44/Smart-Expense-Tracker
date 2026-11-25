from app.categorizer import clean, suggest_category


def test_known_word_gives_its_category():
    assert suggest_category("Swiggy dinner", "expense") == "Food"
    assert suggest_category("Tesco shop", "expense") == "Groceries"


def test_capitals_and_punctuation_do_not_matter():
    assert suggest_category("DOMINO'S PIZZA!!", "expense") == "Food"


def test_whole_words_only():
    # "pg" is a Rent keyword, but it must not match inside "pgadmin"
    assert suggest_category("pgadmin licence", "expense") is None


def test_longest_keyword_wins():
    # "uber eats" (Food) is longer than "uber" (Transport)
    assert suggest_category("uber eats order", "expense") == "Food"


def test_income_only_matches_income_categories():
    assert suggest_category("salary credited", "income") == "Salary"
    assert suggest_category("salary credited", "expense") is None


def test_expense_never_gets_an_income_category():
    assert suggest_category("dividend", "expense") is None


def test_the_category_name_itself_works():
    assert suggest_category("food", "expense") == "Food"
    assert suggest_category("Travel", "expense") == "Travel"


def test_nothing_matches_gives_none():
    assert suggest_category("asdf qwer", "expense") is None


def test_clean_pads_and_simplifies():
    assert clean("Domino's  Pizza!") == " dominos pizza "


def test_accepts_the_enum_type_too():
    from app.models import TransactionType
    assert suggest_category("salary", TransactionType.income) == "Salary"