# Database reference

The backend stores generation requests, sentence suggestions, and the user's
current feedback. These records link each suggested sentence to the inputs that
produced it and identify the sentence the user accepted.

The current implementation supports persistence, feedback updates, regeneration
chains, and exact retrieval of previously accepted sentences. The retrieval
endpoint is documented in [REUSE.md](REUSE.md).

## Implementation

| Location | Responsibility |
| --- | --- |
| `app/models.py` | SQLAlchemy table definitions. |
| `app/database.py` | Database engine and session factory. |
| `migrations/` | Alembic schema migrations. |
| `app/services/suggestions.py` | Generation records, suggestion storage, and regeneration checks. |
| `app/services/feedback.py` | Feedback validation and updates. |
| `app/services/reuse.py` | Retrieval of currently accepted sentences with matching inputs. |
| `app/api/reuse.py` | The `POST /api/suggestions/reuse` endpoint. |
| `app/reuse_schemas.py` | Retrieval input and output schemas. |

Local development uses SQLite by default. `DATABASE_URL` selects the database
connection. PostgreSQL integration requires a separate verification step.
Database structure changes are managed through Alembic migrations.

Identifiers are UUID strings. The application creates timestamps in UTC.

## Tables

### `generation_requests`

One row represents one completed generation operation, including an operation
that returns an empty suggestion list.

| Column | Purpose |
| --- | --- |
| `id` | Primary key identifying the generation request. |
| `created_at` | Time the application creates the request record. |
| `scene_hint` | Context supplied with the request, such as a café setting. |
| `intent_text` | The user's intended message in text form. |
| `selected_symbols` | Selected symbol labels stored as a JSON array. |
| `language` | Requested language. The current API accepts English (`en`). |
| `image_supplied` | Whether the request included an image. |
| `provider` | Name of the provider used for generation. |
| `latency_ms` | Measured generation processing time in milliseconds. |
| `parent_request_id` | Optional foreign key to a previous generation request. |

`scene_hint` describes context and does not replace `intent_text` or the selected
symbols. Symbol order and repeated symbols are preserved.

The API requires at least one selected symbol or a nonblank intention. Input
validation rules are documented in [API.md](API.md).

### `suggestions`

One row stores one sentence returned for a generation request.

| Column | Purpose |
| --- | --- |
| `id` | Primary key identifying the suggestion. |
| `request_id` | Foreign key to the request that produced this suggestion. |
| `text` | Suggested English sentence. |
| `position` | Zero-based position in the displayed suggestion list. |

The generation service validates provider output and returns at most three
suggestions. It removes duplicate sentences and sentences excluded by the
regeneration chain before saving the results. A request can therefore have zero
to three suggestions under the current application rules.

`suggestions.request_id` has an index for request-based lookups. The three-result
limit is enforced by the application rather than by a table constraint.

### `feedback`

One row stores the current decision for a generation request.

| Column | Purpose |
| --- | --- |
| `request_id` | Primary key and foreign key to the generation request. |
| `action` | Current decision: `accepted` or `rejected`. |
| `suggestion_id` | Optional foreign key to the selected suggestion. |
| `updated_at` | Time the application last updates the feedback. |

The current application rules are:

- `accepted` requires an existing suggestion belonging to this request.
- `rejected` requires `suggestion_id` to be absent or null.
- A later feedback update replaces the current decision.

The primary key on `request_id` enforces at most one feedback row per request.
Repeated identical feedback submissions do not create additional rows, although
the update timestamp can change.

There is no feedback event history. If a user changes a decision from `accepted`
to `rejected`, the row represents rejection and no longer identifies an accepted
suggestion.

## Relationships

| Relationship | Meaning |
| --- | --- |
| `suggestions.request_id` references `generation_requests.id` | A request has zero or more suggestion rows; each suggestion belongs to one request. |
| `feedback.request_id` references `generation_requests.id` | A request has zero or one current feedback row. |
| `feedback.suggestion_id` references `suggestions.id` | Accepted feedback identifies the selected suggestion. |
| `generation_requests.parent_request_id` references `generation_requests.id` | A regeneration request can refer to its previous request. |

The feedback service checks that the selected suggestion belongs to the same
request. Separate foreign keys alone do not enforce that ownership condition.

## Regeneration chains

The first request in a chain has `parent_request_id = null`. A regeneration
request references the immediately preceding request.

Before generating again, the service traverses the parent chain, checks the
inputs, and collects all previously suggested sentences for exclusion.

The current rules allow at most 20 ancestors. A change to the scene, intention,
or selected symbols requires a new chain without a parent ID. The frontend must
also start a new chain when the photo changes, because the backend does not
compare photo identity.

## Image storage

The image handler validates and prepares uploaded images before passing JPEG
bytes to the provider. The database stores only the `image_supplied` flag.

These tables do not store original photos, processed image bytes, or image file
paths. An image must be uploaded again for a later request that needs it.
`image_supplied` does not establish that a provider analyzed the image content.

## Tracing an accepted suggestion

To identify an accepted sentence and its original inputs:

1. Find a feedback row whose current `action` is `accepted`.
2. Retrieve the suggestion referenced by `feedback.suggestion_id`.
3. Check that `suggestions.request_id` equals `feedback.request_id`.
4. Retrieve the corresponding generation request to obtain its scene, intention,
   selected symbols, and language.

Acceptance applies only to the selected suggestion, not to every suggestion
produced for that request. A suggestion without feedback is not considered
accepted.

## Retrieval for reuse

`POST /api/suggestions/reuse` returns historical candidates without generating
text or writing records. See [REUSE.md](REUSE.md) for request and response examples.

### Eligibility

Only currently accepted suggestions are eligible. Suggestions with rejected or
missing feedback are excluded.

The search supports text and symbol inputs without a photo. The client must not
use it when the current interaction depends on a photo. Source requests with `image_supplied = true` are excluded because their original visual
context cannot be compared.

### Matching rules

| Input | Rule |
| --- | --- |
| `language` | Exact match. |
| `scene_hint` | Exact match after trimming leading and trailing whitespace on both values. |
| `intent_text` | Exact match after trimming leading and trailing whitespace on both values. |
| `selected_symbols` | Exact array match, preserving order and repetitions. |

Text matching is case-sensitive in this first version. Matching does not sort
symbols, remove repeated symbols, or infer semantic similarity. Finding the same
symbol in two requests is insufficient when their other inputs differ.

### Ordering and result limits

1. Order candidates by `feedback.updated_at`, newest first, then by suggestion ID
   ascending to resolve ties.
2. Trim sentence texts, skip blank or overlong legacy sentences, and remove
   duplicate sentence texts. Valid sentences contain at most 300 characters.
3. Return up to three unique sentences, continuing through candidates as needed.
4. Return an empty list when there are no matches.

The lookup must not modify existing records or call the generation provider.
The initial design uses the existing three tables; additional indexes or schema
changes should follow demonstrated query requirements.

### Source references and new interactions

Each retrieval result includes its sentence text, `source_request_id`, and
`source_suggestion_id`. These IDs identify historical records, not a newly
created interaction.

Selecting a reused sentence must not overwrite feedback for its source request.
Recording a new reuse interaction requires a separate agreed flow with new
interaction records. Semantic retrieval and RAG integration also require a
separate contract with the AI component.

### User scope

The current schema has no user ownership field. Initial retrieval should be
tested locally with synthetic data. User-specific retrieval requires an ownership
model and authorization rules before working with personal histories.
