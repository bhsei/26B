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

## Offline tests

```bash
python -m pytest -q tests/test_gemini_scripts.py
```

These use a mock transport: no network and no key, so they also run in CI.
