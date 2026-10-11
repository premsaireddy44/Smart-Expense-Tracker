from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import auth, models, schemas
from app.categorizer import suggest_category
from app.database import Base, engine, get_db

app = FastAPI(title="Smart Expense Tracker API")

Base.metadata.create_all(bind=engine)


# ---------------------------------------------------------------- helpers
def month_range(year: int, month: int):
    """First day of the month and first day of the next month."""
    start = datetime(year, month, 1)
    end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    return start, end


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
            models.Transaction.created_at >= start,
            models.Transaction.created_at < end,
        )
        .scalar()
    )
    return float(total)


# ---------------------------------------------------------------- basics
@app.get("/health")
def health_check():
    return {"status": "ok"}


# ---------------------------------------------------------------- users
@app.post("/register", response_model=schemas.UserOut)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(models.User).filter(models.User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = models.User(email=user.email, hashed_password=auth.hash_password(user.password))
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@app.post("/login")
def login(credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == credentials.email).first()
    if not user or not auth.verify_password(credentials.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    access_token = auth.create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/me", response_model=schemas.UserOut)
def read_current_user(current_user: models.User = Depends(auth.get_current_user)):
    return current_user


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
    name = suggest_category(description, tx_type)
    if name:
        match = db.query(models.Category).filter(models.Category.name == name).first()
        if match:
            return schemas.SuggestionOut(category_id=match.id, category_name=match.name)
    return schemas.SuggestionOut()


# ---------------------------------------------------------------- transactions
@app.post("/transactions", response_model=schemas.TransactionOut)
def create_transaction(
    transaction: schemas.TransactionCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    category_id = transaction.category_id
    if category_id is not None:
        require_category(db, category_id)
    else:
        name = suggest_category(transaction.description, transaction.type)
        if name:
            match = db.query(models.Category).filter(models.Category.name == name).first()
            if match:
                category_id = match.id

    values = dict(
        description=transaction.description,
        amount=transaction.amount,
        type=transaction.type,
        category_id=category_id,
        owner_id=current_user.id,
    )
    # A past date was chosen: use it. Otherwise the database stamps "now".
    if transaction.transaction_date and transaction.transaction_date != date.today():
        values["created_at"] = datetime.combine(transaction.transaction_date, datetime.now().time())

    new_transaction = models.Transaction(**values)
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
        query = query.filter(models.Transaction.created_at >= start, models.Transaction.created_at < end)
    if tx_type is not None:
        query = query.filter(models.Transaction.type == tx_type)
    if category_id is not None:
        query = query.filter(models.Transaction.category_id == category_id)

    return (
        query.order_by(models.Transaction.created_at.desc(), models.Transaction.id.desc())
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
    transaction.amount = updated.amount
    transaction.type = updated.type
    transaction.category_id = updated.category_id
    if updated.transaction_date and transaction.created_at.date() != updated.transaction_date:
        transaction.created_at = datetime.combine(updated.transaction_date, transaction.created_at.time())

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

    # 3. Spending per category in this month, biggest first
    total_spent = func.sum(models.Transaction.amount)
    rows = (
        db.query(models.Transaction.category_id, total_spent)
        .filter(
            models.Transaction.owner_id == current_user.id,
            models.Transaction.type == models.TransactionType.expense,
            models.Transaction.created_at >= start,
            models.Transaction.created_at < end,
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

    if income == 0 and expense > 0 and budgets:
        alerts.append(schemas.AlertOut(
            level="info",
            message="Add your income to see how spending compares with your budgets",
        ))

    return schemas.SummaryOut(
        period=f"{year}-{month:02d}",
        total_income=round(income, 2),
        total_expense=round(expense, 2),
        savings=round(savings, 2),
        savings_rate_percent=round(savings_rate, 1),
        categories=categories,
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

    start = datetime(int(labels[0][:4]), int(labels[0][5:]), 1)
    rows = (
        db.query(models.Transaction.created_at, models.Transaction.type, models.Transaction.amount)
        .filter(models.Transaction.owner_id == current_user.id, models.Transaction.created_at >= start)
        .all()
    )

    # pandas: one table of rows, then "sum amount for each (month, type)"
    df = pd.DataFrame(rows, columns=["created_at", "type", "amount"])
    totals = {}
    if not df.empty:
        df["month"] = [f"{d.year}-{d.month:02d}" for d in df["created_at"]]
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


# ---------------------------------------------------------------- frontend
# Must stay LAST: it serves the web pages for any URL the API routes above didn't claim.
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")