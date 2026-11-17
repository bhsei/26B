# AI Part: Remaining Work Plan

Context-aware AAC Board · Team B - The Outliers  
Owner: Jiahui Chen · Draft 0.1 · 2026-11-03 (week 8) · Status: proposal for team review

This plan lists what the AI part still needs from week 8 to the launch in week 16.
It builds on the [AI model plan](AI_Model_Plan.md) and the
[evaluation plan](../testing/AI_Evaluation_Plan.md). Changes outside `src/ai/` are
listed in section 6 as coordination items for their owners. This plan does not make
them.

## 1. Where the AI part stands (checked 2026-11-03)

| Area | State | Evidence |
| --- | --- | --- |
| Backend provider | Mock only (`AI_PROVIDER=mock`, the only allowed value) | `app/config.py`, `app/main.py` |
| Hosted providers | Gemini, Ollama and OpenAI-style adapters in the standalone prototype | `src/ai/providers.py` |
| Fallback chain | Ordered models, per-model daily cap 16, cooldown on 429, pause after 3 failures, no mock fallback | `src/ai/chain.py` |
| Reuse and examples | Similarity reuse (0.9) and wording examples (0.4) in the prototype; exact reuse endpoint in the backend | `src/ai/retrieval.py`, `docs/REUSE.md` |
| Tests | 108 pass on `main` today; the AI prototype has offline tests with a mock transport | `pytest -q` run on 2026-11-03 |
| Live checks | 3 cases on 21 Oct and the café request on 28 Oct; survey of 20 models on 28 Oct | `src/ai/README.md` |
| Evaluation set | 80 synthetic cases written today, not run yet | `tests/ai_eval/cases.json` |
| Local model | **Not usable now.** Ollama is not installed; 0.79 GB of 7.34 GB RAM free with normal apps open | measured 2026-11-03 |
| Second vendor (Z.ai) | Adapter written, never called (no key) | `OpenAICompatibleProvider` |

Measured Gemini free-tier facts (survey of 2026-10-28):

- `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite` and `gemini-flash-lite-latest`
  answered 15 of 15 calls with no 429. Their daily limits are still unknown.
- `gemini-3.5-flash` allows 5 per minute and 20 per day. `gemini-3.8-flash` allows
  20 per day and was overloaded.
- `gemma-4-26b-a4b-it` allows 30 per minute; its daily limit and whether it takes
  images through this API were not checked.
- Pro, Omni and `gemini-4-argon` had no free quota. All 2.5 models return 404 for new keys.

## 2. Review commitments that fall on the AI part

All 23 findings of Issues #2 (Team A) and #3 (Group F) have a reply on GitHub. These
replies promise AI work:

| Finding | Replied by (GitHub) | Promise | Work package |
| --- | --- | --- | --- |
| A1, F7 | ghatuwu, thibz1009 | Exact matching as the baseline; prototype thresholds kept out until validated; cases for negation, quantities, times | WP7 |
| A3, F6 | thibz1009 | Reuse history and wording examples only with synthetic data, never in a multi-user deployment before ownership exists | WP7 |
| A4 | Jiahuiche | Provider allow-list per environment; check the provider is reachable from the demo network | WP4, WP6 |
| A5, F4 | ghatuwu | One overall deadline for all attempts; decide whether the local model fits inside it; deadline ends in 503 | WP3 |
| A6, F5 | ghatuwu | Capacity target; non-AI path (speak typed text); provider exhaustion tests | WP3, WP5 |
| A7, F1 | Jiahuiche | Set of at least 32 cases, 2 raters + 1, thresholds 90 % / 2.5 / 0 / 0 / 0 | WP1, WP2 |
| A9 | ghatuwu | Small latency samples reported with size, median and maximum | WP2 |
| A10 | ghatuwu | Output rules (300 characters, repeats, malformed output, negation) as numbered requirements | WP1, WP8 |

## 3. Work packages

Weeks follow the course calendar (week 7 began on 2026-10-26). Course milestones:
detailed design in week 12, launch in week 16.

