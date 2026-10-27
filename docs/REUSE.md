# Retrieval of accepted suggestions

## Endpoint

`POST /api/suggestions/reuse`

- Content type: `application/json`
- Success status: `200`, including when no match exists.
- Operation: read existing records without generating text or changing feedback.

```json
{
  "scene_hint": "A café",
  "selected_symbols": ["water"],
  "intent_text": "",
  "language": "en"
}
```

At least one selected symbol or a nonblank intention is required. Text and symbol
limits match the existing generation input: 500 characters for scene and intention,
20 symbols, and 80 characters per symbol. English (`en`) is the only supported
language. The fields default to empty strings, an empty symbol list, and `en`.

Unknown fields are rejected, including `parent_request_id`, `image`, and
`image_supplied`. This endpoint accepts text and symbol inputs only. Do not use
it for a current interaction whose meaning depends on a photo; the JSON lookup
cannot know whether the UI also holds an image.

## Response

Example result. Source IDs are illustrative.

```json
{
  "suggestions": [
    {
      "text": "Could I have a glass of water, please?",
      "source_request_id": "11111111-1111-4111-8111-111111111111",
      "source_suggestion_id": "22222222-2222-4222-8222-222222222222"
    }
  ]
}
```

No matches:

```json
{
  "suggestions": []
}
```

Invalid input returns HTTP `422` through the existing validation handler, with
`error_code: "VALIDATION_ERROR"` and a list in `detail`. No new application error
codes are introduced. Unexpected database errors retain existing server handling.

## Matching and ranking

The service joins the current feedback, request, and selected suggestion:

1. Require `feedback.action = accepted`.
2. Match both the selected suggestion ID and its request ID. A feedback row that
   points to another request's suggestion cannot qualify.
3. Exclude source requests with `image_supplied = true`.
4. Require matching language.
5. Compare scene and intention case-sensitively after Python whitespace trimming
   on both the incoming and stored text.
6. Compare the symbol arrays exactly, preserving order and repetitions. Incoming
   symbol labels use the same whitespace validation as generation input.
7. Rank by `feedback.updated_at` descending, then suggestion ID ascending.
8. Trim returned sentence texts, omit blank or overlong legacy sentences, and
   keep the first occurrence of each exact sentence text.
9. Return at most three unique matches.

Only the currently selected sentence qualifies. Other sentences from an accepted
request do not qualify automatically. Changing feedback changes subsequent lookup
results; there is no cached result or feedback event history.

## Implementation

| File | Responsibility |
| --- | --- |
| `app/reuse_schemas.py` | Lookup input and output schemas. |
| `app/services/reuse.py` | Read-only lookup and matching rules. |
| `app/api/reuse.py` | Router factory and HTTP endpoint. |
| `tests/test_reuse.py` | Retrieval, validation, and integration tests. |

The service reads candidate rows in batches of 100 and stops when three unique
matches are found or the result is exhausted. Matching happens before the result
limit, so duplicates and unrelated rows cannot hide later valid candidates.

Text and array comparisons use Python after SQL filtering. This avoids differences
in database collation, JSON comparison, and Unicode trimming. A lookup can still
scan many accepted candidates. This initial implementation targets the local
prototype; it does not claim indexed search performance or verified PostgreSQL
compatibility. No schema changes or new dependencies are required.

## Integration boundaries

The endpoint returns historical candidates and their source IDs. It does not
create a new generation request, record a reuse event, select a sentence, or start
speech. Do not send feedback for a new interaction using the returned source
request ID: that would change the historical decision. The recording flow for a
new reuse interaction must be implemented separately with new interaction records.

The existing generation endpoints continue to call their configured provider.
This lookup does not automatically run before generation and does not fall back
to a provider when no match exists. The frontend or a later integration service
must choose when to use lookup versus generation.

The current schema has no user ownership fields. Test this prototype locally with
synthetic records. Personal history retrieval requires ownership and authorization
rules. Semantic search, embeddings, and RAG are outside this implementation.

## Manual check

With the development server running, open `http://127.0.0.1:8000/docs`:

1. Call `POST /api/suggestions` using the sample text input above.
2. Copy the returned request ID and one suggestion ID.
3. Accept that suggestion through `PUT /api/requests/{request_id}/feedback`.
4. Call `POST /api/suggestions/reuse` with the same input.
5. Confirm that the accepted sentence and its source IDs are returned. Older
   matching accepted records can also appear, up to the three-result limit.
6. Change the original feedback to `rejected` and run the lookup again. That
   source must disappear. An identical sentence accepted in another request can
   still appear with that other source's IDs.

In mock mode, the `water` symbol supports this check. A different provider may
return different sentences, but acceptance and retrieval use the same API flow.
