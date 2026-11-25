"""Version 2 foundation: exact money, a real spending date, safer rules, room for later features.

Every step below only ADDS or TIGHTENS. Nothing is thrown away, and every existing row is kept.
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def recreate_owner_fk(table):
    """Re-make the owner link so deleting a user also deletes their rows."""
    op.drop_constraint(f"{table}_owner_id_fkey", table, type_="foreignkey")
    op.create_foreign_key(f"{table}_owner_id_fkey", table, "users", ["owner_id"], ["id"], ondelete="CASCADE")


def upgrade():
    # ---------------- users: a profile, for currency and the AI helper later ----------------
    op.add_column("users", sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.add_column("users", sa.Column("living_currency", sa.String(3), server_default="INR", nullable=False))
    op.add_column("users", sa.Column("home_currency", sa.String(3), server_default="INR", nullable=False))
    op.add_column("users", sa.Column("nationality", sa.String(60), nullable=True))
    op.add_column("users", sa.Column("ai_insights_consent", sa.Boolean(), server_default=sa.false(), nullable=False))

    # ---------------- transactions: exact money ----------------
    op.alter_column(
        "transactions", "amount",
        existing_type=sa.Float(), type_=sa.Numeric(12, 2), existing_nullable=False,
        postgresql_using="round(amount::numeric, 2)",
    )

    # ---------------- transactions: the real spending date ----------------
    # Step 1: add it empty. Step 2: fill it from created_at. Step 3: make it required.
    op.add_column("transactions", sa.Column("transaction_date", sa.Date(), nullable=True))
    op.execute("UPDATE transactions SET transaction_date = COALESCE(created_at::date, CURRENT_DATE)")
    op.alter_column("transactions", "transaction_date", existing_type=sa.Date(),
                    nullable=False, server_default=sa.func.current_date())
    op.execute("UPDATE transactions SET created_at = now() WHERE created_at IS NULL")
    op.alter_column("transactions", "created_at", existing_type=sa.DateTime(timezone=True),
                    nullable=False, existing_server_default=sa.func.now())

    # ---------------- transactions: room for later features (all empty for now) ----------------
    op.add_column("transactions", sa.Column("suggested_category_id", sa.Integer(), nullable=True))
    op.create_foreign_key("transactions_suggested_category_id_fkey", "transactions", "categories",
                          ["suggested_category_id"], ["id"], ondelete="SET NULL")
    op.add_column("transactions", sa.Column("category_source", sa.String(10), nullable=True))
    op.add_column("transactions", sa.Column("suggestion_confidence", sa.Numeric(3, 2), nullable=True))
    op.add_column("transactions", sa.Column("source", sa.String(10), server_default="manual", nullable=False))
    op.add_column("transactions", sa.Column("payment_method", sa.String(20), nullable=True))
    op.add_column("transactions", sa.Column("currency", sa.String(3), nullable=True))
    op.add_column("transactions", sa.Column("exchange_rate", sa.Numeric(18, 8), nullable=True))
    op.add_column("transactions", sa.Column("rate_date", sa.Date(), nullable=True))
    op.add_column("transactions", sa.Column("home_amount", sa.Numeric(12, 2), nullable=True))

    # ---------------- transactions: safer rules ----------------
    op.alter_column("transactions", "owner_id", existing_type=sa.Integer(), nullable=False)
    recreate_owner_fk("transactions")
    op.create_index("ix_transactions_owner_date", "transactions", ["owner_id", "transaction_date"])

    # ---------------- budgets and savings goals: safer rules ----------------
    op.alter_column("budgets", "owner_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("budgets", "category_id", existing_type=sa.Integer(), nullable=False)
    recreate_owner_fk("budgets")
    op.create_unique_constraint("uq_budget_owner_category", "budgets", ["owner_id", "category_id"])

    op.alter_column("savings_goals", "owner_id", existing_type=sa.Integer(), nullable=False)
    recreate_owner_fk("savings_goals")


def downgrade():
    """Undo everything above. (Amounts keep their rounded values.)"""
    op.drop_constraint("savings_goals_owner_id_fkey", "savings_goals", type_="foreignkey")
    op.create_foreign_key("savings_goals_owner_id_fkey", "savings_goals", "users", ["owner_id"], ["id"])
    op.alter_column("savings_goals", "owner_id", existing_type=sa.Integer(), nullable=True)

    op.drop_constraint("uq_budget_owner_category", "budgets", type_="unique")
    op.drop_constraint("budgets_owner_id_fkey", "budgets", type_="foreignkey")
    op.create_foreign_key("budgets_owner_id_fkey", "budgets", "users", ["owner_id"], ["id"])
    op.alter_column("budgets", "category_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("budgets", "owner_id", existing_type=sa.Integer(), nullable=True)

    op.drop_index("ix_transactions_owner_date", table_name="transactions")
    op.drop_constraint("transactions_owner_id_fkey", "transactions", type_="foreignkey")
    op.create_foreign_key("transactions_owner_id_fkey", "transactions", "users", ["owner_id"], ["id"])
    op.alter_column("transactions", "owner_id", existing_type=sa.Integer(), nullable=True)

    for column in ["home_amount", "rate_date", "exchange_rate", "currency", "payment_method", "source",
                   "suggestion_confidence", "category_source"]:
        op.drop_column("transactions", column)
    op.drop_constraint("transactions_suggested_category_id_fkey", "transactions", type_="foreignkey")
    op.drop_column("transactions", "suggested_category_id")

    op.alter_column("transactions", "created_at", existing_type=sa.DateTime(timezone=True), nullable=True)
    op.drop_column("transactions", "transaction_date")
    op.alter_column("transactions", "amount", existing_type=sa.Numeric(12, 2), type_=sa.Float(),
                    postgresql_using="amount::double precision")

    for column in ["ai_insights_consent", "nationality", "home_currency", "living_currency", "created_at"]:
        op.drop_column("users", column)