from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app import db
from app.config import Settings, today_in_hotel
from app.main import create_app
from scripts.seed import seed

SECRET = "test-secret"
AUTH = {"X-Tool-Secret": SECRET}


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.sqlite3")
    conn = db.connect(path)
    seed(conn)
    conn.close()
    return path


@pytest.fixture
def make_client(db_path):
    def _make(**overrides):
        settings = Settings(**{"tool_secret": SECRET, "db_path": db_path, **overrides})
        return TestClient(create_app(settings))
    return _make


@pytest.fixture
def client(make_client):
    return make_client()


@pytest.fixture
def post(client):
    def _post(path, body):
        return client.post(f"/tools/{path}", json=body, headers=AUTH)
    return _post


def day(offset: int) -> str:
    return (today_in_hotel() + timedelta(days=offset)).isoformat()
