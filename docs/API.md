# API contract v0.1

Base URL for local development: `http://127.0.0.1:8000`.
OpenAPI schema: `/openapi.json`. Swagger UI: `/docs`.
All generated sentences are English.

This prototype has no authentication. Run it locally with synthetic inputs.

## Generate with text and symbols

`POST /api/suggestions`

- Content type: `application/json`
- Success status: `201`

```json
{
  "scene_hint": "A café",
  "selected_symbols": ["water"],
  "intent_text": "",
  "language": "en"
}
```

### Input rules

| Field | Type | Rules |
| --- | --- | --- |
| `scene_hint` | string | Optional context, at most 500 characters. Defaults to an empty string. |
| `selected_symbols` | array of strings | At most 20 symbols, each with 1 to 80 characters after trimming. Defaults to an empty array. |
| `intent_text` | string | At most 500 characters. Defaults to an empty string. |
| `language` | string | Only `en` is accepted. Defaults to `en`. |
| `parent_request_id` | UUID string or null | Optional previous request ID for regeneration. |

At least one selected symbol or a nonblank intention is required. Leading and
trailing whitespace is trimmed from text inputs. Unknown fields are rejected.
The scene provides context; it does not replace the user's intention. The mock
provider ignores the scene, while a real provider can use it to interpret context.
The order and repetition of selected symbols are preserved.

### Response

Example response from the mock provider. IDs are illustrative; use the IDs
returned by the server.

```json
{
  "request_id": "11111111-1111-4111-8111-111111111111",
  "provider": "mock",
  "image_supplied": false,
  "image_analyzed": false,
  "suggestions": [
    {
      "id": "22222222-2222-4222-8222-222222222222",
      "text": "Could I have a glass of water, please?"
    }
  ],
  "notice": "Mock templates only. Photos are not analyzed."
}
```

The response contains zero to three suggestions. An empty list is a valid result.
The frontend should display any notice and allow the user to edit the input or
start a new request.

## Generate with a photo

`POST /api/suggestions/image`

- Content type: `multipart/form-data`
- Success status: `201`

| Field | Value |
| --- | --- |
| `payload` | A JSON string matching the input schema above, at most 5,000 characters. |
| `image` | A JPEG, PNG, or WebP file within the configured byte limit and at most 20 megapixels. The default byte limit is 5 MiB. |

```javascript
const form = new FormData();
form.append("payload", JSON.stringify({
  scene_hint: "A café",
  selected_symbols: ["water"],
  intent_text: "",
  language: "en"
}));
form.append("image", selectedFile);

const response = await fetch(
  "http://127.0.0.1:8000/api/suggestions/image",
  { method: "POST", body: form }
);
const result = await response.json();

if (!response.ok) {
  const message = typeof result.detail === "string"
    ? result.detail
    : "Please check the submitted data.";
  throw new Error(`${result.error_code ?? "REQUEST_FAILED"}: ${message}`);
}
```

In this example, `selectedFile` is the file selected in the frontend. Production
UI code should also handle network failures and responses that are not JSON.

Do not manually set `Content-Type` for `FormData`; the browser supplies the
multipart boundary. The backend validates the image and passes sanitized JPEG
bytes to the provider without storing the original photo.

A supplied photo sets `image_supplied` to `true`. This does not guarantee that
`image_analyzed` is `true`. The mock provider does not analyze image content.

## Feedback

`PUT /api/requests/{request_id}/feedback`

- Content type: `application/json`
- Success status: `200`

To accept a suggestion, use the suggestion ID returned for this request:

```json
{
  "action": "accepted",
  "suggestion_id": "22222222-2222-4222-8222-222222222222"
}
```

To reject the suggestions:

```json
{
  "action": "rejected"
}
```

`accepted` requires a suggestion that belongs to the specified request.
`rejected` requires no selected suggestion; omit `suggestion_id` or set it to
`null`. Unknown fields and unsupported actions are rejected.

There is one current feedback record per generation request. Repeating the same
PUT does not create duplicate records. A later PUT replaces the current decision.

Example response to an accepted suggestion:

