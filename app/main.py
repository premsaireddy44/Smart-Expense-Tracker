import calendar
import os
from contextlib import asynccontextmanager
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import analytics, auth, ml_categorizer, models, ratelimit, rates, schemas
from app.suggestions import suggest_category_for
from app.database import get_db

# On a live server set APP_ENV=production in the environment: the public /docs pages are then switched off.
IS_PRODUCTION = os.getenv("APP_ENV", "development") == "production"

@asynccontextmanager
async def lifespan(app):
    """Runs once when the server starts: load the category model, so the first suggestion is as fast as the rest."""
    ml_categorizer.load_model()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Smart Expense Tracker API",
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None,
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
)

@app.middleware("http")
async def no_cache_for_pages(request, call_next):
    """Always ask the server for fresh page files, so an old copy in the browser cannot break the app."""
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.endswith((".html", ".js", ".css")):
        response.headers["Cache-Control"] = "no-cache"
    return response


# Tables are created and changed by Alembic (see the alembic/ folder), not here.


# ---------------------------------------------------------------- helpers
def month_range(year: int, month: int):
    """First day of the month and first day of the next month (plain dates)."""
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return start, end


def to_money(value) -> Decimal:
    """Turn a number into exact money with 2 decimal places (0.1 + 0.2 never drifts)."""
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def check_period(year: Optional[int], month: Optional[int]):
    if (year is None) != (month is None):
        raise HTTPException(status_code=400, detail="Send both year and month, or neither")


