"""Shared set-up for all tests.

The tests never touch your real Postgres database. Each test gets a brand-new
SQLite database that lives in memory and disappears afterwards. This works because
FastAPI lets us swap `get_db` for our own version (dependency_overrides).
"""
import os

# These must be set BEFORE the app is imported, so the app does not look for a real database.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "test-secret-key"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.categorizer import KEYWORDS
from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def session_factory():
    """A fresh empty database with the categories already added."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    db = factory()
    for name in list(KEYWORDS.keys()) + ["Other"]:
        db.add(models.Category(name=name))
    db.commit()
    db.close()

    yield factory
    engine.dispose()


@pytest.fixture()
def client(session_factory):
    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def category_ids(session_factory):
    """{"Food": 1, "Rent": 3, ...}"""
    db = session_factory()
    ids = {c.name: c.id for c in db.query(models.Category).all()}
    db.close()
    return ids


def sign_up(client, email="a@x.com", password="password1"):
    """Register + log in. Returns the headers to send with later requests."""
    client.post("/register", json={"email": email, "password": password})
    token = client.post("/login", json={"email": email, "password": password}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def headers(client):
    return sign_up(client)