from pydantic import BaseModel, EmailStr
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


class BudgetOut(BaseModel):
    id: int
    ratio_percent: float
    category_id: int

    class Config:
        from_attributes = True