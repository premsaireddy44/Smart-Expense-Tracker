import enum

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Enum, Float, ForeignKey, Index, Integer,
    Numeric, String, UniqueConstraint,
)
from sqlalchemy.sql import func

from app.database import Base


class TransactionType(str, enum.Enum):
    income = "income"
    expense = "expense"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Profile. Used from Version 3 (currency conversion); safe defaults until then.
    living_currency = Column(String(3), nullable=False, server_default="INR")  # where they spend
    home_currency = Column(String(3), nullable=False, server_default="INR")    # what they convert to
    nationality = Column(String(60), nullable=True)                           # optional, separate from currency
    ai_insights_consent = Column(Boolean, nullable=False, server_default="false")  # for the future AI helper


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        # Reports always ask: "this user's transactions in this date range".
        Index("ix_transactions_owner_date", "owner_id", "transaction_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    description = Column(String, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)          # exact money, two decimal places
    type = Column(Enum(TransactionType), nullable=False)

    transaction_date = Column(Date, nullable=False, server_default=func.current_date())  # the day it was spent
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)  # when it was saved

    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)

    # What the app suggested and how the category was finally set (feeds the ML later).
    suggested_category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    category_source = Column(String(10), nullable=True)       # "user", "model", "rules" or "memory"
    suggestion_confidence = Column(Numeric(3, 2), nullable=True)

    # Where it came from, and how it was paid.
    source = Column(String(10), nullable=False, server_default="manual")  # "manual", "import" or "ocr"
    payment_method = Column(String(20), nullable=True)                    # "upi", "card", "cash", "bank"

    # Currency conversion (Version 3). Empty until then.
    currency = Column(String(3), nullable=True)
    exchange_rate = Column(Numeric(18, 8), nullable=True)
    rate_date = Column(Date, nullable=True)
    home_amount = Column(Numeric(12, 2), nullable=True)


class Budget(Base):
    __tablename__ = "budgets"
    __table_args__ = (
        # One budget per category per user, enforced by the database itself.
        UniqueConstraint("owner_id", "category_id", name="uq_budget_owner_category"),
    )

    id = Column(Integer, primary_key=True, index=True)
    ratio_percent = Column(Float, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)


class SavingsGoal(Base):
    """How much of their income a user wants to keep. One row per user."""

    __tablename__ = "savings_goals"

    id = Column(Integer, primary_key=True, index=True)
    ratio_percent = Column(Float, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)