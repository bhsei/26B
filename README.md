# The Outliers AAC backend starter

Team B — The Outliers · Software Engineering, Beihang University

A runnable foundation for an English context-aware AAC project: FastAPI, persistent
data, a replaceable sentence provider, and a small browser page for integration testing.

## What works

- JSON input with scene hint, symbols and intention.
- Optional JPEG/PNG/WebP upload through a separate multipart endpoint.
- Fixed water/coffee suggestions, selection, rejection and non-repeating regeneration.
- Explicit confirmation before browser speech; stop-speech control.
- SQLAlchemy models and Alembic migration for requests, suggestions and feedback.
- SQLite for zero-server local setup; PostgreSQL connection option via psycopg.
- Request validation, image decoding/size limits, provider-error responses, local CORS.
- Automated API/migration tests and GitHub Actions checks.

## What is deliberately unfinished

The only provider is **mock**: no LLM, no scene recognition, no paid API calls.
It supports one symbol (`water` or `coffee`), optionally matching text `I want water`
or `I want coffee`. Arbitrary or conflicting intentions return no suggestions.
There are six templates per item; one generation returns up to three. Two rounds
exhaust the templates; start a fresh request to reset the demonstration.

The included page is **not Cboard**. No Cboard source is copied or modified here.
The team must connect its Cboard fork to these endpoints. Authentication, user
ownership, persistent photo storage, semantic caching, production deployment and
mobile packaging are not implemented. Use this as a **local development prototype**,
not an anonymous public service. IDs are not authentication.

## Quick start

Use Python **3.12** and run commands from this folder (where `alembic.ini` lives).

```bash
python -m venv .venv
# Windows PowerShell: use .venv\Scripts\python.exe in place of python below.
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements-dev.txt
# Copy .env.example to .env (PowerShell: Copy-Item .env.example .env).
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Windows: follow the complete commands in START_HERE_RU.md so packages go inside
the virtual environment. macOS/Linux: `cp .env.example .env` before migration.

- Demo: http://127.0.0.1:8000
- Swagger: http://127.0.0.1:8000/docs
- OpenAPI: http://127.0.0.1:8000/openapi.json
- Health/readiness: `/health`, `/ready`

The demo's CSS and JS are local (no CDN). Swagger's default assets need internet;
if `/docs` is blocked by the network, the demo and OpenAPI JSON still work.
Speech uses browser/system English voices; voice availability varies by device.

## Development

```bash
python -m pytest -q
python -m ruff check .
python -m alembic check
```

After a model change, generate and inspect a migration, then apply it:

```bash
python -m alembic revision --autogenerate -m describe_your_change
python -m alembic upgrade head
```

Alembic checks are used in CI. Changing model classes alone does not update the DB.
Direct dependencies are pinned; `requirements-tested.txt` additionally records the
full dependency set used during verification. Keep both current when upgrading.

## Team ownership

| Member | Starting area |
| --- | --- |
| Veronika | API, database, migrations, backend tests; project coordination |
| Thibaut | Cboard fork, selected-symbol mapping, photo input, suggestions and speech UI |
| Jiahui | Real SentenceProvider implementation, prompts and evaluation |
| Fourth member | Containerization, hosting, configuration, CI/deployment and operations |

## Project map

| Path | Purpose |
| --- | --- |
| `app/main.py` | Application factory and API routes |
| `app/schemas.py` | Validated request/response contracts |
| `app/models.py`, `app/database.py` | Data model and connections |
| `app/providers/` | AI boundary and mock implementation |
| `app/images.py` | Photo validation and metadata removal |
| `app/static/` | Disposable integration demo, not the future Cboard UI |
| `migrations/` | Versioned schema changes |
| `tests/` | Behavior tests against a migrated temporary DB |
| `docs/API.md` | Integration examples and exact endpoints |
| `docs/TEAM_NEXT_STEPS.md` | First tasks, AI integration and deployment handoff |

## Data behavior

Successful generation attempts persist text, symbols, suggestions, provider name,
latency, photo-presence flag and retry linkage. Feedback stores one current decision
per request. No raw photos or image metadata are stored in the database. The upload
framework may temporarily spool a file while receiving it; it is closed after use.
Images are decoded, resized to at most 1024×1024 and re-encoded to JPEG before reaching
the provider. This removes metadata but does **not** blur faces or anonymize pixels.

The database is local and ignored by Git. There is no automatic retention/deletion
policy yet. Use synthetic inputs while developing. See deployment handoff for
necessary access control and upload-limit work before any public trial.

## Reference documentation

- [FastAPI forms and files](https://fastapi.tiangolo.com/tutorial/request-forms-and-files/)
- [SQLAlchemy engine configuration](https://docs.sqlalchemy.org/en/20/tutorial/engine.html)
- [Alembic tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [Cboard source](https://github.com/cboard-org/cboard)
- [GitHub Desktop upload guide](https://docs.github.com/en/desktop/adding-and-cloning-repositories/adding-an-existing-project-to-github-using-github-desktop)

This starter contains no third-party source code or symbol assets. Dependencies retain
their own licenses. The team has not selected a license for this new repository yet.

