from datetime import timedelta
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from conftest import sign_in
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from app.auth import COOKIE_NAME
from app.config import Settings
from app.main import create_app
from app.models import AuthSession, Feedback, GenerationRequest, Suggestion, User, utc_now
from app.services.auth import create_user, token_hash, verify_password

PAYLOAD = {"scene_hint": "A café", "selected_symbols": ["water"], "language": "en"}


def raw_login(client, email="owner@example.test", password="Owner-password-123!", **headers):
    return client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
        headers={"X-Requested-With": "OutliersAAC", "Origin": "http://testserver", **headers},
    )


def test_login_stores_only_password_and_token_hashes(application):
    with TestClient(application) as browser:
        response = raw_login(browser, email=" OWNER@EXAMPLE.TEST ")
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["id"] == application.state.test_user_id
        assert set(data) == {"user", "csrf_token"}
        cookie = response.headers["set-cookie"].lower()
        assert "httponly" in cookie and "samesite=lax" in cookie
        assert response.headers["cache-control"] == "no-store"
        raw = browser.cookies.get(COOKIE_NAME)
        with application.state.sessions() as db:
            session = db.get(AuthSession, token_hash(raw))
            assert session is not None and session.token_hash != raw
            user = db.get(User, session.user_id)
            assert user.password_hash.startswith("$argon2id$")
            assert verify_password("Owner-password-123!", user.password_hash)
            assert "Owner-password-123!" not in response.text
        assert browser.get("/api/auth/me").json() == data


def test_wrong_password_and_unknown_account_have_same_response(application):
    with TestClient(application) as browser:
        wrong = raw_login(browser, password="wrong")
        absent = raw_login(browser, email="absent@example.test")
        assert wrong.status_code == absent.status_code == 401
        assert wrong.json() == absent.json()
        assert COOKIE_NAME not in browser.cookies
    with application.state.sessions() as db:
        assert db.scalar(select(func.count()).select_from(AuthSession)) == 0


def test_disabled_account_cannot_login(application):
    with application.state.sessions() as db:
        db.get(User, application.state.test_user_id).is_active = False
        db.commit()
    with TestClient(application) as browser:
        assert raw_login(browser).status_code == 401


@pytest.mark.parametrize(
    "path,method",
    [
        ("/api/auth/me", "get"),
        ("/api/suggestions", "post"),
        ("/api/suggestions/reuse", "post"),
        (f"/api/requests/{uuid4()}/feedback", "put"),
        ("/api/auth/logout", "post"),
    ],
)
def test_endpoints_require_login(application, path, method):
    with TestClient(application) as browser:
        kwargs = {"json": PAYLOAD} if method == "post" else {}
        response = getattr(browser, method)(path, **kwargs)
        assert response.status_code == 401
        assert response.json()["error_code"] == "AUTHENTICATION_REQUIRED"


def test_image_endpoint_requires_login(application):
    with TestClient(application) as browser:
        response = browser.post(
            "/api/suggestions/image",
            data={"payload": "{}"},
            files={"image": ("x.png", b"fake", "image/png")},
        )
        assert response.status_code == 401


def test_app_redirects_to_login_but_health_is_public(application):
    with TestClient(application) as browser:
        response = browser.get("/app", follow_redirects=False)
        assert response.status_code == 303 and response.headers["location"] == "/"
        assert browser.get("/health").status_code == 200
        assert browser.get("/ready").status_code == 200
        assert browser.get("/static/login.js").status_code == 200


@pytest.mark.parametrize("csrf", [None, "wrong"])
def test_write_requires_csrf(application, csrf):
    with TestClient(application) as browser:
        sign_in(browser)
        if csrf is None:
            del browser.headers["X-CSRF-Token"]
        else:
            browser.headers["X-CSRF-Token"] = csrf
        response = browser.post("/api/suggestions", json=PAYLOAD)
        assert response.status_code == 403
        assert response.json()["error_code"] == "CSRF_FAILED"
    with application.state.sessions() as db:
        assert db.scalar(select(func.count()).select_from(GenerationRequest)) == 0


def test_login_and_authenticated_writes_reject_foreign_origin(application, client):
    assert raw_login(client, Origin="https://attacker.example").status_code == 403
    assert (
        client.post(
            "/api/suggestions", json=PAYLOAD, headers={"Origin": "https://attacker.example"}
        ).status_code
        == 403
    )
    with TestClient(application) as browser:
        response = browser.post(
            "/api/auth/login",
            json={
                "email": "owner@example.test",
                "password": "Owner-password-123!",
            },
        )
        assert response.status_code == 403


def test_session_expires_on_server_and_logout_revokes_cookie(client, application):
    raw = client.cookies.get(COOKIE_NAME)
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.set(COOKIE_NAME, raw)
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.clear()
    sign_in(client)
    with application.state.sessions() as db:
        session = db.get(AuthSession, token_hash(client.cookies.get(COOKIE_NAME)))
        session.expires_at = utc_now() - timedelta(seconds=1)
        db.commit()
    response = client.post("/api/suggestions", json=PAYLOAD)
    assert response.status_code == 401 and response.json()["error_code"] == "SESSION_EXPIRED"


