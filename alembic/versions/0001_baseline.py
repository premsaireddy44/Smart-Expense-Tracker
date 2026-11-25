"""Baseline: the tables exactly as Version 1 created them.

A database that already has these tables (yours) is NOT rebuilt. You mark it as
being at this step with:  alembic stamp 0001
A brand-new, empty database gets them created by:  alembic upgrade head
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.UniqueConstraint("name", name="categories_name_key"),
    )
    op.create_index("ix_categories_id", "categories", ["id"])

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("type", sa.Enum("income", "expense", name="transactiontype"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id")),
    )
    op.create_index("ix_transactions_id", "transactions", ["id"])

    op.create_table(
        "budgets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ratio_percent", sa.Float(), nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id")),
    )
    op.create_index("ix_budgets_id", "budgets", ["id"])

    op.create_table(
        "savings_goals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ratio_percent", sa.Float(), nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.UniqueConstraint("owner_id", name="savings_goals_owner_id_key"),
    )
    op.create_index("ix_savings_goals_id", "savings_goals", ["id"])


def downgrade():
    op.drop_table("savings_goals")
    op.drop_table("budgets")
    op.drop_table("transactions")
    op.execute("DROP TYPE IF EXISTS transactiontype")
    op.drop_table("categories")
    op.drop_table("users")