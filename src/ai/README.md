# Gemini Flash scripts

First experiments for the real sentence provider (see `docs/design/AI_Model_Plan.md`).
They call the Gemini REST API (`generateContent`) with `httpx` and are not used by
the backend yet. Default model: `gemini-3.5-flash` (change with `--model`).

New API keys cannot use the 2.5 models: they return 404 "no longer available to new
users". `gemini-3.8-flash` also works but was overloaded (503) and timed out in the
first test on 2026-10-21; try it with `--model gemini-3.8-flash`.

## Setup

1. Create a key in Google AI Studio (https://aistudio.google.com/apikey).
2. Add it to `.env` in the repository root, which is git-ignored:

   ```dotenv
   GEMINI_API_KEY=your-key-here
   ```

   Never commit the key, paste it in documents or Issues, or put it in a URL.
3. Install the dev requirements (includes `httpx`):

   ```bash
   python -m pip install -r requirements-dev.txt
   ```

Run every command from the repository root. On Windows use `.venv\Scripts\python.exe`
in place of `python`. Gemini is not available in mainland China or Hong Kong; a
location error there means the network, not the script.

## Example calls

```bash
python -m src.ai.gemini_quickstart --list
```

```bash
python -m src.ai.gemini_quickstart
```

The second command prints the model's token limits and runs three cases: text only,
photo + symbol, and a negation. For each it shows the sentences, latency and token
use (prompt split by TEXT/IMAGE, output, thinking). The photo is a drawn café scene
sent with `mediaResolution=LOW`, measured at 266 image tokens (the default is about
1,120). Thinking uses the lowest level the model accepts (`minimal`; `low` on 3.8
Flash); change it with `--thinking-level`. Slow answers: raise `--timeout` (default
30 s). Use synthetic photos only: free-tier inputs may be used by Google to improve
its products.

### Saving the generations

```bash
python -m src.ai.gemini_quickstart --save
```

```bash
python -m src.ai.gemini_quickstart --save results/run1.jsonl
```

`--save` alone appends to `generations.jsonl` in the current folder; a path picks
another file (folders are created). Each call becomes one JSON line, so runs add up
in the same file and can be compared later. Failed calls are saved too.

```json
{"time_utc": "2026-10-21T09:12:03+00:00", "model": "gemini-3.5-flash",
 "prompt_version": "862813ee", "thinking": {"thinkingLevel": "minimal"},
 "case": "Photo + symbol 'water'",
 "input": {"symbols": ["water"], "intention": "", "scene_hint": "A café"},
 "image": "synthetic drawn café", "status": 200, "latency_s": 10.14,
 "sentences": ["Water, please.", "Could I have some water?", "I would like water."],
 "finish_reason": "STOP",
 "usage": {"prompt": 412, "prompt_by_modality": {"TEXT": 146, "IMAGE": 266},
           "output": 36, "thinking": 0, "total": 448}, "error": null}
```

(Shown on several lines here; in the file each record is one line. The values are
from the 2026-10-21 run; the timestamp is illustrative.)

- `prompt_version` is the first 8 characters of the SHA-256 of the system prompt, so
  results stay linked to the prompt that produced them.
- The API key and the image data are never written. For a photo only its file name
  is kept.
- The file holds the inputs typed for the test. Keep them synthetic, and decide as a
  team before committing result files.

## Rate-limit checks

Google sends no rate-limit headers. The limit becomes visible in the 429 response,
which names the quota (per minute or per day), its value and the retry delay.
Compare the result with the limits page in AI Studio
(https://aistudio.google.com/rate-limit).

Find the per-minute limit (stops at the first 429, at most 15 requests):

```bash
python -m src.ai.gemini_rate_limit burst
```

Same, then wait the retry delay and confirm the quota recovers:

```bash
python -m src.ai.gemini_rate_limit burst --wait-retry
```

Check that a planned rate is sustainable (for example 5 per minute for 2 minutes):

```bash
python -m src.ai.gemini_rate_limit paced --rpm 5 --minutes 2
```

Keep a CSV log of a run (do not commit logs):

```bash
python -m src.ai.gemini_rate_limit burst --csv rate_limit_log.csv
```

Every request counts against the daily quota (RPD). A burst uses at most 15, a paced
run uses `rpm × minutes`. Do not run checks just before a demo.

### Measured on 2026-10-21 (new free-tier key, `gemini-3.5-flash`)

| Quota (from the 429 response) | Limit |
| --- | --- |
| `GenerateRequestsPerMinutePerProjectPerModel-FreeTier` | 5 requests per minute |
| `GenerateRequestsPerDayPerProjectPerModel-FreeTier` | **20 requests per day** |

- Requests to `gemini-3.5-flash` are counted under `model=gemini-3.6-flash`.
- The first `retryDelay` was 1 s, the next 429 said 58 s; `--wait-retry` retries 3 times.
- 503 "high demand" happened once in 10 requests; it is not a quota error.
- Latency through the local network/proxy: 1.4–26 s per request (median about 5 s).
- Image with `mediaResolution=LOW`: 266 tokens. Thinking tokens: 0 at `minimal`.

20 requests per day is too few for the evaluation set and demos. Limits are per model,
so Flash-Lite models have their own quota; check them in AI Studio before testing.

### Survey of every chat model on 2026-10-28

`survey` runs a burst on each model in turn and writes one summary row per model:

```bash
python -m src.ai.gemini_rate_limit survey --csv ai_data/survey.csv --models gemini-3.5-flash-lite gemma-4-26b-a4b-it
```

Tested: the 18 Gemini and 2 Gemma models that support `generateContent`. TTS, image,
music, transcription, robotics, computer-use and agent models were left out. Burst of
up to 15 requests per model (35 for Gemma).

| Model | Result | Limit in Google's 429 answer | Quota counted as |
| --- | --- | --- | --- |
| `gemini-3.5-flash-lite` | 15 of 15 OK, median 1.0 s | none reached | — |
| `gemini-3.1-flash-lite`, `gemini-3.1-flash-lite-preview` | 15 of 15 OK each, median 3.7–4.0 s | none reached | — |
| `gemini-flash-lite-latest` | 15 of 15 OK, median 0.9 s | none reached | — |
| `gemini-3.5-flash`, `gemini-3.6-flash` | 429 per minute | 5 per minute, 20 per day | `gemini-3.6-flash` |
| `gemini-3.8-flash`, `gemini-3.7-flash`, `gemini-flash-latest` | 503 and timeouts, then 429 per day | 20 per day | `gemini-3.8-flash` |
| `gemini-3-flash-preview` | 429 per minute | 5 per minute | `gemini-3-flash` |
| `gemma-4-26b-a4b-it` | 15 OK, median 1.1 s, then 429 | 30 per minute | `gemma-4-26b` |
| `gemma-4-31b-it` | HTTP 500 "Internal error" | — | — |
| `gemini-3.1-pro-preview`, `gemini-pro-latest`, `gemini-omni-flash-preview`, `gemini-omni-1.1-flash`, `gemini-4-argon` | 429 on the first request, retry in about 22.8 h, no limit value | no free quota (inferred) | `gemini-3.1-pro`, `gemini-omni-1.1-flash`, `gemini-4-argon` |
| `gemini-2.5-flash`, `gemini-2.5-flash-lite`, `gemini-2.5-pro` | 404 "no longer available to new users" | — | — |

- Several names share one quota: 3.5 Flash with 3.6 Flash, and 3.7 Flash and
  `gemini-flash-latest` with 3.8 Flash. A chain that lists both gains nothing.
- No Flash-Lite model returned a 429. Calls are sequential, so the lower bound depends
  on speed: 3.5 Flash-Lite and `flash-lite-latest` did 15 calls in about 15 s (at least
  15 per minute); 3.1 Flash-Lite needed 82 s (at least 11 in one minute) and its preview
  73 s (at least 14). Their daily limits are still unknown; finding them needs a paced
  run over the day.
- `limit=` is the `quotaValue` in Google's 429 answer. For the Pro, Omni and
  `gemini-4-argon` models it was empty, so "no free quota" is inferred from the block on
  the first call.
- `gemini-3.7-flash` rejects `thinkingLevel: minimal`; the survey resends without it.
- By mistake a second copy of the survey ran at the same time, so request counts and
  latencies are higher than one run alone. The limits come from Google's own 429
  answers and do not depend on that.

## Backup models and reuse (standalone)

`suggest.py` runs one request the way the backend should later: reuse first, then
the providers in order. It is not connected to the backend yet; that waits for the
refactor branch to be merged.

```bash
python -m src.ai.suggest --symbols water --scene "A café" --photo
```

```bash
python -m src.ai.suggest --symbols coffee --intention "I do not want sugar" --accept 1
```

```bash
python -m src.ai.suggest --status
```

`--status` makes no calls. It shows each provider's count for today against the
local cap and any cooldown.

### Provider order

Default: `gemini-3.5-flash-lite` → `gemini-3.1-flash-lite` → `gemini-3.5-flash` →
`gemini-3.8-flash` → `ollama:qwen3-vl:2b`. Change it with `--order` or
`AI_PROVIDER_ORDER` in `.env`, as a comma list of `kind:model` (`gemini`, `ollama`,
`zai`).

- Free quotas count per model, so each Gemini model adds its own daily requests on
  the same key. The Flash-Lite limits were not measured (only one or two calls each
  on 2026-10-28); check them in AI Studio.
- A local cap stops each hosted model at 16 calls a day (80 % of the 20 measured for
  3.5 Flash). Change it with `--daily-cap`. Failed calls count too.
- A 429 is not retried. The model cools down for the retry delay in the answer, or
  until the next quota day (midnight Pacific time) for a daily quota, and the next
  provider is used at once.
- Three failures in a row (timeout, 5xx, no connection) pause a provider for 5
  minutes. No new attempt starts after `--budget` seconds (default 240).
- If every provider fails the script says so. It never falls back to the mock
  templates.
- `zai:glm-4.6v-flash` needs `ZAI_API_KEY` in `.env`. That adapter is tested offline
  only (no key yet).
- Ollama: install it, then `ollama pull qwen3-vl:2b`. The first call loads the model
  and can take minutes on this laptop's CPU. Close other apps first (about 3 GB free
  RAM needed). Not measured yet.

Counts and cooldowns are kept in `ai_data/usage.json`, so separate runs share them.

### Reuse and examples (retrieval)

Accepted sentences go to `ai_data/accepted.jsonl` (`--accept N`, or the prompt after
the suggestions). Before calling a model the script scores the request against them:

| Field | Weight | Comparison |
| --- | --- | --- |
| Symbols | 0.5 | Same set, any order or case |
| Words of symbols and intention | 0.3 | Word overlap, common words such as "please" ignored |
| Scene hint | 0.2 | Word overlap |

- Score 0.9 or more: the stored sentences are shown with **no AI call**. Off when a
  photo is attached, because the photo may show another place (same rule as the
  backend lookup).
- Score 0.4 or more: up to three sentences are sent to the model as `examples`, so it
  can follow the person's wording. They cost about 15–40 prompt tokens and no extra
  request.
- A negated wish never matches a plain one ("no sugar" vs "sugar").

This is word overlap, not embeddings, so "glass of water" and "something to drink"
do not match. Embeddings would need a model or another quota. The store has no user
ownership: keep it synthetic and do not commit it.

The backend endpoint `POST /api/suggestions/reuse` (refactor branch) only finds exact
matches. The plan is to move this scoring into `app/services/reuse.py` once that
branch is on `main`.

### Live check on 2026-10-28

| Request | Provider | Result |
| --- | --- | --- |
| Photo + "water", café | `gemini-3.5-flash-lite`, 4.3 s, 406 prompt tokens | 1 sentence with the old "up to three" prompt |
| Coffee + "I do not want sugar" + photo | `gemini-3.5-flash-lite`, 5.5 s, 413 prompt tokens | 3 sentences, negation kept, after the prompt asked for three |
| Same "water" request, text only | none | Reused from `accepted.jsonl`, no call |
| Photo + "water", Ollama first | Ollama "cannot connect" → `gemini-3.1-flash-lite`, 6.2 s | 3 sentences |

## Offline tests

```bash
python -m pytest -q tests/test_gemini_scripts.py tests/test_ai_chain.py tests/test_ai_retrieval.py
```

These use a mock transport: no network and no key, so they also run in CI.
