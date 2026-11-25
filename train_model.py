"""Trains the category model and saves it to ml/model.joblib.

Run from the project folder:
    python train_model.py                  train + practice-exam report
    python train_model.py --use-my-data    also learn from categories YOU chose in the app
    python train_model.py --final-exam     also run the locked exam (do this rarely!)

The practice exam (dev set) is for tuning. The locked exam is the honest score,
so look at it only when you have finished changing things.
"""
import argparse

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

from app import ml_categorizer
from ml.training_data import make_examples


def build_model():
    # Two views of the text: pieces of letters (survives typos) and whole words.
    letters = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), lowercase=True, sublinear_tf=True)
    words = TfidfVectorizer(analyzer="word", ngram_range=(1, 2), lowercase=True, sublinear_tf=True)
    return Pipeline([
        ("features", FeatureUnion([("letters", letters), ("words", words)])),
        ("classifier", LogisticRegression(max_iter=2000, C=8)),
    ])


def my_own_examples():
    """(description, category name) pairs that a real user chose by hand."""
    from app import models
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        rows = (
            db.query(models.Transaction.description, models.Category.name)
            .join(models.Category, models.Category.id == models.Transaction.category_id)
            .filter(models.Transaction.category_source.in_(["user", "accepted"]))
            .all()
        )
        return [(d, c) for d, c in rows]
    finally:
        db.close()


def exam(name, rows):
    """Score the real app logic (model + rules) on a list of (text, expected, type)."""
    right = wrong = silent_ok = missed = 0
    mistakes = []
    for text, expected, tx_type in rows:
        answer = ml_categorizer.combine(text, tx_type)
        got = answer[0] if answer else None
        if expected is None:
            if got is None: silent_ok += 1
            else: wrong += 1; mistakes.append((text, expected, got))
        elif got == expected: right += 1
        elif got is None: missed += 1; mistakes.append((text, expected, got))
        else: wrong += 1; mistakes.append((text, expected, got))
    labelled = sum(1 for r in rows if r[1] is not None)
    answered = right + wrong
    print(f"\n{name}: {len(rows)} descriptions")
    print(f"  correct: {right}/{labelled}  ({right / labelled:.0%})")
    print(f"  when it answered, it was right: {right / max(answered, 1):.0%}")
    print(f"  stayed quiet correctly on 'no clue' lines: {silent_ok}")
    for text, expected, got in mistakes:
        print(f"  x {text!r}: wanted {expected}, got {got}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--use-my-data", action="store_true")
    parser.add_argument("--final-exam", action="store_true")
    args = parser.parse_args()

    extra = my_own_examples() if args.use_my_data else None
    if extra is not None:
        print(f"Learning from {len(extra)} of your own categorised transactions.")
    texts, labels = make_examples(extra=extra)
    model = build_model()
    model.fit(texts, labels)
    joblib.dump(model, ml_categorizer.MODEL_FILE)
    print(f"Trained on {len(texts)} examples. Saved to {ml_categorizer.MODEL_FILE}")

    ml_categorizer._model = model
    from ml.dev_set import DEV_SET
    exam("Practice exam (dev set)", DEV_SET)
    if args.final_exam:
        from ml.locked_test_set import LOCKED_TEST_SET
        exam("LOCKED exam (honest score)", LOCKED_TEST_SET)


if __name__ == "__main__":
    main()