### WP1 · Provider fixes needed by the evaluation (W8)

1. Keep the raw model sentences and the reasons for every dropped sentence in `Result`.
2. Make the chain safe for parallel requests. The backend runs normal endpoints in a
   thread pool, and `UsageStore` and the failure counters are changed without a lock.
3. Move `to_jpeg_384` and the drawn café photo out of the quickstart script into a
   shared module, so the backend adapter and the evaluation use the same code.
4. Offline tests for each change.

Done when the tests pass and a dry run of the evaluation records raw and filtered output.

### WP2 · Evaluation tooling and runs (W8–W10)

1. `eval_photos.py`, `evaluate.py` and `score.py` as described in the evaluation plan,
   section 4.
2. Read the Flash-Lite daily limits in AI Studio (no quota used) and set the caps.
3. Core run (37 calls) on `gemini-3.5-flash-lite` and `gemini-3.1-flash-lite`, plus the
   second-vendor candidate if one is reachable (WP4).
4. Blind rating, adjudication, report in `docs/testing/AI_Evaluation_Report.md`.
5. Full run (88 calls) on the chosen model in W10.

Done when the report closes Appendix B item 3 (provider order and thresholds).

### WP3 · Timing contract and degraded behaviour (W8–W9, with Veronika and Thibaut)

Proposal for Appendix B item 4. The numbers are to be confirmed with the W9 latencies.

| Value | Proposal | Reason |
| --- | --- | --- |
| Overall deadline per generation | 20 s, all attempts included | Flash-Lite generations took 1.7–6.2 s on 28 Oct; leaves room for one fallback |
| Per attempt | at most 10 s, and never more than the time left | One slow model cannot use the whole budget |
| Deadline reached | HTTP 503 `PROVIDER_UNAVAILABLE` | Already in the reply to Team A finding 5 |
| Local model | Not in the live chain; only in an offline demo mode with its own limit | Its first call loads the model on the CPU; the current read timeout is 180 s |
| `suggest.py` budget | 240 s today, lowered to the deadline | Same rule in the script and the backend |

The non-AI path (speak the typed text, labelled as not AI) is a frontend feature. The
AI part provides the clear 503 and adds the exhaustion case to L3 tests.

### WP4 · Second vendor and fallback strategies (W8–W11)

See section 4. In short: confirm one hosted model from a second company, keep the
local model as an optional offline mode, and never fall back to templates presented as AI.

### WP5 · Backend integration (W9–W10, with Veronika)

1. New module in `app/providers/` that maps `SuggestionInput` to the prototype
   `Request` (symbols, intention, scene hint, `excluded` as `avoid`), resizes the
   sanitized JPEG to 384 px, and turns "all providers failed" or "deadline reached" into
   `ProviderUnavailable`.
2. Offline tests through `create_app(settings, provider)` with a mock HTTP transport:
   429 moves on, timeout gives 503, malformed output gives an empty list or 502,
   negation drop, `image_analyzed` truthful, all providers down gives 503.
3. Coordination items of section 6 (configuration, dependency, recorded model name).

Done when the café scenario runs through the backend with the real chain and the L1
suite passes in CI without a key.

### WP6 · Configuration and data protection (W10, with Abid)

1. Model order, caps, deadline and the usage file path in configuration, not in code.
2. Provider allow-list per environment, checked at start (reply to Team A finding 4).
3. The usage file on persistent storage in the deployed container, so daily counts
   survive a restart.
4. Connectivity check of each hosted provider from the demo network.

### WP7 · Reuse decision support (W8–W9, with Veronika)

1. Reuse acceptance pairs (evaluation plan, section 10) for the exact baseline.
2. Keep similarity reuse and examples off in the backend until they are validated
   with the same pairs; examples only with synthetic data.

### WP8 · SRS and design documents (W9, W12)

1. AI parts of SRS v1.0 in W9: model order, thresholds, timing values, output rules
   (Team A finding 10), evaluation set reference in REQ-ML-002.
2. AI chapter of the detailed design in W12: provider module, chain, prompt, data
   flow, failure table, evaluation results.

