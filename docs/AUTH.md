# User accounts and authenticated ownership

Implementation package based on main `ce3627b` (23 November 2026).
This is a proposed implementation of SRS REQ-SEC-005 and SAD v0.3 decision D-06.
The team must review the decision and deployment configuration before publishing.

## Scope

Accounts are provisioned by the developer CLI. There is one user type. Email
verification, self-service signup and password-recovery emails are not included.
The existing login page now checks credentials. The application uses revocable
server-side sessions, stored in the same database as requests. No AI API is called
by authentication or its tests; AI_PROVIDER remains mock.

## Data model and migration

Migration `0002` creates:

- `users`: UUID id, unique normalized email, Argon2id password_hash, is_active,
  created_at.
- `auth_sessions`: SHA-256 token_hash primary key, user_id foreign key, csrf_token,
  created_at, last_seen_at, expires_at. Raw session tokens are never stored.
- `generation_requests.user_id`: indexed nullable FK to users. This is nullable
  only to preserve pre-authentication history. Every new API generation gets the
  authenticated user ID, never a client-supplied user ID.

Suggestions and feedback inherit their owner through request_id. No extra
user_id column is needed on these tables. Existing requests, suggestions and
feedback remain unchanged. Legacy requests retain NULL user_id and are excluded
from authenticated reuse, feedback changes and regeneration. The migration does
not assign old history to the first person signing in.

Do not edit migration 0001 or delete the old database. Back it up, then run
`python -m alembic upgrade head`. SQLite migration 0002 adds the nullable column
in place, so it does not rebuild the existing self-referencing request table.
Its downgrade uses native DROP COLUMN and requires SQLite >= 3.35. Python 3.12
on the tested platforms includes a sufficiently recent SQLite.

`/ready` now compares the database's applied Alembic heads to the heads shipped
with the application, rather than the literal 0001. It also checks the five ORM
tables. A missing/outdated revision returns 503 MIGRATIONS_REQUIRED; database
errors return 503 DATABASE_UNAVAILABLE. /health and /ready remain public.

## API contract

| Method and path | Input | Response |
| --- | --- | --- |
| POST /api/auth/login | JSON email, password; X-Requested-With: OutliersAAC | 200 with user {id,email} and csrf_token; sets outliers_session cookie |
| GET /api/auth/me | Session cookie | 200 with user and csrf_token, or 401 |
| POST /api/auth/logout | Session cookie and X-CSRF-Token | 204; revokes session and deletes cookie |

Cookie: HttpOnly, SameSite=Lax, Path=/, Max-Age matching absolute expiry.
AUTH_COOKIE_SECURE defaults to false for local HTTP development. Set it to true
for HTTPS deployment. Use a host-only cookie (no Domain attribute).

Login requires a custom header and rejects untrusted Origin/Fetch Metadata.
All protected POST/PUT routes require X-CSRF-Token from login or /me, checked
against the server session. Origin checks supplement this session-bound token.
CORS uses the explicit CORS_ORIGINS allow-list with credentials, never a wildcard.
Changing this list changes which browser origins are trusted with credentials.
The existing same-origin pages require no CORS change.

All /api responses and the /app page use Cache-Control: no-store.
/ redirects are not authentication: data endpoints enforce authentication
independently. An anonymous /app request redirects to /; static assets and the
public symbol lexicon remain available without sign-in.

### Existing routes

- POST /api/suggestions and /image require login + CSRF and assign the owner.
- Regeneration verifies ownership of every ancestor before provider invocation.
- PUT /api/requests/{id}/feedback verifies request ownership, then validates the
  suggestion belongs to that request; retains the atomic SQLite/PostgreSQL upsert.
- POST /api/suggestions/reuse filters user_id in SQL before ranking and limiting.
- A foreign or unowned request returns the existing 404 REQUEST_NOT_FOUND, just
  like an unknown ID. Its owner and content are not disclosed.
- user_id in the JSON body remains forbidden. Service functions require an
  explicit keyword-only user_id, supplied by server authentication.
- Authentication closes its SQLAlchemy session before a generation provider
  runs. It does not undo the earlier database-connection-release fix.

### Errors

