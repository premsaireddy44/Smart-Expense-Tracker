# Smart Expense Tracker

A personal finance web app. You add transactions, it sorts them into categories (memory + machine learning + keyword rules), warns you about budgets and savings goals, and shows analytics: 12-month trends, category changes, unusual spending, a month-end estimate, UK and India tax-year totals, a currency choice (rupee, pound, dollar, euro), a live exchange-rate converter and a home-currency comparison.

**Stack:** FastAPI · PostgreSQL · SQLAlchemy · Alembic · JWT + bcrypt · pandas · scikit-learn · plain HTML/CSS/JS (SVG charts, no libraries) · pytest

## Run it

```bash
python -m venv .myenv
.myenv\Scripts\activate            # Windows   (Mac/Linux: source .myenv/bin/activate)
pip install -r requirements.txt
```

Create a `.env` file (never commit it):

```
DATABASE_URL=postgresql://USER:PASSWORD@localhost:5432/expense_db
SECRET_KEY=put-a-long-random-text-here
# APP_ENV=production     <- add this on a real server: switches off /docs
```

Set up the database, add the categories, train the model, start the app:

```bash
alembic upgrade head               # existing database from Version 1? run  alembic stamp 0001  first, then this
python seed_categories.py
python train_model.py              # creates ml/model.joblib  (re-run any time)
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000

## The category model

`python train_model.py` prints a practice-exam report. Add `--use-my-data` to also learn from categories you chose yourself. `--final-exam` runs the locked test set; use it rarely, because it is the honest score.

Measured on 159 descriptions the model never saw while being built (written by the project author, so real-world accuracy may differ): **92% correct, 94% right whenever it answers, and it stays silent on vague text** like names or "payment" instead of guessing.

How a category is chosen, in order: 1. what *you* chose before for the same shop (memory) 2. the model and keyword rules together 3. nothing, and you choose.

## Currency

You pick the currency you spend in when you create an account (change it any time in **Account**). Saved amounts are never converted; only the symbol changes. You can also set a second "home" currency: Analytics then shows your spending in both. Live rates come from the European Central Bank through the free frankfurter.dev service (no key needed; the server needs internet for this one feature, and everything else works without it).

## Tests

```bash
python -m pytest -q
```

## Folders

| Path | What it is |
|---|---|
| `app/` | the backend: routes (`main.py`), database tables (`models.py`), request shapes (`schemas.py`), login (`auth.py`), `suggestions.py`, `ml_categorizer.py`, `analytics.py` |
| `alembic/` | database migrations |
| `ml/` | training data and the two exams |
| `frontend/` | the web pages (`js/` has one file per tab) |
| `tests/` | automatic tests |
| `learn/` | lessons explaining every feature |

## Roadmap

Version 3: currency and profile, recurring payments, receipt OCR. After that: deployment (Docker, hosted PostgreSQL, CI).