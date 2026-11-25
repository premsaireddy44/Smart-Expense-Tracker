"""Loads the trained category model and combines it with the keyword rules.

The model is trained by train_model.py and saved as ml/model.joblib.
If that file is missing, the app keeps working with the keyword rules only.
"""
from pathlib import Path

import joblib

from app.categorizer import INCOME_CATEGORIES, suggest_category

MODEL_FILE = Path(__file__).resolve().parent.parent / "ml" / "model.joblib"
MIN_CONFIDENCE = 0.45      # below this the model says "I am not sure"
STRONG_CONFIDENCE = 0.80   # a model this sure may overrule a keyword rule
UNKNOWN = "Unknown"        # the model's "no clue" answer, never a real category

_model = None


def load_model():
    global _model
    if _model is None and MODEL_FILE.exists():
        _model = joblib.load(MODEL_FILE)
    return _model


def predict(description: str, tx_type):
    """Return (category_name, confidence) from the model, or None when it is unsure."""
    model = load_model()
    if model is None:
        return None

    want_income = str(getattr(tx_type, "value", tx_type)) == "income"
    probabilities = dict(zip(model.classes_, model.predict_proba([description])[0]))

    # The model has a special "Unknown" answer for text that carries no clue
    # (names, junk, vague words like "payment"). If that wins, make no guess.
    if max(probabilities, key=probabilities.get) == UNKNOWN:
        return None

    # Only look at categories that fit the type: income picks income categories.
    allowed = {
        name: score for name, score in probabilities.items()
        if name != UNKNOWN and (name in INCOME_CATEGORIES) == want_income
    }
    if not allowed:
        return None
    best_name = max(allowed, key=allowed.get)
    best_score = float(allowed[best_name])

    if best_score < MIN_CONFIDENCE:
        return None
    return str(best_name), round(best_score, 2)


def combine(description: str, tx_type):
    """Model + keyword rules together. Returns (name, confidence, source) or None.

    - Only one of them has an answer: use it.
    - Both agree: use it.
    - They disagree: trust the model only if it is very sure, otherwise trust the rule.
    (Measured on our practice exam, this beats using either one alone.)
    """
    guess = predict(description, tx_type)
    rule = suggest_category(description, tx_type)

    if guess and not rule:
        return guess[0], guess[1], "model"
    if rule and not guess:
        return rule, 1.0, "rules"
    if not guess and not rule:
        return None
    if guess[0] == rule:
        return guess[0], max(guess[1], 0.9), "model"
    if guess[1] >= STRONG_CONFIDENCE:
        return guess[0], guess[1], "model"
    return rule, 1.0, "rules"


def smart_suggest(description: str, tx_type):
    """Just the category name (or None). Kept for simple callers."""
    answer = combine(description, tx_type)
    return answer[0] if answer else None