| HTTP | error_code | Meaning |
| --- | --- | --- |
| 401 | INVALID_CREDENTIALS | Same message for wrong password, unknown or disabled account |
| 401 | AUTHENTICATION_REQUIRED | Missing, malformed, unknown or revoked session |
| 401 | SESSION_EXPIRED | Absolute/idle timeout or disabled account on an existing session |
| 403 | CSRF_FAILED | Missing/wrong CSRF header or untrusted origin |
| 429 | LOGIN_RATE_LIMITED | Per-process IP attempt limit; Retry-After header included |

Validation errors retain the existing detail list, with submitted input removed
so invalid passwords are not echoed in responses. Responses never include a
password hash, raw session token or internal exception detail.

## Account commands

Run from the repository root in its virtual environment. Passwords are prompted
without echo and are never CLI arguments. New passwords require 12–1024 characters.

```bash
python -m app.manage_users create veronika@example.test
python -m app.manage_users reset-password veronika@example.test
python -m app.manage_users disable veronika@example.test
```

Reset and disable revoke all existing sessions for that account. Resetting a
password does not re-enable a disabled account. The CLI does not create shared or
hard-coded accounts automatically. All account-changing commands require database
administrative access through the configured DATABASE_URL.

## Settings

| Setting | Default | Purpose |
| --- | --- | --- |
| AUTH_COOKIE_SECURE | false | true with HTTPS |
| AUTH_SESSION_TTL_SECONDS | 28800 | Absolute server-side lifetime, eight hours |
| AUTH_SESSION_IDLE_SECONDS | 3600 | Idle server-side lifetime, one hour |
| AUTH_LOGIN_MAX_ATTEMPTS | 10 | Attempts per observed client IP and process |
| AUTH_LOGIN_WINDOW_SECONDS | 60 | Login attempt window |

The in-process limiter has bounded memory and does not trust X-Forwarded-For
itself. Abid must configure HTTPS, trusted proxy handling and shared/proxy request
limits for a public deployment (REQ-SEC-006). Authentication alone does not close
consent, retention or licensing requirements. Continue using synthetic data until
the team's real-user conditions are met.

## Frontend integration

The login form submits credentials to /api/auth/login and displays server errors.
app.js retrieves /me once per page load and adds the CSRF header to API writes.
A session change in another tab fails safely; reloading retrieves the new CSRF
state. It does not automatically retry old requests under a different account.
Sign out clears in-memory suggestions/pending feedback and cancels speech.

Thibaut's speak-first handler and retry are preserved. Saving and retrying use the
original request/suggestion IDs and do not replay speech. The retry button's
inline display:none is now toggled along with its hidden property, so showing it
actually makes it visible. Actual voice playback must be checked manually.

## Verification

Local Python 3.12, SQLite: Ruff passed; 385 pytest cases passed, including the
existing 354. JavaScript syntax checks passed for app.js and login.js. No AI keys
or model calls were used. Added tests cover credentials, hashes, cookies, CSRF,
logout/revocation, expiry, session persistence across app restart, account
isolation, malformed cookies, password reset, full ancestry checks, foreign keys,
legacy migration with populated chains and feedback, and migration-aware readiness.
Existing duplicate-feedback and connection-release regression tests remain green.

PostgreSQL has not been run against a live server for this delivery. Chromium
UI automation could not start in this workspace; complete the manual flow below.

Manual check:

1. Open /app anonymously and confirm redirect to sign-in.
2. Check wrong-password feedback, then sign in with a provisioned account.
3. Use A café and Water; generate, select a sentence, confirm and hear it.
4. In browser developer tools simulate a failed feedback save. Confirm speech
   starts before the save response, Retry save is visible, and retry does not
   speak again. Restore network first.
5. Sign out, then verify /app and protected API requests require sign-in again.
6. In a separate browser profile use a second account. Confirm its reuse list
   does not contain the first account's accepted sentences.

## SAD / SRS handoff

After team review, record the D-06 decision and add users, auth_sessions and the
owner relationship to the SAD ERD. Add login/me/logout sequences, session timeout
values, CSRF and the legacy-data policy. Update REQ-SEC-005 evidence with the tested
commit rather than marking the entire security section complete. Update INC-16
and test counts. The implementation does not connect the AI chain or settle D-04
(the recording of a new reuse interaction).

References:
- https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html
