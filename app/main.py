from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import Base, engine, get_db
from app import models, schemas, auth
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
    new_transaction = models.Transaction(
        description=transaction.description,
        amount=transaction.amount,
        type=transaction.type,
        category_id=transaction.category_id,
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