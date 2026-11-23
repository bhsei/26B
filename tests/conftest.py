import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.auth import create_user


@pytest.fixture
def application(tmp_path, monkeypatch):
    url = "sqlite:///" + (tmp_path / "test.db").as_posix()
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(Config("alembic.ini"), "head")
    app = create_app(Settings(database_url=url, _env_file=None))
    user = create_user("owner@example.test", "Owner-password-123!", app.state.sessions)
    app.state.test_user_id = user.id
    return app


@pytest.fixture
def client(application):
    with TestClient(application) as client:
        sign_in(client)
        yield client


def sign_in(client, email="owner@example.test", password="Owner-password-123!"):
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
        headers={"X-Requested-With": "OutliersAAC", "Origin": str(client.base_url).rstrip("/")},
    )
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return response.json()
