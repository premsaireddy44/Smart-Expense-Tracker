"""Shared test setup. Every test gets a brand-new, empty, in-memory database,
so tests never touch your real PostgreSQL data and never affect each other."""
import os

# These must be set BEFORE the app is imported, because the app reads them at import time.
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
from app import ratelimit


@pytest.fixture()
def session_factory():
    # StaticPool = one shared connection, so the in-memory database is the same everywhere.
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(session_factory):
    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    ratelimit.failed_logins.clear()      # forget failed logins from earlier tests
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def category_ids(session_factory):
    """Put every category in the database and return {"Food": 1, ...}."""
    db = session_factory()
    for name in list(KEYWORDS) + ["Other"]:
        db.add(models.Category(name=name))
    db.commit()
    result = {c.name: c.id for c in db.query(models.Category).all()}
    db.close()
    return result


def sign_up(client, email="user@x.com", password="password123"):
    """Register + log in. Returns the headers a logged-in browser would send."""
    client.post("/register", json={"email": email, "password": password})
    token = client.post("/login", json={"email": email, "password": password}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def headers(client):
    return sign_up(client)