### WP9 · Regression and launch preparation (W13–W16)

1. Extended-place results for REQ-FUNC-011 (W13–W14).
2. Freeze prompt and model order in W15, run the full set once more.
3. Launch checklist for W16: quota status (`suggest.py --status`), no evaluation runs
   the day before, connectivity check, fallback order confirmed, 503 path shown once.

## 4. If the model does not load: inference strategies

"Does not load" covers two cases: the local model cannot start (memory, not
installed), or a hosted model is unreachable, retired or out of quota. The chain
already moves to the next entry in both cases. The question is what the next entries
should be. Options are ordered from least to most effort.

### 4.1 Hosted, no local load (first choice)

| Option | Status | Notes |
| --- | --- | --- |
| Several Gemini Flash-Lite models on one key | **Measured** | Each model has its own quota; aliases share one (do not list both `3.5-flash` and `3.6-flash`) |
| `gemma-4-26b-a4b-it` on the same key | Limit measured (30 RPM); image input not checked | One test call decides whether it is a photo backup or a text-only backup |
| Text-only retry | No new code needed beyond a flag | If a photo call fails, the same model can be asked without the photo; `image_analyzed=false` is then shown truthfully |

### 4.2 Hosted, second company

Every value below comes from secondary sources and must be read in the vendor's own
console before use. None of them has been called by us.

| Option | Reported free terms | Fit | Code |
| --- | --- | --- | --- |
| Z.ai GLM-4.6V-Flash | Free; 1 concurrent request reported | Vision; Chinese provider, likely reachable in China | Adapter exists (`zai:` in the order) |
| OpenRouter `:free` models | 20 per minute, 50 per day without bought credits | Too few for evaluation; usable as a last hosted step | OpenAI-style, existing adapter |
| Cloudflare Workers AI | 10,000 "neurons" per day (official pricing page); cost of a vision call unknown | Possible backup | Different API, new adapter |
| Mistral free plan | Requires opting in to training on inputs; limits not published in the sources found | Synthetic data only | OpenAI-style |
| Groq | Free tier exists; free vision models unclear | Check the console | OpenAI-style |
| Hugging Face Inference Providers | About $0.10 credit per month for free accounts | Too small | Not considered |

### 4.3 Local, lighter than Ollama with a 2B vision model

| Option | Memory | Notes |
| --- | --- | --- |
| Free memory first | — | The 0.79 GB was measured with normal apps open. Closing the browser and other apps and measuring again is the first step before any local trial |
| `llama.cpp` server instead of Ollama | Model size plus a small context | Serves an OpenAI-style endpoint, so the existing `OpenAICompatibleProvider` works with a local URL. Supports a vision projector file on the CPU. Model repository name to confirm |
| Small text-only model (`qwen3:0.6b` about 523 MB, `gemma3:1b` about 815 MB) | Fits the measured free memory better (sizes from secondary sources) | No photo (`image_analyzed=false`). English quality must pass the text-only core cases before use |
| `qwen3-vl:2b` (1.9 GB at Q4, AI model plan) | About 3 GB free needed (estimate) | Only with apps closed or on another machine |

Rule from the AI model plan (F-01): check free memory before trying the local model,
and skip it when it is below the measured need. Ollama's out-of-memory answer is
already turned into "unavailable" by the adapter.

### 4.4 Local model on another machine

A team member's laptop with more free RAM runs Ollama or `llama.cpp` on the local
network, and `OLLAMA_URL` points to it. No code change is needed. The server must be
reachable only on the local network, never from the internet.

### 4.5 Free GPU notebooks, for evaluation only

Kaggle notebooks offer free GPU time (about 30 hours a week according to secondary
sources). They suit an offline evaluation of open models: the case file and the drawn
photos are uploaded, the model runs inside the notebook, and the JSONL output is
downloaded. Sessions end after some hours, so they are not a live backend for the demo.

### 4.6 When nothing answers

Keep the controlled 503. The user keeps communicating through the non-AI path
(reply to Group F finding 5) and through exact reuse of accepted sentences for text
requests. Mock templates are never shown as an AI answer (REQ-ML-006).

