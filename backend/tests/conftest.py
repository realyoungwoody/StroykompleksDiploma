import os

os.environ["DATABASE_URL"] = "sqlite:///./test_stroykompleks.sqlite3"
os.environ["ADMIN_EMAIL"] = "admin@example.com"
os.environ["ADMIN_PASSWORD"] = "testing-password"
os.environ["SESSION_SECRET"] = "testing-session-secret-long-enough"
os.environ["LLM_MODE"] = "demo"

import pytest
from fastapi.testclient import TestClient
from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.seed import seed_database


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_database(db)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def admin_client(client):
    response = client.post(
        "/api/v1/admin/auth/login",
        json={"email": "admin@example.com", "password": "testing-password"},
    )
    assert response.status_code == 200
    return client
