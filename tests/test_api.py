from io import BytesIO
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import func, select

from app.config import Settings
from app.main import create_app
from app.models import Feedback, GenerationRequest
from app.providers.base import GeneratedSentences, ProviderUnavailable

PAYLOAD = {"scene_hint": "A café", "selected_symbols": ["water"], "language": "en"}


def generate(client, **updates):
    response = client.post("/api/suggestions", json=PAYLOAD | updates)
    assert response.status_code == 201, response.text
    return response.json()


def test_health_ready_and_demo(client):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/ready").status_code == 200
    assert "Demo mode" in client.get("/").text
    assert client.get("/static/app.js").status_code == 200


def test_generation_persists_and_survives_restart(client, application):
    data = generate(client)
    assert len(data["suggestions"]) == 3
    assert data["provider"] == "mock"
    assert data["image_analyzed"] is False
    with application.state.sessions() as db:
        assert db.get(GenerationRequest, data["request_id"]).selected_symbols == ["water"]
    # A second app process connects to the same file, not to in-memory state.
    other = create_app(Settings(database_url=str(application.state.engine.url), _env_file=None))
    with TestClient(other) as restarted:
        response = restarted.put(
            f"/api/requests/{data['request_id']}/feedback", json={"action": "rejected"}
        )
        assert response.status_code == 200


def test_feedback_is_idempotent_and_can_be_changed(client, application):
    data = generate(client)
    url = f"/api/requests/{data['request_id']}/feedback"
    body = {"action": "accepted", "suggestion_id": data["suggestions"][0]["id"]}
    for _ in range(2):
        assert client.put(url, json=body).status_code == 200
    with application.state.sessions() as db:
        assert db.scalar(select(func.count()).select_from(Feedback)) == 1
    assert client.put(url, json={"action": "rejected"}).status_code == 200
    with application.state.sessions() as db:
        assert db.get(Feedback, data["request_id"]).suggestion_id is None


def test_cannot_accept_another_requests_suggestion(client):
    a, b = generate(client), generate(client)
    response = client.put(
        f"/api/requests/{a['request_id']}/feedback",
        json={"action": "accepted", "suggestion_id": b["suggestions"][0]["id"]},
    )
    assert response.status_code == 422


def test_regeneration_excludes_entire_chain(client):
    a = generate(client)
    b = generate(client, parent_request_id=a["request_id"])
    assert {s["text"] for s in a["suggestions"]}.isdisjoint(s["text"] for s in b["suggestions"])
    c = generate(client, parent_request_id=b["request_id"])
    assert c["suggestions"] == []
    assert len(generate(client)["suggestions"]) == 3


def test_changed_intent_requires_new_chain(client):
    a = generate(client)
    response = client.post(
        "/api/suggestions",
        json=PAYLOAD | {"selected_symbols": ["coffee"], "parent_request_id": a["request_id"]},
    )
    assert response.status_code == 409


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"intent_text": "  "},
        {"selected_symbols": [" "]},
        PAYLOAD | {"language": "es"},
        PAYLOAD | {"intent_text": "a" * 501},
        PAYLOAD | {"unexpected": "field"},
        PAYLOAD | {"selected_symbols": ["water"] * 21},
    ],
)
def test_invalid_inputs(client, body):
    assert client.post("/api/suggestions", json=body).status_code == 422


def test_mock_does_not_misrepresent_free_text(client):
    assert generate(client, intent_text="I do not want water")["suggestions"] == []
    assert generate(client, selected_symbols=["water", "coffee"])["suggestions"] == []


@pytest.mark.parametrize(
    "body",
    [
        {"action": "accepted"},
        {"action": "rejected", "suggestion_id": str(uuid4())},
        {"action": "spoken"},
    ],
)
def test_invalid_feedback(client, body):
    data = generate(client)
    assert client.put(f"/api/requests/{data['request_id']}/feedback", json=body).status_code == 422


def test_unknown_request(client):
    assert (
        client.put(f"/api/requests/{uuid4()}/feedback", json={"action": "rejected"}).status_code
        == 404
    )
    assert (
        client.post(
            "/api/suggestions", json=PAYLOAD | {"parent_request_id": str(uuid4())}
        ).status_code
        == 404
    )


def image_bytes():
    stream = BytesIO()
    Image.new("RGB", (40, 40), "blue").save(stream, format="PNG")
    return stream.getvalue()


def test_photo_input(client):
    import json

    response = client.post(
        "/api/suggestions/image",
        data={"payload": json.dumps(PAYLOAD)},
        files={"image": ("photo.png", image_bytes(), "image/png")},
    )
    assert response.status_code == 201
    assert response.json()["image_supplied"] is True
    assert response.json()["image_analyzed"] is False


def test_invalid_photo_and_payload(client):
    import json

    response = client.post(
        "/api/suggestions/image",
        data={"payload": json.dumps(PAYLOAD)},
        files={"image": ("fake.png", b"not an image", "image/png")},
    )
    assert response.status_code == 415
    response = client.post(
        "/api/suggestions/image",
        data={"payload": "{bad json"},
        files={"image": ("photo.png", image_bytes(), "image/png")},
    )
    assert response.status_code == 422


def test_oversized_photo(client):
    import json

    response = client.post(
        "/api/suggestions/image",
        data={"payload": json.dumps(PAYLOAD)},
        files={"image": ("huge.png", b"x" * (5 * 1024 * 1024 + 1), "image/png")},
    )
    assert response.status_code == 413


def test_provider_failure_is_safe(application):
    class Broken:
        name = "test"

        def generate(self, *args):
            raise ProviderUnavailable("Sensitive provider detail")

    app = create_app(
        Settings(database_url=str(application.state.engine.url), _env_file=None), Broken()
    )
    with TestClient(app) as client:
        response = client.post("/api/suggestions", json=PAYLOAD)
        assert response.status_code == 503
        assert "Sensitive" not in response.text


def test_invalid_provider_output_is_not_saved(application):
    class Invalid:
        name = "test"

        def generate(self, *args):
            return GeneratedSentences(["x" * 301])

    app = create_app(
        Settings(database_url=str(application.state.engine.url), _env_file=None), Invalid()
    )
    with TestClient(app) as client:
        assert client.post("/api/suggestions", json=PAYLOAD).status_code == 502
    with application.state.sessions() as db:
        assert db.scalar(select(func.count()).select_from(GenerationRequest)) == 0


def test_cors_for_cboard(client):
    response = client.options(
        "/api/suggestions",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert (
        client.options(
            "/api/suggestions",
            headers={
                "Origin": "https://untrusted.example",
                "Access-Control-Request-Method": "POST",
            },
        ).status_code
        == 400
    )


def test_migration_roundtrip_and_schema_match(application):
    cfg = Config("alembic.ini")
    command.check(cfg)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    with TestClient(application) as client:
        assert client.get("/ready").status_code == 200


def test_readiness_requires_migration(tmp_path):
    app = create_app(
        Settings(database_url="sqlite:///" + (tmp_path / "empty.db").as_posix(), _env_file=None)
    )
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 503