### 4.7 Recommended order

1. Now: `gemini-3.5-flash-lite` → `gemini-3.1-flash-lite` → `gemma-4-26b-a4b-it`
   (if it takes images, else text-only) → `gemini-3.5-flash` → 503.
2. After WP4: add the second-company model after the first two Flash-Lite models.
3. Local model: only as an offline demo mode, on a machine with enough free memory.

## 5. Capacity (reply to Team A finding 6)

The target cannot be fixed before the Flash-Lite daily limits are known. The
calculation the team will use:

- Attempts available per day = sum of the local caps of the hosted models in the chain.
- Attempts needed per day = generations × (1 + regenerations per generation) ×
  (1 + share of failed attempts) + evaluation calls of that day.
- The demo day needs attempts available ≥ 2 × attempts needed.

Example with the one limit measured so far: a chain with only `gemini-3.5-flash` gives
16 attempts per day, which is not enough for the core evaluation (37 calls) in one day.

## 6. Coordination items outside the AI folder

Not changed by this plan. Each needs its owner's agreement and its own commit.

| File or area | Change needed for the AI part | Owner |
| --- | --- | --- |
| `app/config.py`, `.env.example` | New provider value and settings: order, caps, deadline, usage file, allowed providers | Veronika |
| `app/main.py` | Choose the provider from the setting | Veronika |
| `requirements.txt` | `httpx` becomes a runtime dependency (today only in the dev list) | Veronika |
| `app/services/suggestions.py`, models, migration | Store the model that actually answered and the prompt version; today the stored name is the static provider name | Veronika |
| Notice text | Notice for real AI answers (REQ-ML-004) | Veronika, Thibaut |
| Frontend | Waiting state, no double submission, 503 notice, speak typed text, speak then save | Thibaut |
| Deployment | API key as a secret, persistent usage file, provider allow-list, network check | Abid |

## 7. Risks

| Risk | Plan |
| --- | --- |
| Flash-Lite daily limits are low | Read them first (WP2); second vendor (WP4); reuse |
| Gemini unreachable from the demo network | Connectivity check (WP6); second company in the chain |
| Free models renamed or retired before W16 | Model IDs in configuration; rerun the core set after any change |
| The negation post-check drops correct sentences | Measured by M11; kept strict unless the data shows a real cost |
| Raters disagree | Kappa check and rubric discussion (evaluation plan 6.2) |
| Not enough time for the extended places | Core set first; extended places stay "Could" (reply to Group F finding 3) |

## 8. Questions for the team

1. Will the demo and any trial run from a network in mainland China?
2. Does any team member have a laptop with at least 8 GB free RAM for a local model?
3. Who rates the evaluation (proposal: Veronika and Thibaut, Abid settles)?
4. Which symbol labels does the frontend use for school, bus, medical visit, shop and home?
5. Are the 20 s deadline and the 10 s per-attempt limit acceptable as provisional values?

## 9. Sources (searched 2026-11-03)

Official pages:

- Cloudflare Workers AI pricing: https://developers.cloudflare.com/workers-ai/platform/pricing/
- Hugging Face Inference Providers pricing: https://huggingface.co/docs/inference-providers/pricing
- llama.cpp multimodal support: https://github.com/ggml-org/llama.cpp/blob/master/docs/multimodal.md

Secondary sources (to verify in each vendor's console):

- GLM-4.6V-Flash free tier: https://www.ayautomate.com/free-models/z-ai-zhipu-ai-glm-4-6v-flash
- OpenRouter free model limits: https://benchlm.ai/md/free-tier/openrouter.md
- Mistral free tier: https://benchlm.ai/md/free-tier/mistral.md
- Groq free tier: https://pricepertoken.com/endpoints/groq/free
- Ollama model sizes: https://needtoknowit.com.au/blog/best-ollama-models-to-download.md
- Kaggle GPU quota: https://blog.paperspace.com/gradient-kaggle-notebook-comparison/

The sources of the AI model plan (section 10) still apply.
