from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings
from app.main import create_app
from app.models import Feedback, GenerationRequest, Suggestion
from app.reuse_schemas import ReuseInput
from app.services.reuse import find_reusable_suggestions

ENDPOINT = "/api/suggestions/reuse"
PAYLOAD = {"scene_hint": "A café", "selected_symbols": ["water"], "language": "en"}
BASE_TIME = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
def seed_request(application):
    def seed(
        texts=("Water, please.",),
        *,
        action="accepted",
        selected=0,
        updated_at=BASE_TIME,
        suggestion_ids=None,
        **request_values,
    ):
        values = {
            "scene_hint": "A café",
            "intent_text": "",
            "selected_symbols": ["water"],
            "language": "en",
            "image_supplied": False,
            "provider": "test",
            "latency_ms": 1,
        }
        values.update(request_values)
        with application.state.sessions() as db:
            request = GenerationRequest(**values)
            db.add(request)
            db.flush()
            items = [
                Suggestion(
                    id=suggestion_ids[i] if suggestion_ids else str(uuid4()),
                    request_id=request.id,
                    text=text,
                    position=i,
                )
                for i, text in enumerate(texts)
            ]
            db.add_all(items)
            db.flush()
            if action is not None:
                db.add(
                    Feedback(
                        request_id=request.id,
                        action=action,
                        suggestion_id=items[selected].id if action == "accepted" else None,
                        updated_at=updated_at,
                    )
                )
            db.commit()
            return request.id, [item.id for item in items]

    return seed


def lookup(client, **updates):
    response = client.post(ENDPOINT, json=PAYLOAD | updates)
    assert response.status_code == 200, response.text
    return response.json()["suggestions"]


def test_empty_database_returns_empty_list(client):
    assert client.post(ENDPOINT, json=PAYLOAD).json() == {"suggestions": []}


def test_generation_acceptance_and_retrieval_flow(client):
    response = client.post("/api/suggestions", json=PAYLOAD)
    assert response.status_code == 201
    generated = response.json()
    chosen = generated["suggestions"][0]
    url = f"/api/requests/{generated['request_id']}/feedback"
    assert (
        client.put(url, json={"action": "accepted", "suggestion_id": chosen["id"]}).status_code
        == 200
    )
    assert lookup(client) == [
        {
            "text": chosen["text"],
            "source_request_id": generated["request_id"],
            "source_suggestion_id": chosen["id"],
        }
    ]
    assert client.put(url, json={"action": "rejected"}).status_code == 200
    assert lookup(client) == []


def test_returns_only_selected_sentence_with_source_ids(client, seed_request):
    request_id, ids = seed_request(("First.", "Second.", "Third."), selected=1)
    assert lookup(client) == [
        {"text": "Second.", "source_request_id": request_id, "source_suggestion_id": ids[1]}
    ]


@pytest.mark.parametrize("action", [None, "rejected"], ids=["no-feedback", "rejected"])
def test_requires_current_acceptance(client, seed_request, action):
    seed_request(action=action)
    assert lookup(client) == []


def test_feedback_updates_change_retrieval(client, seed_request):
    request_id, ids = seed_request(("First.", "Second."))
    url = f"/api/requests/{request_id}/feedback"
    assert lookup(client)[0]["text"] == "First."
    assert client.put(url, json={"action": "accepted", "suggestion_id": ids[1]}).status_code == 200
    assert lookup(client)[0]["text"] == "Second."
    assert client.put(url, json={"action": "rejected"}).status_code == 200
    assert lookup(client) == []


@pytest.mark.parametrize(
    "stored_values",
    [
        {"scene_hint": "On a bus"},
        {"intent_text": "I do not want water"},
        {"selected_symbols": ["coffee"]},
        {"language": "es"},
        {"image_supplied": True},
    ],
    ids=["scene", "intention", "symbols", "language", "photo"],
)
def test_excludes_nonmatching_sources(client, seed_request, stored_values):
    seed_request(**stored_values)
    assert lookup(client) == []


@pytest.mark.parametrize(
    "stored_symbols",
    [["water", "want"], ["want", "water", "water"]],
    ids=["different-order", "extra-repetition"],
)
def test_symbol_order_and_repetitions_matter(client, seed_request, stored_symbols):
    seed_request(selected_symbols=stored_symbols)
    assert lookup(client, selected_symbols=["want", "water"]) == []


def test_matching_repeated_symbols_are_preserved(client, seed_request):
    seed_request(selected_symbols=["water", "water"])
    assert len(lookup(client, selected_symbols=["water", "water"])) == 1


def test_trims_scene_and_intention_on_both_sides(client, seed_request):
    seed_request(scene_hint="\u2003A café\u00a0", intent_text="\tI want water\n")
    assert len(lookup(client, scene_hint=" A café ", intent_text=" I want water ")) == 1


@pytest.mark.parametrize(
    "stored_values",
    [{"scene_hint": "A CAFÉ"}, {"intent_text": "I WANT WATER"}],
    ids=["scene-case", "intention-case"],
)
def test_text_matching_is_case_sensitive(client, seed_request, stored_values):
    values = {"intent_text": "I want water"} | stored_values
    seed_request(**values)
    assert lookup(client, intent_text="I want water") == []


