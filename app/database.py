import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()  # reads the .env file in the project folder

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing. Copy .env.example to .env and fill it in.")

# SQLite (used only by the tests) needs one extra setting; PostgreSQL does not.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Give each request its own database session, and always close it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()