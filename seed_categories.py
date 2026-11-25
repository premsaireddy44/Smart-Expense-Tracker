"""Run once, AFTER  alembic upgrade head :   python seed_categories.py
Adds any missing categories to the database. Safe to run again."""

from app import models
from app.categorizer import KEYWORDS
from app.database import SessionLocal

# Every category the categorizer knows, plus "Other" for things nothing matches.
NAMES = list(KEYWORDS.keys()) + ["Other"]

db = SessionLocal()

added = []
for name in NAMES:
    exists = db.query(models.Category).filter(models.Category.name == name).first()
    if not exists:
        db.add(models.Category(name=name))
        added.append(name)

db.commit()
db.close()

if added:
    print("Added:", ", ".join(added))
else:
    print("All categories already exist.")