def test_idle_session_and_disabled_user_are_denied(client, application):
    with application.state.sessions() as db:
        session = db.get(AuthSession, token_hash(client.cookies.get(COOKIE_NAME)))
        session.last_seen_at = utc_now() - timedelta(hours=2)
        db.commit()
    assert client.get("/api/auth/me").status_code == 401
    sign_in(client)
    with application.state.sessions() as db:
        db.get(User, application.state.test_user_id).is_active = False
        db.commit()
    assert client.get("/api/auth/me").status_code == 401


def test_session_survives_application_restart(client, application):
    settings = Settings(database_url=str(application.state.engine.url), _env_file=None)
    restarted = create_app(settings)
    with TestClient(restarted) as other:
        other.cookies.update(client.cookies)
        assert other.get("/api/auth/me").json()["user"]["id"] == application.state.test_user_id


def test_cookie_secure_setting(application):
    settings = Settings(
        database_url=str(application.state.engine.url), auth_cookie_secure=True, _env_file=None
    )
    with TestClient(create_app(settings), base_url="https://testserver") as browser:
        response = raw_login(browser, Origin="https://testserver")
        assert response.status_code == 200
        assert "; secure" in response.headers["set-cookie"].lower()
        assert browser.get("/api/auth/me").status_code == 200


def test_login_rate_limit(application):
    settings = Settings(
        database_url=str(application.state.engine.url), auth_login_max_attempts=2, _env_file=None
    )
    with TestClient(create_app(settings)) as browser:
        assert raw_login(browser, password="wrong").status_code == 401
        assert raw_login(browser, password="wrong").status_code == 401
        response = raw_login(browser)
        assert response.status_code == 429 and int(response.headers["retry-after"]) > 0


def test_login_validation_does_not_echo_password(application):
    with TestClient(application) as browser:
        password = "Do-not-echo-this-" * 100
        response = raw_login(browser, password=password)
        assert response.status_code == 422
        assert password not in response.text
        assert all("input" not in item for item in response.json()["detail"])


def test_duplicate_email_cannot_replace_existing_account(application):
    with pytest.raises(ValueError, match="already exists"):
        create_user("OWNER@example.test", "Another-password-123!", application.state.sessions)
    with application.state.sessions() as db:
        user = db.get(User, application.state.test_user_id)
        assert verify_password("Owner-password-123!", user.password_hash)


def test_two_accounts_are_isolated_for_feedback_regeneration_and_reuse(client, application):
    create_user("second@example.test", "Second-password-123!", application.state.sessions)
    first = client.post("/api/suggestions", json=PAYLOAD).json()
    chosen = first["suggestions"][0]["id"]
    feedback = f"/api/requests/{first['request_id']}/feedback"
    assert (
        client.put(feedback, json={"action": "accepted", "suggestion_id": chosen}).status_code
        == 200
    )
    with TestClient(application) as other:
        sign_in(other, "second@example.test", "Second-password-123!")
        assert other.post("/api/suggestions/reuse", json=PAYLOAD).json() == {"suggestions": []}
        for body in ({"action": "rejected"}, {"action": "accepted", "suggestion_id": chosen}):
            assert other.put(feedback, json=body).status_code == 404
        response = other.post(
            "/api/suggestions", json=PAYLOAD | {"parent_request_id": first["request_id"]}
        )
        assert response.status_code == 404
        response = other.post(
            "/api/suggestions", json=PAYLOAD | {"user_id": application.state.test_user_id}
        )
        assert response.status_code == 422
        own = other.post("/api/suggestions", json=PAYLOAD).json()
        assert (
            other.put(
                f"/api/requests/{own['request_id']}/feedback",
                json={
                    "action": "accepted",
                    "suggestion_id": own["suggestions"][0]["id"],
                },
            ).status_code
            == 200
        )
    results = client.post("/api/suggestions/reuse", json=PAYLOAD).json()["suggestions"]
    assert len(results) == 1 and results[0]["source_request_id"] == first["request_id"]
    with application.state.sessions() as db:
        assert db.get(Feedback, first["request_id"]).action == "accepted"
        assert (
            db.get(GenerationRequest, first["request_id"]).user_id == application.state.test_user_id
        )
        assert (
            db.get(GenerationRequest, own["request_id"]).user_id != application.state.test_user_id
        )


def test_regeneration_checks_every_ancestor(client, application):
    foreign = create_user(
        "foreign@example.test", "Foreign-password-123!", application.state.sessions
    )
    data = client.post("/api/suggestions", json=PAYLOAD).json()
    with application.state.sessions() as db:
        ancestor = GenerationRequest(
            user_id=foreign.id,
            scene_hint="A café",
            intent_text="",
            selected_symbols=["water"],
            language="en",
            image_supplied=False,
            provider="test",
            latency_ms=1,
        )
        db.add(ancestor)
        db.flush()
        db.get(GenerationRequest, data["request_id"]).parent_request_id = ancestor.id
        db.commit()
    response = client.post(
        "/api/suggestions", json=PAYLOAD | {"parent_request_id": data["request_id"]}
    )
    assert response.status_code == 404


