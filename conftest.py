import os

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

load_dotenv()

from database import Base, get_db
from main import app

test_engine = create_engine(os.getenv("TEST_DATABASE_URL"))
TestingSession = sessionmaker(bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    Base.metadata.create_all(test_engine)
    yield
    Base.metadata.drop_all(test_engine)


@pytest.fixture
def db():
    session = TestingSession()
    session.execute(text("TRUNCATE click_events, links, users CASCADE"))
    session.commit()
    yield session
    session.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def login_headers(client, email="angella@example.com", password="password123"):
    creds = {"email": email, "password": password}
    client.post("/auth/register", json=creds)
    token = client.post("/auth/login", json=creds).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers(client):
    return login_headers(client)