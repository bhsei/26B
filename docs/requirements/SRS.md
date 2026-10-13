# Software Requirements Specification
## For Context-aware AAC Board (B - The Outliers)

Version 0.1  
Prepared by Veronika Surianinova, Jiahui Chen, Thibaut de Robien and Abid (Team B - The Outliers)  
Software Engineering course, Beihang University  
2026-10-13

## Table of Contents
<!-- TOC -->
* [1. Introduction](#1-introduction)
    * [1.1 Document Purpose](#11-document-purpose)
    * [1.2 Product Scope](#12-product-scope)
    * [1.3 Definitions, Acronyms, and Abbreviations](#13-definitions-acronyms-and-abbreviations)
    * [1.4 References](#14-references)
    * [1.5 Document Overview](#15-document-overview)
* [2. Product Overview](#2-product-overview)
    * [2.1 Product Perspective](#21-product-perspective)
    * [2.2 Product Functions](#22-product-functions)
    * [2.3 Product Constraints](#23-product-constraints)
    * [2.4 User Characteristics](#24-user-characteristics)
    * [2.5 Assumptions and Dependencies](#25-assumptions-and-dependencies)
    * [2.6 Apportioning of Requirements](#26-apportioning-of-requirements)
* [3. Requirements](#3-requirements)
    * [3.1 External Interfaces](#31-external-interfaces)
    * [3.2 Functional](#32-functional)
    * [3.3 Quality of Service](#33-quality-of-service)
    * [3.4 Compliance](#34-compliance)
    * [3.5 Design and Implementation](#35-design-and-implementation)
    * [3.6 AI/ML](#36-aiml)
* [4. Verification](#4-verification)
* [5. Appendixes](#5-appendixes)
<!-- TOC -->

## Revision History

| Name | Date | Reason For Changes | Version |
|------|------|--------------------|---------|
| Team B - The Outliers | 2026-10-13 | Initial draft based on the project proposal slides and the backend starter (API v0.1) | 0.1 |

## 1. Introduction

This SRS describes the Context-aware AAC Board: an extension of the open-source Cboard communication board that suggests complete English sentences from the user's selected symbols or text and an optional scene photo. Section 1.1 gives the purpose, 1.2 the scope, and 1.5 the document organization.

### 1.1 Document Purpose

This SRS defines **what** the Context-aware AAC Board must do, not how it is built. It is used by the four team members (frontend, backend, AI, deployment) to agree on scope, by all members for testing and integration, and by the course staff and other teams for peer review. Related documents are the API contract (`docs/API.md`), the team plan (`docs/TEAM_NEXT_STEPS.md`) and the verification record (`docs/VERIFICATION.md`).

### 1.2 Product Scope

**Product:** Context-aware AAC Board, release 0.1 (backend starter, API v0.1).

The product extends Cboard with AI. The user adds context (a scene photo, plus symbols or text that express what they want to say). The system then suggests complete English sentences. The user accepts one and confirms before the app speaks it, or rejects the options to get new ones. Example: at a café, the user selects "water" and gets "Could I have a glass of water, please?". The goal is to reduce the effort of composing everyday requests. This is a benefit the team plans to evaluate. It is not an achieved result.

| In scope | Out of scope (or not yet decided) |
|----------|-----------------------------------|
| Working web application in English | Languages other than English |
| Scene-based sentence suggestions (photo + symbols/text) | Mobile packaging (optional extension, depends on time) |
| User confirmation before speech; reject and regenerate | Recreating Cboard accounts or boards in the backend |
| Persisting requests, suggestions and feedback | Semantic caching (to be assessed) |
| First scenario: café; later more everyday situations | Production public service for untrusted users (before authentication exists) |

### 1.3 Definitions, Acronyms, and Abbreviations

| Term | Definition |
|------|------------|
| AAC | Augmentative and Alternative Communication: methods that support or replace speech for people with speech or language impairments |
| API | Application Programming Interface: a set of definitions and protocols for building and integrating application software |
| Cboard | Open-source AAC communication board web application (React/JavaScript) that this product extends |
| CI | Continuous Integration (here: GitHub Actions checks) |
| CORS | Cross-Origin Resource Sharing: browser rule that controls which web origins may call the API |
| Feedback | The user's current decision on a generation: `accepted` (with a suggestion) or `rejected` |
| Generation chain | A generation request and its regenerations (linked by `parent_request_id`) for the same unchanged inputs |
| Intention (intent text) | Free text in which the user states what they want to say (e.g. "I want water") |
| LLM | Large Language Model |
| Mock provider | Placeholder provider that returns fixed water/coffee templates. It is not AI and does not analyse photos |
| Scene hint | Short text that describes where the user is (e.g. "A café"). It is context, not the user's intention |
| Sentence provider | Replaceable backend component that generates sentence suggestions (interface `SentenceProvider`) |
| SRS | Software Requirements Specification: a document that describes the intended purpose, requirements and nature of a software product |
| Suggestion | A complete English sentence proposed to the user |
| Symbol | A Cboard tile selected by the user, sent as its English label (e.g. "water") |
| TBD | To Be Determined: a value the team has not decided yet |
| UI | User Interface: the visual part of a computer application through which a user interacts with the software |
| VLM | Vision-Language Model: a model that takes images and text as input |

### 1.4 References

| Title | Owner | Version / Date | Location | Type |
|-------|-------|----------------|----------|------|
| B - The Outliers: Context-aware AAC board (proposal slides) | Team B | 2026 | Team Google Drive (not in repository) | Normative (scope) |
| API contract | Team B | v0.1 | `docs/API.md` | Normative |
| Team next steps | Team B | v0.1 | `docs/TEAM_NEXT_STEPS.md` | Informative |
| Verification of the starter | Team B | v0.1 | `docs/VERIFICATION.md` | Informative |
| Repository README | Team B | v0.1 | `README.md` | Informative |
| Cboard source code | cboard-org | master | https://github.com/cboard-org/cboard | Normative (base product) |
| SRS template (IEEE-based) | ovikrai | master | https://github.com/ovikrai/SRS-Template-IEEE/blob/master/srs-template.md | Normative (document format) |

### 1.5 Document Overview

Section 2 gives the context: perspective, functions, constraints, users, assumptions and allocation to team members. Section 3 lists the verifiable requirements with IDs of the form `REQ-[AREA]-[NNN]`. Each requirement states in "More Information" whether it is **Implemented** in the v0.1 starter (mock provider) or **Planned**. Section 4 maps each requirement to its verification. Values the team has not decided are marked **TBD**. Changes are recorded in the Revision History and in Git commits.

## 2. Product Overview

### 2.1 Product Perspective

This is a new extension of an existing product, **Cboard** (open-source AAC board, React/JavaScript). It is a non-profit course project. The team's Cboard fork (frontend) calls a new Python backend over HTTP. The backend validates input, calls a replaceable sentence provider (AI), and stores requests, suggestions and feedback in a database.

```text
 User ──► Cboard fork (React, browser) ──HTTP/JSON──► Backend API (FastAPI)
              │                                         │        │
              ▼                                         ▼        ▼
     Browser/system speech                     Sentence provider   Database
     (English voice)                           (mock now; VLM/LLM  (SQLite now;
                                               API or local later) PostgreSQL option)
```

Ownership: frontend: Thibaut; backend and data: Veronika; AI: Jiahui; deployment and operations: Abid. There are no SLAs or support model; the product is a course prototype.

### 2.2 Product Functions

- **Add context:** select symbols and/or type an intention, optionally add a scene hint and a scene photo.
- **Generate:** receive up to three complete English sentence suggestions.
- **Choose and speak:** accept one suggestion and explicitly confirm before it is spoken; stop speech.
- **Reject and regenerate:** reject the options and get new ones that do not repeat earlier ones.
- **Keep records:** store requests, suggestions and the user's decision for evaluation.
- **Operate:** check liveness/readiness; configure database, provider and allowed frontend origin.

### 2.3 Product Constraints

- **C-01** The product must extend Cboard (React/JavaScript frontend). It must not copy Cboard code into the backend repository.
- **C-02** The backend must use Python with FastAPI.
- **C-03** The user interface and all generated sentences must be in English.
- **C-04** The AI part must be accessed only through the replaceable sentence-provider interface. The model choice (hosted VLM/LLM API, or local inference with PyTorch) is still open.
- **C-05** Data must be stored in a relational database: SQLite for local development, PostgreSQL as the planned server database. Schema changes must use Alembic migrations.
- **C-06** Deployment must use Docker Compose. The hosting provider is still open.
- **C-07** The team must use GitHub (`bhsei/26B`) and the course Git workflow, plus Google Drive for shared files.
- **C-08** The product must be a working web application. A mobile version is optional.
- **C-09** The current release is a local development prototype. It must not be offered to untrusted users before authentication and user ownership exist.

### 2.4 User Characteristics

| User class | Description | Expertise | Main goals |
|------------|-------------|-----------|------------|
| AAC user | Person with a speech or language impairment who uses the board to communicate everyday requests | Uses Cboard symbols; may have difficulty composing full sentences | Say what they mean with less effort; stay in control of what is spoken |
| Developer / evaluator (team) | Team members who run the system locally and evaluate sentence quality and response time | Software engineering students | Integrate, test and evaluate with synthetic inputs |
| Operator (team) | Team member who configures, deploys and monitors the backend | Docker, configuration, CI | Start the system reproducibly; check health |

Accessibility: the user may need large, simple choices and must never hear a sentence they did not confirm. Specific accessibility standards are TBD (see 3.1.1).

### 2.5 Assumptions and Dependencies

| # | Assumption / dependency | Impact if false |
|---|-------------------------|-----------------|
| A-1 | Cboard can be run locally and extended by the team | Frontend integration (REQ-FUNC-010) is delayed or must use the demo page |
| A-2 | The device's browser/OS provides an English speech voice | Speech is unavailable; the choice is still saved (REQ-FUNC-007) |
| A-3 | A suitable VLM/LLM (hosted API or local) is available within budget | No real sentence generation; only the mock provider works |
| A-4 | A photo alone cannot reliably reveal intent, so the user's symbols/text are always needed | If ignored, the system could invent intentions (see REQ-ML-003) |
| A-5 | Development uses synthetic inputs only | Real personal data would require consent and retention rules first (REQ-SEC-007) |
| A-6 | Third-party libraries (FastAPI, SQLAlchemy, Alembic, Pydantic, Pillow, psycopg) remain available at pinned versions | Build or install fails; versions must be updated |

### 2.6 Apportioning of Requirements

| Requirement(s) | Component | Owner | Increment |
|----------------|-----------|-------|-----------|
| REQ-FUNC-001 … 006, 009; REQ-INT-004, 005; REQ-SEC-001, 002, 004; REQ-REL-001 … 003; REQ-AVAIL-001; REQ-PERF-001 | Backend API + database | Veronika | v0.1 (implemented) |
| REQ-INST-001; REQ-MAINT-001; REQ-PORT-001 | Backend build and configuration | Veronika | v0.1 (PostgreSQL check pending) |
| REQ-BUILD-001 | CI (GitHub Actions) | Abid | v0.1 (implemented) |
| REQ-FUNC-007, 008; REQ-INT-001 … 003 | Demo page (v0.1), then Cboard fork | Thibaut | v0.1 demo implemented; Cboard in Increment 1 |
| REQ-FUNC-010; REQ-INT-006; REQ-SEC-004 (display); REQ-POC-001 | Cboard fork + backend | Thibaut, Veronika | Increment 1: café scenario |
| REQ-ML-001 … 006 | Sentence provider (AI) | Jiahui | Increment 1 |
| REQ-DIST-001; REQ-SEC-003, 005, 006; REQ-OBS-001 | Deployment and operations | Abid | Before any public trial |
| REQ-SEC-007; REQ-COMP-001, 002; REQ-CM-001 | Project-wide | All | Before real-user trials / ongoing |
| REQ-FUNC-011 | All components | All | Increment 2: more situations |
| Mobile version | Frontend | Thibaut | Optional, deferred |

## 3. Requirements

Each requirement uses the template fields. "Status" in More Information is **Implemented** (in the v0.1 starter, mock provider) or **Planned**.

### 3.1 External Interfaces

#### 3.1.1 User Interfaces

- ID: REQ-INT-001
- Title: English communication flow
- Statement: The UI shall present, in English, three steps: (1) add context: symbols, intention text, scene hint and optional photo; (2) view up to three suggestions; (3) select a suggestion and use "Confirm and speak", "Reject and try again" and "Stop speaking".
- Rationale: Matches the proposed flow "Add context → Generate → Choose & speak" (C-03).
- Acceptance Criteria: All three steps and the three action buttons are visible and usable; "Confirm and speak" is disabled until a suggestion is selected.
- Verification Method: Demonstration
- More Information: Status: Implemented in demo page (`app/static/`); Planned in Cboard fork. Visual design of the Cboard UI: TBD. Accessibility standard (e.g. WCAG level): TBD.

- ID: REQ-INT-002
- Title: Status, notices and errors are shown, never spoken
- Statement: The UI shall display the backend's notice and error messages as text and shall not pass them to speech output.
- Rationale: Only a sentence the user confirmed may be spoken.
- Acceptance Criteria: An error (e.g. invalid photo) or empty result appears as on-screen text; no audio is produced.
- Verification Method: Demonstration
- More Information: Status: Implemented in demo page (status line uses `aria-live="polite"`).

#### 3.1.2 Hardware Interfaces

- ID: REQ-INT-003
- Title: Photo input and audio output
- Statement: The system shall accept a scene photo selected on the user's device (file or camera, as offered by the browser) and shall speak through the device's browser/system speech output with an English voice.
- Rationale: The product uses a scene photo for context and speech for output; no special hardware is required.
- Acceptance Criteria: A JPEG/PNG/WebP photo can be selected and sent; a confirmed sentence is heard on a device with an installed English voice; if speech is unavailable, the UI says so and the choice is still saved.
- Verification Method: Demonstration
- More Information: Status: Implemented in demo page (Web Speech API, `en-US`). Voice availability varies by device; actual audio has not been verified yet (`docs/VERIFICATION.md`).

#### 3.1.3 Software Interfaces

- ID: REQ-INT-004
- Title: Backend REST API v0.1
- Statement: The backend shall provide these HTTP endpoints, as defined in `docs/API.md`: `POST /api/suggestions` (JSON), `POST /api/suggestions/image` (multipart: `payload` JSON + `image`), `PUT /api/requests/{request_id}/feedback`, `GET /health`, `GET /ready`, and an OpenAPI description at `/openapi.json`.
- Rationale: Contract between the Cboard fork and the backend.
- Acceptance Criteria: Endpoints return the documented status codes (201, 200, 404, 409, 413, 415, 422, 502, 503) and a `detail` field on errors.
- Verification Method: Test
- More Information: Status: Implemented. There is no authentication in v0.1 (see REQ-SEC-005). Cross-origin access is limited to the exact origins in `CORS_ORIGINS`; CORS is not an authentication mechanism.

- ID: REQ-INT-005
- Title: Sentence provider interface
- Statement: The backend shall call the AI only through the `SentenceProvider` interface. Input: validated request, sanitized JPEG bytes or none, and the sentences to exclude. Output: up to three sentences and a truthful `image_analyzed` flag.
- Rationale: Keeps the model choice open (C-04) and allows the mock to be replaced.
- Acceptance Criteria: A test provider injected through `create_app(settings, provider)` is used for generation without other code changes.
- Verification Method: Test
- More Information: Status: Implemented (mock only). The provider is selected with `AI_PROVIDER`; unsupported values fail configuration validation.

- ID: REQ-INT-006
- Title: Cboard symbol mapping
- Statement: The Cboard fork shall send the English labels of the selected Cboard tiles as `selected_symbols`, and shall call the API from a configurable base URL.
- Rationale: First integration step without recreating Cboard boards or accounts in the backend.
- Acceptance Criteria: Selecting the "water" tile in Cboard sends `["water"]` and shows the returned suggestions.
- Verification Method: Demonstration
- More Information: Status: Planned (Thibaut).

### 3.2 Functional

- ID: REQ-FUNC-001
- Title: Enter communication context
- Statement: The system shall accept a request with selected symbols (0–20, each 1–80 characters), intention text (≤500 characters), scene hint (≤500 characters) and language `en`, and shall reject it if there is neither a symbol nor a nonblank intention.
- Rationale: The user's symbols or text express the intention; the scene only adds context.
- Acceptance Criteria: Valid input returns 201; empty intention with no symbols, too many or too long values, or unknown fields return 422.
- Verification Method: Test
- More Information: Status: Implemented.

- ID: REQ-FUNC-002
- Title: Optional scene photo
- Statement: The system shall optionally accept one scene photo in JPEG, PNG or WebP format of at most 5 MiB and 20 megapixels with the request.
- Rationale: The photo gives scene context for sentence generation.
- Acceptance Criteria: A valid photo returns 201 with `image_supplied=true`; a photo over 5 MiB or 20 MP returns 413; an invalid or unsupported file returns 415.
- Verification Method: Test
- More Information: Status: Implemented. The mock does not analyse photos (`image_analyzed=false`).

- ID: REQ-FUNC-003
- Title: Generate sentence suggestions
- Statement: The system shall return 0–3 complete English sentence suggestions for a valid request, each with a unique ID, together with the request ID, provider name, `image_supplied`, `image_analyzed` and a notice.
- Rationale: Core function: suggest complete sentences from scene and intent.
- Acceptance Criteria: Café/water input returns up to three water requests (e.g. "Could I have a glass of water, please?").
- Verification Method: Test
- More Information: Status: Implemented with mock (water/coffee templates only); real AI is Planned (REQ-ML-001).

- ID: REQ-FUNC-004
- Title: Handle "no suggestions"
- Statement: When no suggestion can be produced, the system shall return an empty list with an explanatory notice, and the UI shall let the user edit the input.
- Rationale: An empty result is valid and must not look like a failure or produce a wrong sentence.
- Acceptance Criteria: Unsupported or negative intention (e.g. "I do not want water") returns 201 with an empty list and a notice.
- Verification Method: Test
- More Information: Status: Implemented.

- ID: REQ-FUNC-005
- Title: Accept a suggestion
- Statement: The system shall record the user's acceptance of one suggestion that belongs to the same request.
- Rationale: Stores which sentence the user chose, for evaluation.
- Acceptance Criteria: Accepting a suggestion of the request returns 200; accepting a suggestion from another request returns 422; an unknown request returns 404.
- Verification Method: Test
- More Information: Status: Implemented.

- ID: REQ-FUNC-006
- Title: Reject and regenerate without repetition
- Statement: The system shall record a rejection and, on a new generation with the same inputs and `parent_request_id`, shall not return any sentence already shown in that generation chain.
- Rationale: "Reject to generate new options" (proposal); repeated sentences waste the user's effort.
- Acceptance Criteria: A regeneration returns only new sentences; changed inputs with a parent return 409; more than 20 ancestors return 409.
- Verification Method: Test
- More Information: Status: Implemented. The backend does not keep photos, so the client must upload the photo again; a changed photo requires a new chain.

- ID: REQ-FUNC-007
- Title: Speak only after explicit confirmation
- Statement: The UI shall speak a suggestion only after the user selects it and presses a confirm action, shall save the acceptance at that moment, and shall provide a control to stop speech.
- Rationale: The user must stay in control of what is said in their name.
- Acceptance Criteria: Showing suggestions produces no audio; "Confirm and speak" saves the acceptance and speaks the selected text; "Stop speaking" stops it.
- Verification Method: Demonstration
- More Information: Status: Implemented in demo page; Planned in Cboard fork.

- ID: REQ-FUNC-008
- Title: Clear stale suggestions
- Statement: The UI shall clear previous suggestions whenever the user changes any input.
- Rationale: Prevents accepting or speaking a sentence generated for a different intention.
- Acceptance Criteria: After an input change, the old suggestions are gone and "Confirm and speak" is disabled.
- Verification Method: Demonstration
- More Information: Status: Implemented in demo page; Planned in Cboard fork.

- ID: REQ-FUNC-009
- Title: Persist requests, suggestions and feedback
- Statement: For each successful generation the system shall store the inputs (scene hint, intention, symbols, language), photo-presence flag, provider name, latency, parent link, the suggestions, and one current feedback decision per request.
- Rationale: Needed to evaluate sentence quality and response time.
- Acceptance Criteria: Records remain after a backend restart; a later feedback replaces the earlier decision without duplicate rows.
- Verification Method: Test
- More Information: Status: Implemented. Raw photos are not stored (REQ-SEC-001).

- ID: REQ-FUNC-010
- Title: End-to-end use inside Cboard
- Statement: The Cboard fork shall perform REQ-FUNC-003 to REQ-FUNC-008 against the backend.
- Rationale: The product is an extension of Cboard (C-01).
- Acceptance Criteria: See REQ-POC-001.
- Verification Method: Demonstration
- More Information: Status: Planned (Increment 1).

- ID: REQ-FUNC-011
- Title: More everyday situations
- Statement: The system should support everyday situations beyond the café, such as bus travel and a doctor's visit.
- Rationale: Planned expansion after the first scenario works.
- Acceptance Criteria: TBD (situation list and evaluation set to be defined by the team).
- Verification Method: Demonstration
- More Information: Status: Planned (Increment 2).

### 3.3 Quality of Service

#### 3.3.1 Performance

- ID: REQ-PERF-001
- Title: Measured generation response time
- Statement: The system shall measure and store the provider latency (ms) of every generation, and the end-to-end response time shall not exceed TBD seconds under TBD conditions.
- Rationale: The proposal plans to "evaluate sentence quality and response time"; no target has been set yet.
- Acceptance Criteria: `latency_ms` is stored for each request; threshold TBD.
- Verification Method: Analysis
- More Information: Status: Measurement Implemented; threshold TBD. Whether caching improves repeated requests will be assessed (pgvector only if semantic caching proves useful).

#### 3.3.2 Security

- ID: REQ-SEC-001
- Title: Photo privacy
- Statement: The system shall decode each photo, resize it to at most 1024×1024, re-encode it as JPEG without metadata before passing it to the provider, and shall not store raw photos or their metadata.
- Rationale: Photos of the user's surroundings are personal data.
- Acceptance Criteria: The database contains only the photo-presence flag; provider input has no EXIF metadata.
- Verification Method: Inspection
- More Information: Status: Implemented. This does **not** blur faces or anonymise image content.

- ID: REQ-SEC-002
- Title: No internal details in responses
- Statement: The system shall not include provider exceptions, stack traces or credentials in API responses.
- Rationale: Prevents leaking secrets and internals.
- Acceptance Criteria: A failing provider produces only a generic 502/503 message.
- Verification Method: Test
- More Information: Status: Implemented.

- ID: REQ-SEC-003
- Title: Secrets in environment only
- Statement: Credentials (database password, AI API keys) shall be provided through environment variables and shall never be committed to the repository or written in documents.
- Rationale: The repository is public.
- Acceptance Criteria: `.env` is git-ignored; repository inspection finds no secrets.
- Verification Method: Inspection
- More Information: Status: Implemented for configuration (`.env.example`); applies to all future AI keys.

- ID: REQ-SEC-004
- Title: Input validation and safe display
- Statement: The system shall validate all input lengths, types and fields (REQ-FUNC-001, 002) and the UI shall render generated text as plain escaped text.
- Rationale: Prevents malformed input and script injection through generated text.
- Acceptance Criteria: Invalid input returns 422/413/415; text containing HTML is shown literally.
- Verification Method: Test
- More Information: Status: Backend validation Implemented; Cboard rendering Planned (React's normal escaped rendering).

- ID: REQ-SEC-005
- Title: Authentication and data ownership
- Statement: Before any access by untrusted users, the system shall authenticate users and restrict each user to their own requests and feedback.
- Rationale: Request UUIDs are not authorization (C-09).
- Acceptance Criteria: TBD (method to be selected).
- Verification Method: Test
- More Information: Status: Planned; not implemented in v0.1.

- ID: REQ-SEC-006
- Title: Abuse and cost limits
- Statement: Before a paid AI provider is connected, the deployment shall enforce total request-size limits, timeouts, rate limits and spending limits.
- Rationale: The image check runs after multipart parsing; paid API calls can create costs.
- Acceptance Criteria: Values TBD.
- Verification Method: Test
- More Information: Status: Planned (Abid).

- ID: REQ-SEC-007
- Title: Consent and data retention
- Statement: Before trials with real users, the team shall define consent, and retention and deletion rules for stored text.
- Rationale: There is no automatic retention or deletion policy yet.
- Acceptance Criteria: A documented policy exists and is applied; values TBD.
- Verification Method: Inspection
- More Information: Status: Planned.

#### 3.3.3 Reliability

- ID: REQ-REL-001
- Title: Validate provider output
- Statement: The system shall reject provider output that is not a list of at most three nonblank strings of at most 300 characters, returning 502 without storing anything; duplicates and excluded sentences shall be removed.
- Rationale: Future AI output may be malformed.
- Acceptance Criteria: Invalid provider output returns 502 and no record is saved.
- Verification Method: Test
- More Information: Status: Implemented.

- ID: REQ-REL-002
- Title: Provider unavailability
- Statement: The system shall return 503 "Generation unavailable" when the provider is unavailable, and real providers shall use explicit network timeouts.
- Rationale: Graceful failure instead of hanging requests.
- Acceptance Criteria: A provider that raises `ProviderUnavailable` produces 503; timeout value TBD.
- Verification Method: Test
- More Information: Status: 503 mapping Implemented; timeouts Planned with the real provider.

- ID: REQ-REL-003
- Title: Retry-safe feedback
- Statement: Repeating the same feedback request shall not create duplicate records.
- Rationale: Network retries must not corrupt evaluation data.
- Acceptance Criteria: Two identical PUTs leave one feedback row.
- Verification Method: Test
- More Information: Status: Implemented.

#### 3.3.4 Availability

- ID: REQ-AVAIL-001
- Title: Liveness and readiness checks
- Statement: The system shall provide `/health` (process alive, provider name, version) and `/ready` (database reachable and migrations applied, else 503). The availability target is TBD.
- Rationale: Lets the operator and the container platform detect failures.
- Acceptance Criteria: `/ready` returns 503 when migrations are missing and "ready" after `alembic upgrade head`.
- Verification Method: Test
- More Information: Status: Checks Implemented; availability target TBD (hosting not selected).

#### 3.3.5 Observability

- ID: REQ-OBS-001
- Title: Privacy-safe logging
- Statement: Logs shall not contain photos, complete intentions or secrets.
- Rationale: Logs must not become an archive of personal data.
- Acceptance Criteria: Log inspection during a test run finds none of these items.
- Verification Method: Inspection
- More Information: Status: Planned. Per-request provider name and latency are already stored in the database (REQ-FUNC-009). Metrics, dashboards and alerts: TBD.

### 3.4 Compliance

- ID: REQ-COMP-001
- Title: Third-party licenses
- Statement: The team shall respect the licenses of Cboard and of all dependencies, and shall select a license for this repository.
- Rationale: The product extends open-source software; no repository license has been selected yet.
- Acceptance Criteria: A license file exists and is compatible with Cboard's license.
- Verification Method: Inspection
- More Information: Status: Planned. Repository license: TBD.

- ID: REQ-COMP-002
- Title: Course workflow
- Statement: All work shall follow the course GitHub guide: commit message format `W<week> - <summary>; <description>`, one commit per document, and peer reviews as GitHub Issues.
- Rationale: Course requirement (C-07).
- Acceptance Criteria: Git history and Issues follow the guide.
- Verification Method: Inspection
- More Information: Status: Applied.

### 3.5 Design and Implementation

#### 3.5.1 Installation

- ID: REQ-INST-001
- Title: Documented local installation
- Statement: The backend shall be installable on Python 3.12 from `requirements.txt`, configured by copying `.env.example` to `.env`, migrated with `python -m alembic upgrade head`, and started with uvicorn.
- Rationale: Every member must be able to run the backend.
- Acceptance Criteria: Following the README, `/ready` returns "ready".
- Verification Method: Demonstration
- More Information: Status: Implemented. Configuration variables: `DATABASE_URL`, `AI_PROVIDER`, `CORS_ORIGINS`, `MAX_IMAGE_BYTES`.

#### 3.5.2 Build and Delivery

- ID: REQ-BUILD-001
- Title: Continuous integration checks
- Statement: Every push and pull request shall run lint (ruff), tests (pytest) and migration checks (alembic upgrade + check) on Python 3.12, with pinned direct dependencies.
- Rationale: Keeps `main` working and reproducible.
- Acceptance Criteria: The GitHub Actions workflow passes.
- Verification Method: Inspection
- More Information: Status: Implemented (`.github/workflows/tests.yml`).

#### 3.5.3 Distribution

- ID: REQ-DIST-001
- Title: Containerized deployment
- Statement: The backend and database shall be deployable with Docker Compose; migrations shall run once per release before the app starts; HTTPS, persistent storage, backups and secret handling shall be configured.
- Rationale: Proposed deployment stack (C-06).
- Acceptance Criteria: The stack starts from documented configuration and `/ready` returns "ready".
- Verification Method: Demonstration
- More Information: Status: Planned (Abid). Hosting provider: TBD.

#### 3.5.4 Maintainability

- ID: REQ-MAINT-001
- Title: Replaceable components and versioned schema
- Statement: The AI shall stay behind the provider interface (REQ-INT-005), and every database model change shall come with an Alembic migration.
- Rationale: Allows the model and database to change without rewriting the API.
- Acceptance Criteria: `alembic check` reports no differences; the provider can be swapped by configuration.
- Verification Method: Inspection
- More Information: Status: Implemented.

#### 3.5.5 Reusability

The product reuses Cboard (boards, symbols, frontend) and does not recreate its accounts or boards. The backend API and provider interface are generic: they accept symbol labels and text, not Cboard-specific IDs. No further reuse requirements have been defined.

#### 3.5.6 Portability

- ID: REQ-PORT-001
- Title: Database and platform portability
- Statement: The backend shall run with SQLite (local) or PostgreSQL (server) selected only by `DATABASE_URL`, and the frontend shall run in a web browser.
- Rationale: Zero-setup local development and a server database for deployment.
- Acceptance Criteria: Migrations and tests pass on both databases.
- Verification Method: Test
- More Information: Status: SQLite verified; PostgreSQL not yet verified with a live server. Windows execution not yet verified. Mobile version: optional.

#### 3.5.7 Cost

Non-profit course project. The choice between a hosted model API (cost per call) and local inference (hardware cost) is still open, as is the hosting provider. Budget: TBD. Spending limits are required before a paid provider is connected (REQ-SEC-006).

#### 3.5.8 Deadline

Milestone dates: TBD. Planned order of increments:

1. Set up Cboard locally.
2. Connect one complete café scenario (REQ-POC-001).
3. Evaluate sentence quality and response time.
4. Expand to more everyday situations (REQ-FUNC-011).
5. Optional: mobile version.

#### 3.5.9 Proof of Concept

- ID: REQ-POC-001
- Title: Café end-to-end scenario
- Statement: In the Cboard fork, the user shall be able to select the "water" tile, see suggestions, reject and regenerate, select one and explicitly speak it, and the feedback shall persist after a backend restart.
- Rationale: First shared milestone; validates the integration before more situations are added.
- Acceptance Criteria: The full scenario works in Cboard and keeps working while the mock is replaced by the real provider.
- Verification Method: Demonstration
- More Information: Status: Planned (Increment 1). Timebox: TBD.

#### 3.5.10 Change Management

- ID: REQ-CM-001
- Title: Controlled changes
- Statement: Changes shall be committed per document with the course message format, API contract changes shall update `docs/API.md` and its version, schema changes shall use migrations, and SRS changes shall be recorded in the Revision History.
- Rationale: Keeps history auditable and integration stable.
- Acceptance Criteria: Each API or SRS change has a matching document and version update.
- Verification Method: Inspection
- More Information: Status: Applied.

### 3.6 AI/ML

#### 3.6.1 Model Specification

- ID: REQ-ML-001
- Title: Context-aware sentence generation
- Statement: The real provider shall use a vision-language model to obtain scene context from the photo and a language model to propose up to three complete English sentences that express the user's selected symbols or text.
- Rationale: Core AI function of the proposal.
- Acceptance Criteria: On the team's evaluation set, suggestions are rated for correctness of intent and fluency; thresholds TBD.
- Verification Method: Analysis
- More Information: Status: Planned (Jiahui). Model: hosted VLM/LLM API or local (PyTorch), TBD.

- ID: REQ-ML-002
- Title: Truthful photo-analysis flag
- Statement: The provider shall set `image_analyzed=true` only when it actually used the photo content.
- Rationale: The user and evaluators must know whether the photo influenced the result.
- Acceptance Criteria: Mock always returns `false`; a real provider returns `true` only when the image was processed.
- Verification Method: Test
- More Information: Status: Implemented for mock.

#### 3.6.2 Data Management

The proposal covers model selection and prompting; no training or fine-tuning dataset is defined. Development and evaluation use **synthetic inputs** only (e.g. a synthetic café photo with the explicit intention "water"). Stored data is limited to REQ-FUNC-009 and excludes raw photos (REQ-SEC-001). The team will define a small evaluation set (contents TBD).

#### 3.6.3 Guardrails

- ID: REQ-ML-003
- Title: The user's intention is authoritative
- Statement: The provider shall base each suggestion on the user's symbols or text, shall never invent an intention from the photo or scene alone, and shall never turn a negative intention into an affirmative request.
- Rationale: A photo cannot reliably reveal intent; a wrong sentence is spoken in the user's name.
- Acceptance Criteria: Evaluation cases with negation, ambiguous images and incorrect scene hints produce no contradicting suggestions.
- Verification Method: Test
- More Information: Status: Implemented for mock (negative or unknown intent returns no suggestions); Planned for the real provider.

- ID: REQ-ML-004
- Title: Scene text is data
- Statement: The provider shall treat the scene hint and intention text as data, not as instructions to the model.
- Rationale: Protects against prompt injection.
- Acceptance Criteria: A scene hint that contains instructions does not change the provider's behavior beyond context.
- Verification Method: Test
- More Information: Status: Planned. Output limits are enforced by REQ-REL-001.

#### 3.6.4 Ethics

The target users are people with speech or language impairments, so the product must not put words in their mouth. Transparency: responses show whether the mock or a real provider was used and whether the photo was analysed (REQ-ML-002). The benefit of reducing effort is a hypothesis to evaluate, not a claim. Fairness and explainability metrics: TBD.

#### 3.6.5 Human-in-the-Loop

- ID: REQ-ML-005
- Title: User confirms every spoken sentence
- Statement: No AI output shall be spoken or treated as accepted without the AAC user's explicit selection and confirmation; the user can always reject and regenerate or edit the input.
- Rationale: The user stays in control of their own message (2.4).
- Acceptance Criteria: Same as REQ-FUNC-007 and REQ-FUNC-006; every acceptance is stored with the chosen suggestion.
- Verification Method: Demonstration
- More Information: Status: Implemented in demo page.

#### 3.6.6 Model Lifecycle and Operations

- ID: REQ-ML-006
- Title: Provider selection and evaluation before use
- Statement: The provider shall be selected by configuration (`AI_PROVIDER`), each stored request shall record the provider name, and a new provider shall pass the team's evaluation (including negation, ambiguous images, incorrect scene hints, and refusal/regeneration) before it replaces the current one.
- Rationale: Allows comparison and rollback to the previous provider.
- Acceptance Criteria: Unsupported provider values fail at startup; evaluation results are documented; rollback is a configuration change.
- Verification Method: Inspection
- More Information: Status: Configuration and recording Implemented; evaluation Planned.

## 4. Verification

Automated tests are in `tests/test_api.py` and run in CI. "Passed" means passed in the v0.1 verification (`docs/VERIFICATION.md`, Linux, Python 3.12, SQLite, mock provider).

| Requirement ID | Verification Method | Test/Artifact Link | Status | Evidence |
|----------------|---------------------|--------------------|--------|----------|
| REQ-INT-001 | demonstration | `docs/VERIFICATION.md` manual check | Not run | Browser click-through not yet verified |
| REQ-INT-002 | demonstration | `docs/VERIFICATION.md` manual check | Not run | |
| REQ-INT-003 | demonstration | `docs/VERIFICATION.md` manual check 2 | Not run | Actual speech audio not verified |
| REQ-INT-004 | test | `tests/test_api.py` (all) | Passed | `docs/VERIFICATION.md` |
| REQ-INT-005 | test | `test_provider_failure_is_safe`, `test_invalid_provider_output_is_not_saved` | Passed | `docs/VERIFICATION.md` |
| REQ-INT-006 | demonstration | REQ-POC-001 scenario | Not started | |
| REQ-FUNC-001 | test | `test_invalid_inputs` | Passed | `docs/VERIFICATION.md` |
| REQ-FUNC-002 | test | `test_photo_input`, `test_invalid_photo_and_payload`, `test_oversized_photo` | Passed | `docs/VERIFICATION.md` |
| REQ-FUNC-003 | test | `test_generation_persists_and_survives_restart` | Passed (mock) | `docs/VERIFICATION.md` |
| REQ-FUNC-004 | test | `test_mock_does_not_misrepresent_free_text` | Passed | `docs/VERIFICATION.md` |
| REQ-FUNC-005 | test | `test_cannot_accept_another_requests_suggestion`, `test_invalid_feedback`, `test_unknown_request` | Passed | `docs/VERIFICATION.md` |
| REQ-FUNC-006 | test | `test_regeneration_excludes_entire_chain`, `test_changed_intent_requires_new_chain` | Passed | `docs/VERIFICATION.md` |
| REQ-FUNC-007 | demonstration | `docs/VERIFICATION.md` manual check 2 | Not run | |
| REQ-FUNC-008 | demonstration | `docs/VERIFICATION.md` manual check 5 | Not run | |
| REQ-FUNC-009 | test | `test_generation_persists_and_survives_restart`, `test_feedback_is_idempotent_and_can_be_changed` | Passed | `docs/VERIFICATION.md` |
| REQ-FUNC-010 | demonstration | REQ-POC-001 scenario | Not started | |
| REQ-FUNC-011 | demonstration | TBD | Not started | |
| REQ-PERF-001 | analysis | TBD evaluation report | WIP | `latency_ms` recorded; threshold TBD |
| REQ-SEC-001 | inspection | `app/images.py`, `app/models.py` | WIP | |
| REQ-SEC-002 | test | `test_provider_failure_is_safe` | Passed | `docs/VERIFICATION.md` |
| REQ-SEC-003 | inspection | `.gitignore`, `.env.example` | WIP | |
| REQ-SEC-004 | test | `test_invalid_inputs`, `test_invalid_photo_and_payload` | Passed (backend) | Cboard rendering not started |
| REQ-SEC-005 | test | TBD | Not started | |
| REQ-SEC-006 | test | TBD | Not started | |
| REQ-SEC-007 | inspection | TBD policy document | Not started | |
| REQ-REL-001 | test | `test_invalid_provider_output_is_not_saved` | Passed | `docs/VERIFICATION.md` |
| REQ-REL-002 | test | `test_provider_failure_is_safe` | Passed (503 mapping) | Timeouts not started |
| REQ-REL-003 | test | `test_feedback_is_idempotent_and_can_be_changed` | Passed | `docs/VERIFICATION.md` |
| REQ-AVAIL-001 | test | `test_health_ready_and_demo`, `test_readiness_requires_migration` | Passed | `docs/VERIFICATION.md` |
| REQ-OBS-001 | inspection | TBD | Not started | |
| REQ-COMP-001 | inspection | License file (TBD) | Not started | |
| REQ-COMP-002 | inspection | Git history, Issues | WIP | |
| REQ-INST-001 | demonstration | `README.md` quick start | WIP | Windows not verified |
| REQ-BUILD-001 | inspection | `.github/workflows/tests.yml` | Passed | CI runs |
| REQ-DIST-001 | demonstration | TBD | Not started | |
| REQ-MAINT-001 | inspection | `test_migration_roundtrip_and_schema_match` | Passed | `docs/VERIFICATION.md` |
| REQ-PORT-001 | test | `test_migration_roundtrip_and_schema_match` | WIP | SQLite only; PostgreSQL not run |
| REQ-POC-001 | demonstration | Café scenario script (TBD) | Not started | |
| REQ-CM-001 | inspection | Git history, `docs/API.md` | WIP | |
| REQ-ML-001 | analysis | Evaluation set (TBD) | Not started | |
| REQ-ML-002 | test | `test_photo_input` | Passed (mock) | `docs/VERIFICATION.md` |
| REQ-ML-003 | test | `test_mock_does_not_misrepresent_free_text` | Passed (mock) | Real provider not started |
| REQ-ML-004 | test | TBD | Not started | |
| REQ-ML-005 | demonstration | `docs/VERIFICATION.md` manual check 2 | Not run | |
| REQ-ML-006 | inspection | `app/config.py`; evaluation report (TBD) | WIP | |

## 5. Appendixes

**A. Example scenario (illustrative, from the proposal).** At a café, the user adds a photo of the scene and selects the "water" symbol. The system suggests "Could I have a glass of water, please?" and other options. The user selects one and confirms, and the app speaks it. If none fit, the user rejects them and receives new options.

**B. Open issues (TBD).**

| # | Open issue | Related requirements |
|---|------------|----------------------|
| 1 | Response time and availability targets | REQ-PERF-001, REQ-AVAIL-001 |
| 2 | Model choice: hosted API or local inference | REQ-ML-001, 3.5.7 |
| 3 | Hosting provider | REQ-DIST-001 |
| 4 | Authentication method | REQ-SEC-005 |
| 5 | Request, rate and spending limit values; provider timeout | REQ-SEC-006, REQ-REL-002 |
| 6 | Consent and retention policy | REQ-SEC-007 |
| 7 | Accessibility standard for the UI | REQ-INT-001 |
| 8 | Evaluation set and quality thresholds | REQ-ML-001, REQ-FUNC-011 |
| 9 | Repository license | REQ-COMP-001 |
| 10 | Milestone dates | 3.5.8 |

**C. Data model (v0.1).** See `app/models.py`: `generation_requests` (inputs, photo flag, provider, latency, parent link), `suggestions` (text, position), `feedback` (one current decision per request).
