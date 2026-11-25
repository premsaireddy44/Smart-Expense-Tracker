"""Alembic's start-up file. It tells Alembic which database to change and what the tables should look like."""
from alembic import context
from sqlalchemy import create_engine

from app import models  # noqa: F401  (importing the models registers the tables)
from app.database import DATABASE_URL, Base

target_metadata = Base.metadata


def run_migrations_online():
    engine = create_engine(DATABASE_URL)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()