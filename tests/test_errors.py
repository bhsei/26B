import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.providers.base import GeneratedSentences, ProviderUnavailable

PAYLOAD = {"scene_hint": "A café", "selected_symbols": ["water"], "language": "en"}


def test_request_not_found(client):
    response = client.post("/api/suggestions", json=PAYLOAD | {"parent_request_id": str(uuid4())})
    assert response.status_code == 404
    assert response.json() == {
        "detail": "Previous request not found.",
        "error_code": "REQUEST_NOT_FOUND",
    }


def test_changed_inputs(client):
    first = client.post("/api/suggestions", json=PAYLOAD).json()
    response = client.post(
        "/api/suggestions",
        json=PAYLOAD | {"selected_symbols": ["coffee"], "parent_request_id": first["request_id"]},
    )
    assert response.status_code == 409
    assert response.json()["error_code"] == "INPUT_CHANGED"


@pytest.mark.parametrize("body", [{}, PAYLOAD | {"language": "es"}, {"unexpected": True}])
def test_validation_error_keeps_detail_list(client, body):
    response = client.post("/api/suggestions", json=body)
    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"
    assert isinstance(response.json()["detail"], list)


@pytest.mark.parametrize(
    "data,expected_status,expected_code",
    [
        (b"not a photo", 415, "INVALID_IMAGE"),
        (b"x" * (5 * 1024 * 1024 + 1), 413, "IMAGE_TOO_LARGE"),
    ],
    ids=["invalid-image", "oversized-image"],
)

def test_image_error_codes(client, data, expected_status, expected_code):
    response = client.post(
        "/api/suggestions/image",
        data={"payload": json.dumps(PAYLOAD)},
        files={"image": ("photo.png", data, "image/png")},
    )
    assert response.status_code == expected_status
    assert response.json()["error_code"] == expected_code


def test_invalid_multipart_payload(client):
    response = client.post(
        "/api/suggestions/image",
        data={"payload": "{broken"},
        files={"image": ("photo.png", b"anything", "image/png")},
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "INVALID_PAYLOAD"


@pytest.mark.parametrize(
    "mode,status,code",
    [
        ("unavailable", 503, "PROVIDER_UNAVAILABLE"),
        ("failed", 502, "PROVIDER_FAILED"),
        ("invalid", 502, "INVALID_PROVIDER_OUTPUT"),
    ],
)
def test_provider_errors_hide_internal_details(application, mode, status, code):
    class Provider:
        name = "test"

        def generate(self, *args):
            if mode == "unavailable":
                raise ProviderUnavailable("private provider detail")
            if mode == "failed":
                raise RuntimeError("private provider detail")
            return GeneratedSentences(["x" * 301])

    app = create_app(
        Settings(database_url=str(application.state.engine.url), _env_file=None), Provider()
    )
    with TestClient(app) as client:
        response = client.post("/api/suggestions", json=PAYLOAD)
    assert response.status_code == status
    assert response.json()["error_code"] == code
    assert "private provider detail" not in response.text