def test_legacy_history_is_preserved_but_not_assigned_to_a_user(client, application):
    with application.state.sessions() as db:
        old = GenerationRequest(
            scene_hint="A café",
            intent_text="",
            selected_symbols=["water"],
            language="en",
            image_supplied=False,
            provider="old",
            latency_ms=1,
        )
        db.add(old)
        db.flush()
        item = Suggestion(request_id=old.id, text="Old personal sentence.", position=0)
        db.add(item)
        db.flush()
        db.add(Feedback(request_id=old.id, action="accepted", suggestion_id=item.id))
        db.commit()
        old_id = old.id
    assert client.post("/api/suggestions/reuse", json=PAYLOAD).json()["suggestions"] == []
    assert (
        client.put(f"/api/requests/{old_id}/feedback", json={"action": "rejected"}).status_code
        == 404
    )
    with application.state.sessions() as db:
        assert db.get(GenerationRequest, old_id).user_id is None
        assert db.get(Feedback, old_id).action == "accepted"


def test_ready_checks_alembic_heads_instead_of_literal(client, monkeypatch):
    assert client.get("/ready").status_code == 200
    monkeypatch.setattr("app.api.health.expected_heads", lambda: {"future_revision"})
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["error_code"] == "MIGRATIONS_REQUIRED"


def test_migration_preserves_populated_0001_database(tmp_path, monkeypatch):
    url = "sqlite:///" + (tmp_path / "legacy.db").as_posix()
    monkeypatch.setenv("DATABASE_URL", url)
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "0001")
    from app.database import make_database

    engine, sessions = make_database(url)
    try:
        with engine.begin() as connection:
            for key, parent in [("a", None), ("b", "a")]:
                connection.execute(
                    text(
                        "INSERT INTO generation_requests "
                        "(id,created_at,scene_hint,intent_text,selected_symbols,language,image_supplied,"
                        "provider,latency_ms,parent_request_id) "
                        "VALUES (:id,:now,'A café','','[\"water\"]','en',0,'mock',1,:parent)"
                    ),
                    {"id": key, "now": utc_now().isoformat(), "parent": parent},
                )
            connection.execute(
                text(
                    "INSERT INTO suggestions (id,request_id,text,position) VALUES ('s','a','Water.',0)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO feedback (request_id,action,suggestion_id,updated_at) "
                    "VALUES ('a','accepted','s',:now)"
                ),
                {"now": utc_now().isoformat()},
            )
        command.upgrade(cfg, "head")
        command.check(cfg)
        with engine.connect() as connection:
            assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
            assert connection.execute(
                text("SELECT id,user_id,parent_request_id FROM generation_requests ORDER BY id")
            ).all() == [("a", None, None), ("b", None, "a")]
            assert connection.execute(text("SELECT text FROM suggestions")).scalar_one() == "Water."
        with TestClient(create_app(Settings(database_url=url, _env_file=None))) as browser:
            assert browser.get("/ready").status_code == 200
        command.downgrade(cfg, "0001")
        with engine.connect() as connection:
            assert (
                connection.execute(text("SELECT count(*) FROM generation_requests")).scalar_one()
                == 2
            )
            assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
    finally:
        engine.dispose()


@pytest.mark.parametrize("cookie", ["forged", "a" * 43])
def test_forged_session_is_denied(application, cookie):
    with TestClient(application) as browser:
        browser.cookies.set(COOKIE_NAME, cookie)
        assert browser.get("/api/auth/me").status_code == 401


def test_password_reset_revokes_sessions(client, application, monkeypatch):
    from app import manage_users

    monkeypatch.setattr("sys.argv", ["manage_users", "reset-password", "owner@example.test"])
    monkeypatch.setattr(manage_users, "read_password", lambda: "Replacement-password-123!")
    manage_users.main()
    assert client.get("/api/auth/me").status_code == 401
    with TestClient(application) as browser:
        assert raw_login(browser).status_code == 401
        assert raw_login(browser, password="Replacement-password-123!").status_code == 200


def test_cookie_is_rotated_at_login(application):
    with TestClient(application) as browser:
        assert raw_login(browser).status_code == 200
        previous = browser.cookies.get(COOKIE_NAME)
        assert raw_login(browser).status_code == 200
        assert browser.cookies.get(COOKIE_NAME) != previous


def test_csrf_from_one_session_is_not_valid_in_another(client, application):
    with TestClient(application) as second:
        sign_in(second)
        second.headers["X-CSRF-Token"] = client.headers["X-CSRF-Token"]
        assert second.post("/api/suggestions", json=PAYLOAD).status_code == 403


def test_database_foreign_keys_enforce_valid_user(client, application):
    from sqlalchemy.exc import IntegrityError

    with application.state.sessions() as db:
        row = GenerationRequest(
            user_id=str(uuid4()),
            scene_hint="",
            intent_text="Water",
            selected_symbols=[],
            language="en",
            image_supplied=False,
            provider="test",
            latency_ms=1,
        )
        db.add(row)
        with pytest.raises(IntegrityError):
            db.commit()
