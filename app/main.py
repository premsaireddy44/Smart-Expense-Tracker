from fastapi import FastAPI
from app.database import Base, engine
from app import models

app = FastAPI(title="Smart Expense Tracker API")

Base.metadata.create_all(bind=engine)

@app.get("/health")
def health_check():
    return {"status": "ok"}