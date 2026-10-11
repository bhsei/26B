# API contract v0.1

Base URL for local development: `http://127.0.0.1:8000`.
OpenAPI: `/openapi.json`. Swagger: `/docs`. All sentences are English.
This prototype has no authentication. Run locally with synthetic inputs.

## Generate with text and symbols

`POST /api/suggestions` · `Content-Type: application/json` · success `201`

```json
{
  "scene_hint": "A café",
  "selected_symbols": ["water"],
  "intent_text": "",
  "language": "en"
}
```

At least one symbol or nonblank intention is required. Maximum 20 symbols, 80
characters per symbol, 500 for scene and intention. Unknown fields are rejected.
Scene is context, not user intention. The mock ignores it; real AI should use it.

Response shape (IDs below are illustrative; always use returned IDs):

```json
{
  "request_id": "11111111-1111-4111-8111-111111111111",
  "provider": "mock",
  "image_supplied": false,
  "image_analyzed": false,
  "suggestions": [
    {"id": "22222222-2222-4222-8222-222222222222", "text": "Could I have a glass of water, please?"}
  ],
  "notice": "Mock templates only. Photos are not analyzed."
}
```

0–3 suggestions may be returned. An empty list is a valid result, not a network
failure. The frontend should show the notice and allow editing input.

## Generate with a photo

`POST /api/suggestions/image` · `multipart/form-data` · success `201`

| Field | Value |
| --- | --- |
| `payload` | JSON string with exactly the fields used above |
| `image` | File, JPEG/PNG/WebP, at most 5 MiB and 20 MP |

```javascript
const form = new FormData();
form.append('payload', JSON.stringify({
  scene_hint: 'A café', selected_symbols: ['water'], intent_text: '', language: 'en'
}));
form.append('image', selectedFile);
const response = await fetch('http://127.0.0.1:8000/api/suggestions/image', {
  method: 'POST', body: form
});
const result = await response.json();
if (!response.ok) throw new Error(JSON.stringify(result.detail));
```

Do not manually set `Content-Type` for FormData; the browser supplies its boundary.
Sending a photo sets `image_supplied=true`, not `image_analyzed=true`. Mock mode
does not inspect content. The backend passes sanitized JPEG bytes to the provider.

## Feedback and regeneration

`PUT /api/requests/{request_id}/feedback` · JSON · success `200`

Accepted: `{"action":"accepted","suggestion_id":"<returned suggestion UUID>"}`

Rejected: `{"action":"rejected"}`

Accepted requires a suggestion belonging to this request. Rejected must not carry
a suggestion ID. There is one current feedback record per generation; repeated
identical PUTs do not create duplicate rows. A later PUT replaces the decision.

To regenerate, save rejection, then call a generation endpoint with the original
inputs plus `parent_request_id` set to the previous returned request ID. Upload the
photo again if applicable, because the backend does not retain it. Sentences from
the entire parent chain are excluded. Maximum 20 ancestors. Changed scene/text/
symbols require a fresh request without a parent. Photo identity is not compared;
the client must also start a fresh chain when changing photos.

The included demo clears its old results whenever inputs change, so stale choices
cannot accidentally be submitted for a new intention.

## Responses to handle

| Status | Meaning |
| --- | --- |
| 404 | Unknown request or parent |
| 409 | Changed inputs or regeneration depth limit |
| 413 | Photo too large |
| 415 | Invalid or unsupported photo |
| 422 | Invalid input or unrelated suggestion ID |
| 502 | Provider failed or returned invalid content |
| 503 | Provider unavailable, or readiness/database failure |

The response contains `detail` (string or FastAPI validation list). Do not speak
errors. Provider exceptions and credentials must not appear in API responses.

## Connecting Cboard

Map selected Cboard tiles to their English labels for `selected_symbols` in this
first integration. Keep Cboard's IDs separately if needed; this API does not fetch
boards or recreate Cboard's accounts. Call the API from a configurable base URL.
Display text with React's normal escaped rendering. Show options without speaking;
only pass the selected text to speech after an explicit user action.

`CORS_ORIGINS` must contain the frontend's exact origin, including port. The default
allows `localhost:3000` and `127.0.0.1:3000`. It is not an authentication mechanism.

