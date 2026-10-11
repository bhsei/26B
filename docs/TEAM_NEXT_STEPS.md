# Team next steps

## First shared milestone

One local café scenario: Cboard sends the selected water tile to the backend;
the user sees suggestions, rejects/regenerates, selects one and explicitly speaks.
Feedback persists after restart. Keep this working while replacing the mock.

| Owner | First pull request | Done when |
| --- | --- | --- |
| Veronika | Review API/models, run tests, agree contracts | Team can run backend from README |
| Thibaut | Connect Cboard fork to generation/feedback | End-to-end café scenario works in Cboard |
| Jiahui | Add real provider behind SentenceProvider | Photo + intention generate evaluated English options |
| Fourth member | Reproducible infrastructure and staging plan | Backend/DB can start with documented configuration |

## AI handoff

Implement `SentenceProvider` from `app/providers/base.py` in a new module.
Input: validated `SuggestionInput`, sanitized JPEG bytes (or None), and previously
shown sentences to exclude. Output: `GeneratedSentences` with at most three
nonblank sentences, at most 300 characters each. Set `image_analyzed` truthfully.

Inject your provider via `create_app(settings, provider)` during tests. For normal
startup, extend the allowed provider setting and the factory in `app/main.py`.
Setting AI_PROVIDER to an unsupported value currently fails validation, rather than
silently pretending to use real AI.

Keep credentials in environment variables. Use explicit network timeouts and
translate upstream failures into `ProviderUnavailable`. Do not log photos, complete
intentions or secrets. Treat scene text as data, not instructions. Keep the person's
intention authoritative; never invent intent solely from an image. Evaluation must
include negation, ambiguous images, incorrect scene hints and refusal/regeneration.

## PostgreSQL handoff

SQLite is the tested zero-server default. To try PostgreSQL, create an empty
database and user using your preferred local tooling. Install `requirements.txt`,
then edit `.env`:

```dotenv
DATABASE_URL=postgresql+psycopg://outliers:YOUR_PASSWORD@localhost:5432/outliers
```

URL-encode special characters in the password. Run `python -m alembic upgrade head`,
then `python -m alembic check` and start the app. Migrations create the tables, not
the database/user. Changing the URL does not transfer existing SQLite records.
Use a fresh DB for the first trial; any later data migration is a separate task.

This delivery was exercised with SQLite. PostgreSQL DDL is designed to be portable;
a live PostgreSQL integration run remains a team task before selecting it for staging.

## Deployment handoff for the fourth member

The repository provides the entrypoint, environment example, migration and health
routes. It deliberately does not deploy anywhere or create cloud resources.

- Python 3.12; install `requirements.txt` (no test tools required in runtime).
- Build container and set DATABASE_URL and exact CORS_ORIGINS via environment.
- Run `python -m alembic upgrade head` once per release before app workers start.
- Runtime command: `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`.
  Use this bind inside the managed container; local instructions bind loopback.
- `/health` checks process liveness; `/ready` checks DB/schema readiness.
- Select persistent DB storage, backups, HTTPS and secrets handling.
- Add authentication and ownership before access by untrusted users. Current
  request UUIDs do not authorize access. CORS does not stop direct API clients.
- Add reverse-proxy total request limits, timeouts, rate limits and spending limits
  before connecting paid AI. The current image check runs after multipart parsing;
  it is not an early limit on all uploaded HTTP bytes.
- Agree text retention/deletion and consent before real-user trials. No raw-photo
  archive exists; logs should not create one accidentally.
- Browser speech may need device-specific handling and English voice testing.

## Suggested small issues

1. Thibaut: run Cboard locally and locate symbol selection + speech code.
2. Veronika + Thibaut: send one JSON request from Cboard and render results.
3. Jiahui: build a provider test with a synthetic café photo and explicit water intent.
4. Veronika: add provider integration tests for timeout and malformed responses.
5. Fourth member: run the initial migration on an isolated PostgreSQL instance.
6. All: define the first usability scenario and a small evaluation set.

## Verification record

See `VERIFICATION.md` for checks actually run on this delivery. Do not interpret
the starter's interface as evidence of completed Cboard integration or AI quality.