```json
{
  "request_id": "11111111-1111-4111-8111-111111111111",
  "action": "accepted",
  "suggestion_id": "22222222-2222-4222-8222-222222222222"
}
```

For rejection, the response contains `action: "rejected"` and
`suggestion_id: null`.

## Regeneration

1. Save rejection for the current request.
2. Call a generation endpoint with the original inputs and `parent_request_id`
   set to the previous request ID.
3. Upload the photo again when applicable; the backend does not retain it.

Example text request:

```json
{
  "scene_hint": "A café",
  "selected_symbols": ["water"],
  "intent_text": "",
  "language": "en",
  "parent_request_id": "11111111-1111-4111-8111-111111111111"
}
```

The backend excludes sentences from the entire parent chain. A request can have
at most 20 ancestors. Changing the scene, intention, or selected symbols requires
a new chain without `parent_request_id`.

The backend does not compare photo identity. The frontend must also start a new
chain when the photo changes. Clear stale suggestions when any input changes.

## Health and readiness

| Endpoint | Success status | Purpose |
| --- | --- | --- |
| `GET /health` | 200 | Returns application status, provider name, and API version. |
| `GET /ready` | 200 | Checks database access and the expected migration revision. |

Readiness failures return HTTP `503`. A successful health response does not
guarantee database readiness or availability of an external model service.

## Error responses

### Application errors

Expected application failures return an HTTP status and a JSON body:

| Field | Type | Meaning |
| --- | --- | --- |
| `detail` | string | A readable, client-safe explanation. |
| `error_code` | string | A stable application error code. |

Example: an unknown parent request returns HTTP `404`:

```json
{
  "detail": "Previous request not found.",
  "error_code": "REQUEST_NOT_FOUND"
}
```

### Request validation errors

Automatic FastAPI request validation failures return HTTP `422` with
`error_code: "VALIDATION_ERROR"`. In these responses, `detail` is a list of
validation errors rather than a string.

Invalid JSON or invalid field values in the multipart `payload` field return
HTTP `422` with `error_code: "INVALID_PAYLOAD"` and a string `detail`.

### Status summary

| Status | Meaning | Error codes |
| --- | --- | --- |
| 404 | Unknown request or parent. | `REQUEST_NOT_FOUND` |
| 409 | Changed inputs or regeneration chain limit. | `INPUT_CHANGED`, `GENERATION_LIMIT_REACHED` |
| 413 | Photo exceeds the byte or pixel limit. | `IMAGE_TOO_LARGE`, `IMAGE_DIMENSIONS_TOO_LARGE` |
| 415 | Invalid or unsupported photo. | `INVALID_IMAGE`, `UNSUPPORTED_IMAGE_FORMAT` |
| 422 | Invalid input or a suggestion that does not belong to the request. | `VALIDATION_ERROR`, `INVALID_PAYLOAD`, `SUGGESTION_MISMATCH` |
| 502 | Provider failure or invalid provider output. | `PROVIDER_FAILED`, `INVALID_PROVIDER_OUTPUT` |
| 503 | Provider unavailable or readiness failure. | `PROVIDER_UNAVAILABLE`, `MIGRATIONS_REQUIRED`, `DATABASE_UNAVAILABLE` |

Use `error_code` for application-specific handling instead of matching message
text. Handle both string and list values in `detail`. Fall back to a generic
message when `error_code` is missing or the response is not JSON. Standard
routing errors and unexpected server failures may use FastAPI's default format.

Display errors visually and do not send them to text-to-speech. Provider exception
details and credentials must not appear in API responses. See
[ERRORS.md](ERRORS.md) for implementation guidance and the complete code reference.

## Connecting the frontend

Map selected UI symbols to their English labels in `selected_symbols`. Keep any
frontend-specific symbol IDs separately if needed. Use a configurable API base
URL for local and deployed environments.

Display generated text with React's normal escaped rendering. Show suggestions
without speaking them automatically. Start speech only after an explicit user
confirmation. The backend returns text; speech playback happens in the browser.

`CORS_ORIGINS` must contain the frontend's exact origin, including scheme and
port. The default allowed origins are `http://localhost:3000` and
`http://127.0.0.1:3000`. CORS configuration does not provide authentication.