def get_owned(db: Session, model, item_id: int, user: models.User, label: str):
    """Fetch one row by id. 404 if missing, 403 if it belongs to someone else."""
    item = db.query(model).filter(model.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    if item.owner_id != user.id:
        raise HTTPException(status_code=403, detail=f"Not authorized to change this {label.lower()}")
    return item


def require_category(db: Session, category_id: Optional[int]):
    if category_id is not None:
        if not db.query(models.Category).filter(models.Category.id == category_id).first():
            raise HTTPException(status_code=404, detail="Category not found")


def total_by_type(db: Session, user_id: int, tx_type, start, end) -> float:
    total = (
        db.query(func.coalesce(func.sum(models.Transaction.amount), 0))
        .filter(
            models.Transaction.owner_id == user_id,
            models.Transaction.type == tx_type,
            models.Transaction.transaction_date >= start,
            models.Transaction.transaction_date < end,
        )
        .scalar()
    )
    return float(total)


def check_savings_goal(goal, income, expense, year, month, today=None):
    """Compare this month's spending with the savings goal.
    Returns (SavingsStatus, list of alerts). Money shown in messages has no currency symbol."""
    alerts = []
    ratio = goal.ratio_percent

    if income <= 0:
        return schemas.SavingsStatus(
            ratio_percent=ratio, goal_amount=0, max_spend=0, spent=round(expense, 2),
            left_to_spend=0, status="no_income",
        ), alerts

    goal_amount = income * ratio / 100
    max_spend = income - goal_amount
    left = max_spend - expense

    if expense > max_spend:
        status = "over"
        alerts.append(schemas.AlertOut(
            level="over",
            message=f"You have spent {expense:,.0f}, which is {-left:,.0f} more than the "
                    f"{max_spend:,.0f} you can spend and still save {ratio:.0f}% of your income",
        ))
    elif expense >= 0.8 * max_spend:
        status = "warning"
        alerts.append(schemas.AlertOut(
            level="warning",
            message=f"Only {left:,.0f} left to spend if you want to save {ratio:.0f}% of your income",
        ))
    else:
        status = "ok"

    # For the current month, guess where spending will end up at today's pace.
    projected = None
    now = today or datetime.now()
    if year == now.year and month == now.month and now.day >= 5:
        days_in_month = calendar.monthrange(year, month)[1]
        projected = expense / now.day * days_in_month
        if status != "over" and projected > max_spend:
            alerts.append(schemas.AlertOut(
                level="warning",
                message=f"At this pace you will spend about {projected:,.0f} by the end of the month, "
                        f"more than the {max_spend:,.0f} that keeps your {ratio:.0f}% savings goal",
            ))

    return schemas.SavingsStatus(
        ratio_percent=ratio,
        goal_amount=round(goal_amount, 2),
        max_spend=round(max_spend, 2),
        spent=round(expense, 2),
        left_to_spend=round(left, 2),
        status=status,
        projected_spend=round(projected, 2) if projected is not None else None,
    ), alerts


# ---------------------------------------------------------------- basics
@app.get("/health")
def health_check():
    return {"status": "ok"}


# ---------------------------------------------------------------- users
@app.post("/register", response_model=schemas.UserOut)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(models.User).filter(func.lower(models.User.email) == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = models.User(
        email=user.email,
        hashed_password=auth.hash_password(user.password),
        living_currency=user.currency,
        home_currency=user.currency,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@app.post("/login")
def login(credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    wait = ratelimit.seconds_to_wait(credentials.email)
    if wait > 0:
        raise HTTPException(
            status_code=429,
            detail=f"Too many wrong passwords. Please try again in {wait // 60 + 1} minutes.",
            headers={"Retry-After": str(wait)},
        )

    user = db.query(models.User).filter(func.lower(models.User.email) == credentials.email).first()
    if not user or not auth.verify_password(credentials.password, user.hashed_password):
        ratelimit.record_failure(credentials.email)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    ratelimit.clear(credentials.email)
    access_token = auth.create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/me", response_model=schemas.UserOut)
def read_current_user(current_user: models.User = Depends(auth.get_current_user)):
    return current_user


@app.put("/me/profile", response_model=schemas.UserOut)
def update_profile(
    profile: schemas.ProfileIn,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Which currency you spend in, and which one you compare against. Amounts are not changed."""
    current_user.living_currency = profile.living_currency
    current_user.home_currency = profile.home_currency
    db.commit()
    db.refresh(current_user)
    return current_user


@app.get("/rates", response_model=schemas.RateOut)
def get_exchange_rate(
    base: str = Query(..., alias="from"),
    target: str = Query(..., alias="to"),
    amount: Optional[float] = Query(None, ge=0, le=9_999_999_999),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Live exchange rate, and optionally an amount converted with it."""
    base, target = base.upper(), target.upper()
    for code in (base, target):
        if code not in rates.SUPPORTED:
            raise HTTPException(status_code=422, detail=f"Unsupported currency: {code}")
    try:
        rate, day = rates.get_rate(base, target)
    except rates.RatesUnavailable:
        raise HTTPException(status_code=503, detail="Exchange rates are unavailable right now. Try again later.")
    converted = round(amount * rate, 2) if amount is not None else None
    return schemas.RateOut(base=base, target=target, rate=rate, date=day, amount=amount, converted=converted)


@app.delete("/me")
def delete_my_account(
    data: schemas.DeleteAccount,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Erase the user and everything they stored. The password is asked again as a safety check."""
    if not auth.verify_password(data.password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="That password is not correct")

    db.query(models.Transaction).filter(models.Transaction.owner_id == current_user.id).delete()
    db.query(models.Budget).filter(models.Budget.owner_id == current_user.id).delete()
    db.query(models.SavingsGoal).filter(models.SavingsGoal.owner_id == current_user.id).delete()
    db.delete(current_user)
    db.commit()
    return {"detail": "Your account and all your data were deleted"}


# ---------------------------------------------------------------- categories
@app.get("/categories", response_model=list[schemas.CategoryOut])
def list_categories(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(models.Category).order_by(models.Category.name).all()


@app.get("/categories/suggest", response_model=schemas.SuggestionOut)
def suggest(
    description: str = Query(..., min_length=1),
    tx_type: models.TransactionType = Query(models.TransactionType.expense, alias="type"),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    found = suggest_category_for(db, current_user.id, description, tx_type)
    return schemas.SuggestionOut(
        category_id=found.category_id,
        category_name=found.category_name,
        confidence=found.confidence,
        source=found.source,
    )


# ---------------------------------------------------------------- transactions
@app.post("/transactions", response_model=schemas.TransactionOut)
def create_transaction(
    transaction: schemas.TransactionCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    # Ask for a suggestion every time, even when the user picked a category themselves:
    # comparing the two is how we measure (and later improve) the suggestions.
    found = suggest_category_for(db, current_user.id, transaction.description, transaction.type)

    category_id = transaction.category_id
    if category_id is not None:
        require_category(db, category_id)
        # They kept our suggestion ("accepted") or chose something else ("user").
        category_source = "accepted" if category_id == found.category_id else "user"
    else:
        category_id = found.category_id          # nothing chosen: use the suggestion, if there is one
        category_source = found.source

    new_transaction = models.Transaction(
        description=transaction.description,
        amount=to_money(transaction.amount),
        type=transaction.type,
        transaction_date=transaction.transaction_date or date.today(),
        category_id=category_id,
        category_source=category_source,
        suggested_category_id=found.category_id,
        suggestion_confidence=found.confidence,
        owner_id=current_user.id,
    )
    db.add(new_transaction)
    db.commit()
    db.refresh(new_transaction)
    return new_transaction


@app.get("/transactions", response_model=list[schemas.TransactionOut])
def list_transactions(
    year: Optional[int] = Query(None, ge=2000, le=2100),
    month: Optional[int] = Query(None, ge=1, le=12),
    tx_type: Optional[models.TransactionType] = Query(None, alias="type"),
    category_id: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    check_period(year, month)

    query = db.query(models.Transaction).filter(models.Transaction.owner_id == current_user.id)
    if year is not None:
        start, end = month_range(year, month)
        query = query.filter(models.Transaction.transaction_date >= start, models.Transaction.transaction_date < end)
    if tx_type is not None:
        query = query.filter(models.Transaction.type == tx_type)
    if category_id is not None:
        query = query.filter(models.Transaction.category_id == category_id)

    return (
        query.order_by(models.Transaction.transaction_date.desc(), models.Transaction.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@app.put("/transactions/{transaction_id}", response_model=schemas.TransactionOut)
def update_transaction(
    transaction_id: int,
    updated: schemas.TransactionCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    transaction = get_owned(db, models.Transaction, transaction_id, current_user, "Transaction")
    require_category(db, updated.category_id)

    transaction.description = updated.description
    transaction.amount = to_money(updated.amount)
    transaction.type = updated.type
    if updated.category_id != transaction.category_id:
        # The user changed the category by hand: remember that it was their choice.
        transaction.category_source = "user" if updated.category_id is not None else None
    transaction.category_id = updated.category_id
    if updated.transaction_date:
        transaction.transaction_date = updated.transaction_date

    db.commit()
    db.refresh(transaction)
    return transaction


@app.delete("/transactions/{transaction_id}")
def delete_transaction(
    transaction_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    transaction = get_owned(db, models.Transaction, transaction_id, current_user, "Transaction")
    db.delete(transaction)
    db.commit()
    return {"detail": "Transaction deleted successfully"}


# ---------------------------------------------------------------- budgets
@app.post("/budgets", response_model=schemas.BudgetOut)
def create_budget(
    budget: schemas.BudgetCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    require_category(db, budget.category_id)

    existing = (
        db.query(models.Budget)
        .filter(models.Budget.owner_id == current_user.id, models.Budget.category_id == budget.category_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Budget for this category already exists")

    new_budget = models.Budget(
        ratio_percent=budget.ratio_percent,
        category_id=budget.category_id,
        owner_id=current_user.id,
    )
    db.add(new_budget)
    db.commit()
    db.refresh(new_budget)
    return new_budget


@app.get("/budgets", response_model=list[schemas.BudgetOut])
def list_budgets(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(models.Budget).filter(models.Budget.owner_id == current_user.id).all()


@app.put("/budgets/{budget_id}", response_model=schemas.BudgetOut)
def update_budget(
    budget_id: int,
    data: schemas.BudgetUpdate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    budget = get_owned(db, models.Budget, budget_id, current_user, "Budget")
    budget.ratio_percent = data.ratio_percent
    db.commit()
    db.refresh(budget)
    return budget


@app.delete("/budgets/{budget_id}")
def delete_budget(
    budget_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    budget = get_owned(db, models.Budget, budget_id, current_user, "Budget")
    db.delete(budget)
    db.commit()
    return {"detail": "Budget deleted successfully"}


# ---------------------------------------------------------------- savings goal
@app.get("/savings-goal", response_model=Optional[schemas.SavingsGoalOut])
def get_savings_goal(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(models.SavingsGoal).filter(models.SavingsGoal.owner_id == current_user.id).first()


@app.put("/savings-goal", response_model=schemas.SavingsGoalOut)
def set_savings_goal(
    data: schemas.SavingsGoalIn,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Create the goal, or change it if one already exists."""
    goal = db.query(models.SavingsGoal).filter(models.SavingsGoal.owner_id == current_user.id).first()
    if goal:
        goal.ratio_percent = data.ratio_percent
    else:
        goal = models.SavingsGoal(ratio_percent=data.ratio_percent, owner_id=current_user.id)
        db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


@app.delete("/savings-goal")
def delete_savings_goal(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    goal = db.query(models.SavingsGoal).filter(models.SavingsGoal.owner_id == current_user.id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Savings goal not found")
    db.delete(goal)
    db.commit()
    return {"detail": "Savings goal deleted successfully"}


# ---------------------------------------------------------------- reports
@app.get("/summary", response_model=schemas.SummaryOut)
def get_summary(
    year: Optional[int] = Query(None, ge=2000, le=2100),
    month: Optional[int] = Query(None, ge=1, le=12),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    # 0. Which month? Default = current month
    check_period(year, month)
    if year is None:
        now = datetime.now()
        year, month = now.year, now.month
    start, end = month_range(year, month)

    # 1. Big totals
    income = total_by_type(db, current_user.id, models.TransactionType.income, start, end)
    expense = total_by_type(db, current_user.id, models.TransactionType.expense, start, end)
    savings = income - expense
    savings_rate = savings / income * 100 if income > 0 else 0.0

    # 2. Lookup tables: {1: "Food", ...} and {1: 30.0, ...}
    names = {c.id: c.name for c in db.query(models.Category).all()}
    budgets = {
        b.category_id: b.ratio_percent
        for b in db.query(models.Budget).filter(models.Budget.owner_id == current_user.id).all()
    }

    goal = db.query(models.SavingsGoal).filter(models.SavingsGoal.owner_id == current_user.id).first()

    # 3. Spending per category in this month, biggest first
    total_spent = func.sum(models.Transaction.amount)
    rows = (
        db.query(models.Transaction.category_id, total_spent)
        .filter(
            models.Transaction.owner_id == current_user.id,
            models.Transaction.type == models.TransactionType.expense,
            models.Transaction.transaction_date >= start,
            models.Transaction.transaction_date < end,
        )
        .group_by(models.Transaction.category_id)
        .order_by(total_spent.desc())
        .all()
    )

    # 4. Build the report
    categories = []
    alerts = []
    for category_id, amount in rows:
        amount = float(amount)
        name = names.get(category_id, "Uncategorized")
        ratio = budgets.get(category_id)
        percent = amount / income * 100 if income > 0 else 0.0

        if ratio is None:
            status = "no_budget"
        elif income == 0:
            status = "no_income"
        elif percent > ratio:
            status = "over"
            alerts.append(schemas.AlertOut(
                level="over",
                message=f"{name} is at {percent:.1f}% of your income, over your {ratio:.0f}% budget",
            ))
        elif percent >= 0.8 * ratio:
            status = "warning"
            alerts.append(schemas.AlertOut(
                level="warning",
                message=f"{name} is at {percent:.1f}% of your income, close to your {ratio:.0f}% budget",
            ))
        else:
            status = "ok"

        categories.append(
            schemas.CategorySpend(
                category=name,
                amount=round(amount, 2),
                percent_of_income=round(percent, 1),
                budget_ratio=ratio,
                status=status,
            )
        )

    # 5. Savings goal
    savings_status = None
    if goal:
        savings_status, goal_alerts = check_savings_goal(goal, income, expense, year, month)
        alerts.extend(goal_alerts)

    if income == 0 and expense > 0 and (budgets or goal):
        alerts.append(schemas.AlertOut(
            level="info",
            message="Add your income to see how spending compares with your budgets and savings goal",
        ))

    return schemas.SummaryOut(
        period=f"{year}-{month:02d}",
        total_income=round(income, 2),
        total_expense=round(expense, 2),
        savings=round(savings, 2),
        savings_rate_percent=round(savings_rate, 1),
        categories=categories,
        savings_goal=savings_status,
        alerts=alerts,
    )


@app.get("/trend", response_model=list[schemas.TrendPoint])
def get_trend(
    months: int = Query(6, ge=1, le=24),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    # The last N month labels, oldest first, e.g. ["2026-05", ..., "2026-10"]
    labels = []
    y, m = datetime.now().year, datetime.now().month
    for _ in range(months):
        labels.append(f"{y}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    labels.reverse()

    start = date(int(labels[0][:4]), int(labels[0][5:]), 1)
    rows = (
        db.query(models.Transaction.transaction_date, models.Transaction.type, models.Transaction.amount)
        .filter(models.Transaction.owner_id == current_user.id, models.Transaction.transaction_date >= start)
        .all()
    )

    # pandas: one table of rows, then "sum amount for each (month, type)"
    df = pd.DataFrame(rows, columns=["transaction_date", "type", "amount"])
    totals = {}
    if not df.empty:
        df["month"] = [f"{d.year}-{d.month:02d}" for d in df["transaction_date"]]
        df["type"] = [t.value for t in df["type"]]
        totals = df.groupby(["month", "type"])["amount"].sum().to_dict()

    return [
        schemas.TrendPoint(
            month=label,
            income=round(float(totals.get((label, "income"), 0)), 2),
            expense=round(float(totals.get((label, "expense"), 0)), 2),
        )
        for label in labels
    ]


# ---------------------------------------------------------------- analytics
@app.get("/analytics", response_model=schemas.AnalyticsOut)
def get_analytics(
    fy: str = Query("uk", pattern="^(uk|india)$"),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Deeper numbers for the Analytics tab. pandas does the maths in app/analytics.py."""
    rows = (
        db.query(
            models.Transaction.transaction_date,
            models.Transaction.amount,
            models.Transaction.type,
            models.Category.name,
            models.Transaction.description,
            models.Transaction.category_source,
            models.Transaction.suggested_category_id,
        )
        .outerjoin(models.Category, models.Category.id == models.Transaction.category_id)
        .filter(models.Transaction.owner_id == current_user.id)
        .all()
    )
    df = pd.DataFrame(rows, columns=["date", "amount", "type", "category", "description",
                                     "category_source", "suggested_category_id"])
    df["date"] = pd.to_datetime(df["date"])
    df["amount"] = df["amount"].astype(float)
    df["type"] = df["type"].map(lambda t: getattr(t, "value", t))
    df["category"] = df["category"].fillna("Uncategorized")
    return analytics.build_analytics(df, date.today(), fy)


# ---------------------------------------------------------------- frontend
# Must stay LAST: it serves the web pages for any URL the API routes above didn't claim.
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")