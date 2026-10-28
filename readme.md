# Smart Expense Tracker (Version 1)

A web app where you record your income and expenses, and it tells you where your money goes. It sorts each expense into a category automatically, lets you set monthly budgets and a savings goal, and warns you before you overspend.

## Why this project exists

Most people only notice they overspent after the month is over. This app shows the picture while the month is still running:

- **See everything in one place.** Total income, total spending and what is left, for any month.
- **Less typing.** Type "Swiggy dinner" and the app picks the Food category for you.
- **Stay in control.** Set a budget per category and a savings goal (for example, "keep 20% of my income"). You get a warning at 80% and an alert when you pass the limit.
- **Spot trends.** A six-month chart compares income and spending.

## Features

- Register and log in (passwords are hashed, login uses a signed token that expires after 24 hours)
- Add, edit, delete and filter transactions (income or expense)
- Automatic category suggestion (rule-based keyword matching)
- Monthly budgets per category
- Savings goal with a month-end spending forecast
- Alerts on the dashboard (on track, warning, over budget)
- Six-month income vs spending chart
- Delete your whole account and data from inside the app
- Privacy page, age confirmation (18+) at sign-up, keyboard-friendly pages with visible focus and a skip link

## Tech stack

| Part | Tool |
| --- | --- |
| Backend | Python, FastAPI |
| Database | PostgreSQL with SQLAlchemy |
| Validation | Pydantic |
| Login security | bcrypt password hashing, JWT tokens |
| Reports | SQL SUM / GROUP BY, pandas for the trend |
| Frontend | Plain HTML, CSS and JavaScript (no frameworks, no external scripts) |
| Tests | pytest (95 tests) |

## How it works (the flow)

1. The browser page (`frontend/`) sends a request to the API.
2. FastAPI (`app/main.py`) receives it. `schemas.py` checks the data is valid.
3. For private routes, `auth.py` reads the login token and finds the user.
4. `models.py` tables are read or written in PostgreSQL through `database.py`.
5. The answer goes back as JSON and the page shows it.

Every transaction, budget and goal is tied to its owner, so one user can never read or change another user's data.

## Project structure

```
app/
  database.py     connects to the database, gives each request a session
  models.py       the tables (users, categories, transactions, budgets, savings goals)
  schemas.py      what data is allowed in and out
  auth.py         password hashing, tokens, "who is logged in"
  categorizer.py  guesses a category from the description
  main.py         all the API routes
frontend/
  index.html      login and register page
  app.html        the dashboard
  privacy.html    privacy page
  css/style.css   styling
  js/             common.js (talks to the API), auth.js (login page), app.js (dashboard)
tests/            automated tests
seed_categories.py  adds the categories to the database (run once)
requirements.txt    Python packages
```

## Run it on your computer

You need Python 3.10+ and PostgreSQL.

1. Create a database, for example `expense_tracker`.
2. Create and activate a virtual environment, then install the packages:
   ```
   python -m venv .myenv
   .myenv\Scripts\activate        (Windows)
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in your values:
   ```
   DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/expense_tracker
   SECRET_KEY=a-long-random-text
   ```
4. Add the categories (once):
   ```
   python seed_categories.py
   ```
5. Start the app:
   ```
   uvicorn app.main:app --reload
   ```
6. Open http://127.0.0.1:8000 and register an account. API docs are at http://127.0.0.1:8000/docs.

## Run the tests

```
pytest
```

The tests use a temporary in-memory database, so your real data is never touched.

## Security notes

- Passwords are hashed with bcrypt, never stored as plain text.
- The login token is kept in the browser tab only (sessionStorage) and expires after 24 hours.
- Every private route checks the token, and every record is checked against its owner.
- Secrets live in `.env`, which is not uploaded to GitHub.

## Known limits in Version 1

- Month boundaries follow the server's timezone.
- Tests run on SQLite, not PostgreSQL.
- Amounts in alerts show no currency symbol.
- Logging out clears the token in the browser but does not cancel it on the server.

## Planned next (Version 1.1)

- Machine-learning category suggestions that learn from your own history
- Deployment online (Render with a hosted PostgreSQL)
- AI-written spending insights

## Author

Naredla Prem Sai Srinivasa Reddy, Hyderabad, India, psai48138@gmail.com
