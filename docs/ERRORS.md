# Backend error handling

This update builds on the API router and service refactoring in
`Backend_Step1_Refactor.zip`.

## Applying the update

1. Stop the development server with Control+C.
2. Extract this archive into a separate directory. Merge its `app` contents into
   the existing `app` directory, replacing matching files and adding `errors.py`.
   Keep the other project files.
3. Add `tests/test_errors.py` to the existing `tests` directory.
4. Run these commands from the project root:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check app tests
.venv/bin/python -m uvicorn app.main:app --reload
```

Validation: 37 tests pass (26 existing tests and 11 new tests), and Ruff passes.
This update requires no additional dependencies or database migrations.

## Implementation

`app/errors.py` defines `AppError(status_code, detail, error_code)`, its response
handler, and a handler for automatic request validation errors.
`register_error_handlers(app)` is called immediately after creating the FastAPI
application in `app/main.py`.

Example service error:

```python
from app.errors import AppError

raise AppError(404, "Previous request not found.", "REQUEST_NOT_FOUND")
```

The response retains its HTTP status and includes a stable error code:

```json
{
  "detail": "Previous request not found.",
  "error_code": "REQUEST_NOT_FOUND"
}
```

Automatic FastAPI request validation errors retain their existing list in
`detail` and include `error_code: "VALIDATION_ERROR"`. Invalid JSON in the
multipart `payload` field retains its string `detail` and uses `INVALID_PAYLOAD`.

## Error codes

| Code | HTTP status | Meaning |
|---|---|---|
| REQUEST_NOT_FOUND | 404 | The request or a previous request in its chain was not found. |
| INPUT_CHANGED | 409 | Inputs changed within a regeneration chain. |
| GENERATION_LIMIT_REACHED | 409 | The existing regeneration chain limit was exceeded. |
| SUGGESTION_MISMATCH | 422 | The suggestion does not belong to the specified request. |
| INVALID_PAYLOAD | 422 | The multipart payload field is invalid. |
| VALIDATION_ERROR | 422 | Automatic FastAPI request validation failed. |
| IMAGE_TOO_LARGE | 413 | The uploaded file exceeds the size limit. |
| IMAGE_DIMENSIONS_TOO_LARGE | 413 | The image exceeds 20 megapixels. |
| UNSUPPORTED_IMAGE_FORMAT | 415 | The image format is not JPEG, PNG, or WebP. |
| INVALID_IMAGE | 415 | The image cannot be decoded or exceeds decoding safety limits. |
| PROVIDER_UNAVAILABLE | 503 | The generation provider is temporarily unavailable. |
| PROVIDER_FAILED | 502 | The generation provider raised an unexpected exception. |
| INVALID_PROVIDER_OUTPUT | 502 | The provider returned invalid sentences. |
| MIGRATIONS_REQUIRED | 503 | The readiness check found an unexpected migration revision. |
| DATABASE_UNAVAILABLE | 503 | The readiness check could not read the database or migration table. |

## Scope

Standard routing errors, such as an unknown URL, unexpected server exceptions,
and response validation errors retain FastAPI's default handling.

Input limits, database operations, the provider implementation, and the frontend
retain their existing behavior. Centralizing limits is a subsequent task; the
file size error currently retains the original fixed `5 MiB` message.

Review the eight Python files included in this update before committing.
Suggested commit message: `Add consistent backend error codes and handlers`.