def test_intention_only_lookup(client, seed_request):
    seed_request(selected_symbols=[], intent_text="I want water")
    assert len(lookup(client, selected_symbols=[], intent_text="I want water")) == 1


def test_sorts_by_feedback_time_then_suggestion_id(client, seed_request):
    low = "00000000-0000-4000-8000-000000000001"
    high = "00000000-0000-4000-8000-000000000002"
    seed_request(("Older request, latest acceptance.",), updated_at=BASE_TIME + timedelta(days=1))
    seed_request(("Higher ID.",), suggestion_ids=[high])
    seed_request(("Lower ID.",), suggestion_ids=[low])
    assert [item["text"] for item in lookup(client)] == [
        "Older request, latest acceptance.",
        "Lower ID.",
        "Higher ID.",
    ]


def test_deduplicates_before_limiting_and_keeps_newest_source(client, seed_request):
    seed_request(("Fourth.",), updated_at=BASE_TIME)
    seed_request(("Third.",), updated_at=BASE_TIME + timedelta(seconds=1))
    seed_request(("Second.",), updated_at=BASE_TIME + timedelta(seconds=2))
    seed_request(("Water, please.",), updated_at=BASE_TIME + timedelta(seconds=3))
    newest_request, newest_ids = seed_request(
        ("  Water, please.  ",), updated_at=BASE_TIME + timedelta(seconds=4)
    )
    result = lookup(client)
    assert [item["text"] for item in result] == ["Water, please.", "Second.", "Third."]
    assert result[0]["source_request_id"] == newest_request
    assert result[0]["source_suggestion_id"] == newest_ids[0]


def test_continues_past_candidate_batch_for_matches(client, seed_request):
    seed_request(("A matching result.",), updated_at=BASE_TIME)
    for offset in range(105):
        seed_request(
            scene_hint="A different scene",
            updated_at=BASE_TIME + timedelta(seconds=offset + 1),
        )
    assert lookup(client)[0]["text"] == "A matching result."


def test_rejects_feedback_pointing_to_another_requests_suggestion(
    client, application, seed_request
):
    source_id, _ = seed_request()
    _, other_ids = seed_request(action="rejected", scene_hint="Elsewhere")
    with application.state.sessions() as db:
        db.get(Feedback, source_id).suggestion_id = other_ids[0]
        db.commit()
    assert lookup(client) == []


@pytest.mark.parametrize("sentence", ["   ", "x" * 301], ids=["blank", "too-long"])
def test_skips_invalid_legacy_sentences(client, seed_request, sentence):
    seed_request((sentence,))
    assert lookup(client) == []


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"intent_text": " "},
        PAYLOAD | {"selected_symbols": [" "]},
        PAYLOAD | {"selected_symbols": ["x" * 81]},
        PAYLOAD | {"selected_symbols": ["water"] * 21},
        PAYLOAD | {"scene_hint": "x" * 501},
        PAYLOAD | {"intent_text": "x" * 501},
        PAYLOAD | {"language": "es"},
        PAYLOAD | {"parent_request_id": str(uuid4())},
        PAYLOAD | {"parent_request_id": None},
        PAYLOAD | {"image_supplied": True},
        PAYLOAD | {"image": "photo.png"},
        PAYLOAD | {"unexpected": "field"},
    ],
    ids=[
        "empty",
        "blank-intention",
        "blank-symbol",
        "long-symbol",
        "many-symbols",
        "long-scene",
        "long-intention",
        "unsupported-language",
        "parent-id",
        "null-parent",
        "image-flag",
        "image-field",
        "unknown-field",
    ],
)
def test_invalid_reuse_input_uses_existing_error_handler(client, body):
    response = client.post(ENDPOINT, json=body)
    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"
    assert isinstance(response.json()["detail"], list)


def test_lookup_has_no_provider_call_and_preserves_all_records(application, seed_request):
    seed_request()

    def snapshot():
        with application.state.sessions() as db:
            return [
                db.execute(
                    select(model.__table__).order_by(next(iter(model.__table__.primary_key)))
                ).all()
                for model in (GenerationRequest, Suggestion, Feedback)
            ]

    class ProviderMustNotRun:
        name = "test"
        calls = 0

        def generate(self, *args):
            self.calls += 1
            raise AssertionError("Retrieval must not generate sentences.")

    before = snapshot()
    provider = ProviderMustNotRun()
    app = create_app(
        Settings(database_url=str(application.state.engine.url), _env_file=None), provider
    )
    with TestClient(app) as client:
        assert len(lookup(client)) == 1
        assert len(lookup(client)) == 1
    assert provider.calls == 0
    assert snapshot() == before


def test_service_can_be_used_without_http(application, seed_request):
    source_id, ids = seed_request()
    result = find_reusable_suggestions(ReuseInput(**PAYLOAD), application.state.sessions)
    assert str(result.suggestions[0].source_request_id) == source_id
    assert str(result.suggestions[0].source_suggestion_id) == ids[0]


def test_reuse_contract_is_in_openapi(client):
    schema = client.get("/openapi.json").json()
    operation = schema["paths"][ENDPOINT]["post"]
    assert "200" in operation["responses"]
    assert "422" in operation["responses"]
    fields = schema["components"]["schemas"]["ReuseInput"]["properties"]
    assert "parent_request_id" not in fields
    assert "image" not in fields
