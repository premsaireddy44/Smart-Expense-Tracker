from datetime import datetime
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import Base, engine, get_db
from app import models, schemas, auth
from app.categorizer import suggest_category


app = FastAPI(title="Smart Expense Tracker API")

Base.metadata.create_all(bind=engine)

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/register", response_model=schemas.UserOut)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(models.User).filter(models.User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_pw = auth.hash_password(user.password)
    new_user = models.User(email=user.email, hashed_password=hashed_pw)

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user



@app.post("/login")
def login(credentials: schemas.UserCreate, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == credentials.email).first()

    if not user or not auth.verify_password(credentials.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    access_token = auth.create_access_token(data={"sub": user.email})

    return {"access_token": access_token, "token_type": "bearer"}



@app.get("/me", response_model=schemas.UserOut)
def read_current_user(current_user: models.User = Depends(auth.get_current_user)):
    return current_user



@app.post("/transactions", response_model=schemas.TransactionOut)
def create_transaction(
    transaction: schemas.TransactionCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    category_id = transaction.category_id

    if category_id is not None:
        if not db.query(models.Category).filter(models.Category.id == category_id).first():
            raise HTTPException(status_code=404, detail="Category not found")
    else:
        name = suggest_category(transaction.description, transaction.type)
        if name:
            match = db.query(models.Category).filter(models.Category.name == name).first()
            if match:
                category_id = match.id

    new_transaction = models.Transaction(
        description=transaction.description,
        amount=transaction.amount,
        type=transaction.type,
        category_id=category_id,
        owner_id=current_user.id,
    )
    db.add(new_transaction)
    db.commit()
    db.refresh(new_transaction)
    return new_transaction


@app.get("/transactions", response_model=list[schemas.TransactionOut])
def list_transactions(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(models.Transaction).filter(models.Transaction.owner_id == current_user.id).all()



@app.put("/transactions/{transaction_id}", response_model=schemas.TransactionOut)
def update_transaction(
    transaction_id: int,
    updated: schemas.TransactionCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    transaction = db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if transaction.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to edit this transaction")

    transaction.description = updated.description
    transaction.amount = updated.amount
    transaction.type = updated.type
    transaction.category_id = updated.category_id

    db.commit()
    db.refresh(transaction)
    return transaction


@app.delete("/transactions/{transaction_id}")
def delete_transaction(
    transaction_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    transaction = db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if transaction.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this transaction")

    db.delete(transaction)
    db.commit()
    return {"detail": "Transaction deleted successfully"}



@app.post("/budgets", response_model=schemas.BudgetOut)
def create_budget(
    budget: schemas.BudgetCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    category = db.query(models.Category).filter(models.Category.id == budget.category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    existing = db.query(models.Budget).filter(
        models.Budget.owner_id == current_user.id,
        models.Budget.category_id == budget.category_id,
    ).first()
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



@app.get("/categories", response_model=list[schemas.CategoryOut])
def list_categories(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(models.Category).order_by(models.Category.name).all()


def month_range(year: int, month: int):
    start = datetime(year, month, 1)
    end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    return start, end


def total_by_type(db: Session, user_id: int, tx_type, start, end):
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


@app.get("/summary", response_model=schemas.SummaryOut)
def get_summary(
    year: Optional[int] = Query(None, ge=2000, le=2100),
    month: Optional[int] = Query(None, ge=1, le=12),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    # 0. Which month? Default = current month
    if (year is None) != (month is None):
        raise HTTPException(status_code=400, detail="Send both year and month, or neither")
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
            alerts.append(f"{name}: {percent:.1f}% of income, over your {ratio:.0f}% budget")
        elif percent >= 0.8 * ratio:
            status = "warning"
            alerts.append(f"{name}: {percent:.1f}% of income, close to your {ratio:.0f}% budget")
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

    if income == 0 and expense > 0:
        alerts.append("Add your income to see budget alerts")

    return schemas.SummaryOut(
        period=f"{year}-{month:02d}",
        total_income=round(income, 2),
        total_expense=round(expense, 2),
        savings=round(savings, 2),
        savings_rate_percent=round(savings_rate, 1),
        categories=categories,
        alerts=alerts,
    )
    
    
