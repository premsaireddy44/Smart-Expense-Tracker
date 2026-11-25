"""Picks a category for a new transaction. Three helpers, in this order:

1. MEMORY  - what this user chose before for the same shop or wording.
2. MODEL   - the trained model (and the keyword rules as backup).
3. nothing - the user chooses.
"""
import re
from difflib import SequenceMatcher
from typing import NamedTuple, Optional

from sqlalchemy.orm import Session

from app import models
from app.categorizer import clean
from app.ml_categorizer import combine

# Words that say how something was paid, not what it was. They are ignored when matching.
FILLER_WORDS = {
    "paid", "payment", "to", "upi", "card", "pos", "online", "debit", "order", "bill", "txn", "ref",
    "monthly", "my", "today", "ltd", "india", "uk", "london", "the", "for", "at", "of", "and",
}
SIMILAR_ENOUGH = 0.85      # how alike two descriptions must be to count as "the same shop"
HOW_MANY_TO_CHECK = 500    # look only at the user's most recent labelled transactions


class Suggestion(NamedTuple):
    category_id: Optional[int]
    category_name: Optional[str]
    confidence: Optional[float]
    source: Optional[str]          # "memory", "model" or "rules"


NOTHING = Suggestion(None, None, None, None)


def memory_key(text: str) -> str:
    """'UPI Swiggy order 450' -> 'swiggy'. Digits and filler words are dropped."""
    words = re.sub(r"[0-9]+", " ", clean(text)).split()
    return " ".join(word for word in words if word not in FILLER_WORDS)


def from_memory(db: Session, user_id: int, description: str, tx_type) -> Suggestion:
    """Reuse the category this user picked before for a very similar description."""
    key = memory_key(description)
    if not key:
        return NOTHING

    past = (
        db.query(models.Transaction.description, models.Transaction.category_id)
        .filter(
            models.Transaction.owner_id == user_id,
            models.Transaction.type == tx_type,
            models.Transaction.category_id.isnot(None),
            models.Transaction.category_source.in_(["user", "accepted"]),   # only choices the user made
        )
        .order_by(models.Transaction.id.desc())
        .limit(HOW_MANY_TO_CHECK)
        .all()
    )

    votes = {}      # category_id -> [how many times, best similarity]
    for old_description, category_id in past:
        similarity = SequenceMatcher(None, key, memory_key(old_description)).ratio()
        if similarity >= SIMILAR_ENOUGH:
            entry = votes.setdefault(category_id, [0, 0.0])
            entry[0] += 1
            entry[1] = max(entry[1], similarity)
    if not votes:
        return NOTHING

    # Most votes wins. On a tie the first one found wins, which is the most recent one.
    category_id = max(votes, key=lambda c: votes[c][0])
    category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if category is None:
        return NOTHING
    return Suggestion(category.id, category.name, round(votes[category_id][1], 2), "memory")


def suggest_category_for(db: Session, user_id: int, description: str, tx_type) -> Suggestion:
    """The one function the routes call."""
    remembered = from_memory(db, user_id, description, tx_type)
    if remembered.category_id is not None:
        return remembered

    answer = combine(description, tx_type)
    if answer:
        name, confidence, source = answer
        category = db.query(models.Category).filter(models.Category.name == name).first()
        if category:
            return Suggestion(category.id, category.name, round(confidence, 2), source)
    return NOTHING