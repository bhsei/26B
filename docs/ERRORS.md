# Backend error handling

This document describes application errors, request validation errors, and the
error handling conventions used by the backend. For endpoint definitions and
request examples, see [API.md](API.md).

## Response format

An application error returns an HTTP status and a JSON body with two fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `detail` | string | A readable, client-safe explanation of the failure. |
| `error_code` | string | A stable identifier for application-specific handling. |

Example response with HTTP status `404`:

```json
{
  "detail": "Previous request not found.",
  "error_code": "REQUEST_NOT_FOUND"
}
```

Several application errors can share an HTTP status. Clients should use
`error_code` to distinguish them rather than matching the text of `detail`.

## Request validation errors

Automatic FastAPI request validation errors return HTTP `422` with
`error_code: "VALIDATION_ERROR"`. Their `detail` field retains FastAPI's list of
validation errors. Each entry describes the invalid field and the reason.

Invalid JSON or invalid field values in the multipart `payload` field follow a
separate path: they return HTTP `422` with `error_code: "INVALID_PAYLOAD"` and a
string `detail`.

## Implementation

`app/errors.py` defines:

- `AppError(status_code, detail, error_code)` for expected application failures.
- `app_error_handler()` to convert `AppError` into a JSON response.
- `validation_error_handler()` to add `VALIDATION_ERROR` to FastAPI's existing
  request validation response.
- `register_error_handlers(app)` to register both handlers.

`app/main.py` calls `register_error_handlers(app)` after creating the FastAPI
application. Routes and services raise `AppError` when a known failure occurs.

## Adding an application error

Import `AppError` and provide the HTTP status, a client-safe message, and a code:

```python
from app.errors import AppError

raise AppError(
    404,
    "Previous request not found.",
    "REQUEST_NOT_FOUND",
)
```

When adding an error:

1. Reuse an existing code when it describes the same condition. Otherwise, choose
   a descriptive uppercase code with underscores.
2. Keep the message suitable for display to the client. Do not include API keys,
   credentials, or internal exception details.
3. Add the code to the table below and update the API contract when necessary.
4. Test the HTTP status, the error code, and any required message behavior.

The generation service converts provider failures into safe application errors
instead of returning the original provider exception text.

## Error codes

| Code | HTTP status | Meaning |
| --- | --- | --- |
| `REQUEST_NOT_FOUND` | 404 | The request or a previous request in its chain was not found. |
| `INPUT_CHANGED` | 409 | The scene, intention, or selected symbols changed within a regeneration chain. |
| `GENERATION_LIMIT_REACHED` | 409 | The regeneration chain exceeds the allowed number of ancestors. |
| `SUGGESTION_MISMATCH` | 422 | The suggestion does not exist or does not belong to the specified request. |
| `INVALID_PAYLOAD` | 422 | The multipart payload is invalid JSON or does not satisfy `SuggestionInput`. |
| `VALIDATION_ERROR` | 422 | Automatic FastAPI request validation failed. |
| `IMAGE_TOO_LARGE` | 413 | The uploaded file exceeds the configured byte limit. |
| `IMAGE_DIMENSIONS_TOO_LARGE` | 413 | The image exceeds 20 megapixels. |
| `UNSUPPORTED_IMAGE_FORMAT` | 415 | The decoded image format is not JPEG, PNG, or WebP. |
| `INVALID_IMAGE` | 415 | The image cannot be decoded or triggers an image decoding safety check. |
| `PROVIDER_UNAVAILABLE` | 503 | The generation provider is temporarily unavailable. |
| `PROVIDER_FAILED` | 502 | The generation provider raised an unexpected exception. |
| `INVALID_PROVIDER_OUTPUT` | 502 | The provider returned an invalid sentence result. |
| `MIGRATIONS_REQUIRED` | 503 | The readiness check found an unexpected migration revision. |
| `DATABASE_UNAVAILABLE` | 503 | The readiness check could not read the database or migration table. |

## Client behavior

- Use `error_code` for application-specific handling.
- Handle both string and list values in `detail`.
- Fall back to a generic message if `error_code` is missing or the response is
  not JSON.
- Display errors visually. Do not send error messages to text-to-speech.

## Scope

These handlers cover expected failures raised as `AppError` and automatic request
validation failures. Standard routing errors, unexpected server exceptions, and
response validation errors retain FastAPI's default handling and may not include
`error_code`.

`DATABASE_UNAVAILABLE` describes a readiness check failure. It is not a global
handler for all database exceptions.
