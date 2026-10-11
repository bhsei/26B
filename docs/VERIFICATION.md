# Verification of the starter

Verified in a Linux environment with Python 3.12 and the dependency set recorded
in `requirements-tested.txt`.

## Passed

- 26 pytest cases: input validation, successful generation, persistence across app
  instances, feedback updates, cross-request selection rejection, retry exclusion,
  unsupported/negative mock intent, image upload/size/format, provider failures,
  CORS, readiness and migration downgrade/upgrade.
- Ruff code checks.
- Alembic schema comparison against the applied SQLite migration.
- JavaScript syntax check using `node --check app/static/app.js`.
- HTTP/static-page delivery through FastAPI TestClient.

The installed Starlette version emits an httpx TestClient deprecation warning;
all tests pass. It is a future test-tool migration item, not a runtime failure.

## Not verified here

- A live PostgreSQL server. The URL/driver and portable migration are included;
  run an integration check before staging.
- Real AI inference or Cboard integration; these are intentionally not implemented.
- Windows execution and actual speech audio. Instructions use standard Python 3.12
  commands; test on your laptop and check its installed English voice.
- Rendered browser layout and click-through behavior. The attempted Playwright
  browser download failed in this environment. The page is included for your first
  local trial; this report does not claim a completed browser test.

## Manual acceptance check

1. Run the documented setup; `/ready` returns ready.
2. Generate Water suggestions, select one and explicitly confirm speech.
3. Reject and regenerate: the next three phrases differ from the first set.
4. Reject again: no templates remain; start a fresh request to reset.
5. Change an input: previous choices are cleared.
6. Upload a valid image: `image_supplied=true`, `image_analyzed=false` in mock mode.
7. Restart backend: existing database records remain.

Use synthetic test inputs; this is a local prototype without account ownership.
