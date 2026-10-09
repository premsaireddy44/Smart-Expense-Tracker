from pydantic import BaseModel, EmailStr, field_validator
from datetime import datetime
from typing import Optional
from app.models import TransactionType


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: EmailStr

    class Config:
        from_attributes = True
        
class CategoryOut(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class TransactionCreate(BaseModel):
    description: str
    amount: float
    type: TransactionType
    category_id: Optional[int] = None

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, value):
        if value <= 0:
            raise ValueError("Amount must be greater than 0")
        return value


class TransactionOut(BaseModel):
    id: int
    description: str
    amount: float
    type: TransactionType
    created_at: datetime
    category_id: Optional[int] = None

    class Config:
        from_attributes = True


class BudgetCreate(BaseModel):
    ratio_percent: float
    category_id: int

    @field_validator("ratio_percent")
    @classmethod
    def ratio_must_be_valid(cls, value):
        if value <= 0 or value > 100:
            raise ValueError("Ratio must be between 0 and 100")
        return value


class BudgetOut(BaseModel):
    id: int
    ratio_percent: float
    category_id: int

    class Config:
        from_attributes = True
        
        
class CategorySpend(BaseModel):
    category: str
    amount: float
    percent_of_income: float
    budget_ratio: Optional[float] = None
    status: str


class SummaryOut(BaseModel):
    period: str    
    total_income: float
    total_expense: float
    savings: float
    savings_rate_percent: float
    categories: list[CategorySpend]
    alerts: list[str]