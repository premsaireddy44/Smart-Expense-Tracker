from datetime import date, datetime, timedelta
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, computed_field, field_validator

from app.categorizer import INCOME_CATEGORIES
from app.rates import SUPPORTED as SUPPORTED_CURRENCIES
from app.models import TransactionType


# ---------- Users ----------
def _check_currency(value):
    value = str(value).strip().upper()
    if value not in SUPPORTED_CURRENCIES:
        raise ValueError("Currency must be one of: " + ", ".join(SUPPORTED_CURRENCIES))
    return value


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    currency: str = "INR"          # the currency this person spends in

    @field_validator("currency")
    @classmethod
    def currency_must_be_supported(cls, value):
        return _check_currency(value)

    @field_validator("email")
    @classmethod
    def email_to_lowercase(cls, value):
        return str(value).strip().lower()

    @field_validator("password")
    @classmethod
    def password_must_be_strong_enough(cls, value):
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters")
        if len(value.encode("utf-8")) > 72:  # bcrypt only reads the first 72 bytes
            raise ValueError("Password must be 72 bytes or fewer")
        return value


class UserLogin(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def email_to_lowercase(cls, value):
        return str(value).strip().lower()


class UserOut(BaseModel):
    id: int
    email: EmailStr
    living_currency: str = "INR"
    home_currency: str = "INR"

    model_config = ConfigDict(from_attributes=True)


class ProfileIn(BaseModel):
    living_currency: str       # what you spend in
    home_currency: str         # what you compare against

    @field_validator("living_currency", "home_currency")
    @classmethod
    def currency_must_be_supported(cls, value):
        return _check_currency(value)


class RateOut(BaseModel):
    base: str
    target: str
    rate: float
    date: Optional[str] = None
    amount: Optional[float] = None
    converted: Optional[float] = None


# ---------- Categories ----------
class CategoryOut(BaseModel):
    id: int
    name: str

    @computed_field
    @property
    def kind(self) -> str:
        return "income" if self.name in INCOME_CATEGORIES else "expense"

    model_config = ConfigDict(from_attributes=True)


class SuggestionOut(BaseModel):
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    confidence: Optional[float] = None
    source: Optional[str] = None        # "memory", "model" or "rules"


# ---------- Transactions ----------
class TransactionCreate(BaseModel):
    description: str
    amount: float
    type: TransactionType
    category_id: Optional[int] = None
    transaction_date: Optional[date] = None

    @field_validator("description")
    @classmethod
    def description_must_not_be_blank(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Description can't be empty")
        return value

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, value):
        if value <= 0:
            raise ValueError("Amount must be greater than 0")
        if value > 9_999_999_999:
            raise ValueError("Amount is too large")
        return value

    @field_validator("transaction_date")
    @classmethod
    def date_must_not_be_in_future(cls, value):
        # One day of slack: a user ahead of the server's timezone can legitimately
        # be on "tomorrow" while the server still thinks it is today.
        if value is not None and value > date.today() + timedelta(days=1):
            raise ValueError("Date can't be in the future")
        return value


class TransactionOut(BaseModel):
    id: int
    description: str
    amount: float
    type: TransactionType
    transaction_date: date
    created_at: datetime
    category_id: Optional[int] = None
    category_source: Optional[str] = None   # "user", "accepted", "memory", "model", "rules" or empty

    model_config = ConfigDict(from_attributes=True)


# ---------- Budgets ----------
def _check_ratio(value):
    if value <= 0 or value > 100:
        raise ValueError("Ratio must be between 0 and 100")
    return value


class BudgetCreate(BaseModel):
    ratio_percent: float
    category_id: int

    @field_validator("ratio_percent")
    @classmethod
    def ratio_must_be_valid(cls, value):
        return _check_ratio(value)


class BudgetUpdate(BaseModel):
    ratio_percent: float

    @field_validator("ratio_percent")
    @classmethod
    def ratio_must_be_valid(cls, value):
        return _check_ratio(value)


class BudgetOut(BaseModel):
    id: int
    ratio_percent: float
    category_id: int

    model_config = ConfigDict(from_attributes=True)


# ---------- Savings goal ----------
class SavingsGoalIn(BaseModel):
    ratio_percent: float

    @field_validator("ratio_percent")
    @classmethod
    def ratio_must_be_valid(cls, value):
        return _check_ratio(value)


class SavingsGoalOut(BaseModel):
    id: int
    ratio_percent: float

    model_config = ConfigDict(from_attributes=True)


# ---------- Deleting an account ----------
class DeleteAccount(BaseModel):
    password: str


# ---------- Reports ----------
class CategorySpend(BaseModel):
    category: str
    amount: float
    percent_of_income: float
    budget_ratio: Optional[float] = None
    status: str


class AlertOut(BaseModel):
    level: str  # "over", "warning" or "info"
    message: str


class SavingsStatus(BaseModel):
    ratio_percent: float            # the goal, e.g. 20 (percent of income)
    goal_amount: float              # income x ratio, the money to keep
    max_spend: float                # income - goal_amount, the most you can spend
    spent: float                    # expenses so far this month
    left_to_spend: float            # max_spend - spent (negative when over)
    status: str                     # "ok", "warning", "over" or "no_income"
    projected_spend: Optional[float] = None   # month-end guess at the current pace


class SummaryOut(BaseModel):
    period: str
    total_income: float
    total_expense: float
    savings: float
    savings_rate_percent: float
    categories: list[CategorySpend]
    savings_goal: Optional[SavingsStatus] = None
    alerts: list[AlertOut]


class TrendPoint(BaseModel):
    month: str
    income: float
    expense: float


# ---------------------------------------------------------------- analytics
class MonthPoint(BaseModel):
    month: str
    income: float
    expense: float
    savings: float


class CategoryChange(BaseModel):
    category: str
    this_month: float
    last_month: float
    change_percent: Optional[float] = None


class Merchant(BaseModel):
    name: str
    total: float
    count: int


class WeekdaySpend(BaseModel):
    day: str
    total: float


class UnusualSpend(BaseModel):
    description: str
    category: str
    amount: float
    usual_limit: float
    date: str


class FinancialYear(BaseModel):
    label: str
    start: str
    income: float
    expense: float
    savings: float


class MonthEnd(BaseModel):
    spent_so_far: float
    estimate: float
    days_left: int


class SuggestionAccuracy(BaseModel):
    checked: int
    kept: int
    percent: Optional[int] = None


class AnalyticsOut(BaseModel):
    months: list[MonthPoint]
    category_changes: list[CategoryChange]
    top_merchants: list[Merchant]
    weekdays: list[WeekdaySpend]
    unusual: list[UnusualSpend]
    financial_year: FinancialYear
    month_end: MonthEnd
    suggestion_accuracy: SuggestionAccuracy
    insights: list[str]