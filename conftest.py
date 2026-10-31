import os

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

load_dotenv()

from database import Base, get_db
from main import app
from models import User

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
    session.add(User(email="dummy@example.com", password_hash="not-a-real-hash"))
    session.commit()
    yield session
    session.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()