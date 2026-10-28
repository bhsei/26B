import json

import httpx
import pytest

from src.ai.chain import AllProvidersFailed, Entry, ProviderChain, UsageStore, next_quota_day
from src.ai.providers import (
    GeminiProvider,
    OllamaProvider,
    OpenAICompatibleProvider,
    RateLimited,
    Request,
    Result,
    Unavailable,
    clean_sentences,
    sentences_from_text,
)

DAILY_429 = json.dumps(
    {
        "error": {
            "code": 429,
            "status": "RESOURCE_EXHAUSTED",
            "details": [
                {
                    "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                    "violations": [
                        {"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}
                    ],
                },
                {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "40s"},
            ],
        }
    }
)


def gemini_answer(sentences):
    text = json.dumps({"sentences": sentences})
    return {
        "candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}],
        "usageMetadata": {"promptTokenCount": 150, "candidatesTokenCount": 30},
    }


def gemini(handler, model="gemini-3.5-flash-lite"):
    return GeminiProvider(model, "fake-key", transport=httpx.MockTransport(handler))


class Fake:
    def __init__(self, name, outcomes):
        self.name = name
        self.outcomes = list(outcomes)
        self.calls = 0

    def generate(self, request):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return Result(outcome, False, self.name)


class Clock:
    def __init__(self, now=1_800_000_000.0):
        self.now = now

    def __call__(self):
        return self.now


def test_gemini_request_has_json_fields_low_resolution_and_examples():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=gemini_answer(["Water, please."]))

    request = Request(
        ["water"], scene_hint="A café", jpeg=b"\xff\xd8jpeg", examples=["Water, please."]
    )
    result = gemini(handler).generate(request)
    body = seen["body"]
    data = json.loads(body["contents"][0]["parts"][0]["text"])
    assert data["examples"] == ["Water, please."] and data["symbols"] == ["water"]
    assert "examples" in body["systemInstruction"]["parts"][0]["text"]
    assert body["generationConfig"]["mediaResolution"] == "MEDIA_RESOLUTION_LOW"
    assert result.sentences == ["Water, please."] and result.image_analyzed


def test_gemini_daily_quota_is_rate_limited_and_daily():
    provider = gemini(lambda r: httpx.Response(429, text=DAILY_429))
    with pytest.raises(RateLimited) as error:
        provider.generate(Request(["water"]))
    assert error.value.daily and error.value.retry_after_s == 40.0


def test_gemini_timeout_becomes_unavailable_without_details():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(Unavailable, match="timed out"):
        gemini(handler).generate(Request(["water"]))


def test_ollama_missing_model_and_no_server():
    missing = OllamaProvider(
        "qwen3-vl:2b", transport=httpx.MockTransport(lambda r: httpx.Response(404))
    )
    with pytest.raises(Unavailable, match="ollama pull qwen3-vl:2b"):
        missing.generate(Request(["water"]))

    def refused(request):
        raise httpx.ConnectError("refused", request=request)

    down = OllamaProvider("qwen3-vl:2b", transport=httpx.MockTransport(refused))
    with pytest.raises(Unavailable, match="cannot connect"):
        down.generate(Request(["water"]))


def test_ollama_sends_image_and_retries_without_think_field():
    bodies = []

    def handler(request):
        body = json.loads(request.content)
        bodies.append(body)
        if "think" in body:
            return httpx.Response(400, json={"error": "model does not support thinking"})
        content = 'Sure: {"sentences": ["Could I have some water?"]}'
        return httpx.Response(200, json={"message": {"content": content}, "eval_count": 9})

    provider = OllamaProvider("qwen3-vl:2b", transport=httpx.MockTransport(handler))
    result = provider.generate(Request(["water"], jpeg=b"\xff\xd8jpeg"))
    assert result.sentences == ["Could I have some water?"] and result.image_analyzed
    assert len(bodies) == 2 and bodies[1]["messages"][1]["images"]
    provider.generate(Request(["water"]))
    assert len(bodies) == 3  # the switch is remembered


def test_openai_compatible_rate_limit_uses_retry_after():
    provider = OpenAICompatibleProvider(
        "zai",
        "https://example.test/v4",
        "glm-4.6v-flash",
        "fake-key",
        transport=httpx.MockTransport(lambda r: httpx.Response(429, headers={"retry-after": "12"})),
    )
    with pytest.raises(RateLimited) as error:
        provider.generate(Request(["water"]))
    assert error.value.retry_after_s == 12.0 and not error.value.daily


def test_clean_sentences_keeps_negation_and_drops_repeats():
    request = Request(["coffee"], intention="I do not want sugar", avoid=["Coffee without sugar."])
    raw = [
        "Coffee with sugar, please.",
        "No sugar in my coffee, please.",
        "coffee without sugar.",
        "",
        "x" * 301,
        "I don't want sugar.",
        "Never sugar.",
    ]
    assert clean_sentences(request, raw) == [
        "No sugar in my coffee, please.",
        "I don't want sugar.",
        "Never sugar.",
    ]


def test_sentences_from_text_tolerates_extra_text_and_bad_json():
    assert sentences_from_text('Here: {"sentences": ["A.", 3]} done') == ["A."]
    assert sentences_from_text("not json") == []


def test_chain_falls_back_and_cools_down_on_per_minute_quota(tmp_path):
    clock = Clock()
    first = Fake("a", [RateLimited("a: per-minute quota", retry_after_s=30)])
    second = Fake("b", [["Water, please."], ["Water, please."]])
    chain = ProviderChain(
        [Entry(first, 16), Entry(second, 16)], UsageStore(tmp_path / "u.json"), clock=clock
    )
    outcome = chain.generate(Request(["water"]))
    assert outcome.result.provider == "b"
    assert [a.outcome for a in outcome.attempts] == ["a: per-minute quota", "ok"]
    outcome = chain.generate(Request(["water"]))
    assert first.calls == 1 and outcome.attempts[0].outcome.startswith("skipped: quota cooldown")
    clock.now += 31
    assert chain.skip_reason(chain.entries[0], clock.now) == ""


def test_chain_daily_quota_waits_for_next_quota_day_across_runs(tmp_path):
    clock = Clock()
    path = tmp_path / "u.json"
    chain = ProviderChain(
        [
            Entry(Fake("a", [RateLimited("daily", daily=True)]), 16),
            Entry(Fake("b", [["Hi."]]), None),
        ],
        UsageStore(path),
        clock=clock,
    )
    chain.generate(Request(["water"]))
    # A new process reads the same file and still skips "a".
    again = ProviderChain([Entry(Fake("a", []), 16)], UsageStore(path), clock=clock)
    assert "cooldown" in again.skip_reason(again.entries[0], clock.now)
    assert again.skip_reason(again.entries[0], next_quota_day(clock.now) + 1) == ""


def test_chain_local_cap_counts_failed_calls_and_resets_next_day(tmp_path):
    clock = Clock()
    provider = Fake("a", [Unavailable("a: HTTP 503"), ["One."], ["Two."]])
    chain = ProviderChain([Entry(provider, 2)], UsageStore(tmp_path / "u.json"), clock=clock)
    with pytest.raises(AllProvidersFailed):
        chain.generate(Request(["water"]))
    chain.generate(Request(["water"]))
    with pytest.raises(AllProvidersFailed) as error:
        chain.generate(Request(["water"]))
    assert "daily cap 2" in error.value.attempts[0].outcome and provider.calls == 2
    clock.now = next_quota_day(clock.now) + 1
    assert chain.generate(Request(["water"])).result.sentences == ["Two."]


def test_chain_pauses_provider_after_three_failures(tmp_path):
    clock = Clock()
    broken = Fake("a", [Unavailable("a: down")] * 3)
    backup = Fake("b", [["Ok."]] * 4)
    chain = ProviderChain([Entry(broken, None), Entry(backup, None)], UsageStore(None), clock=clock)
    for _ in range(4):
        chain.generate(Request(["water"]))
    assert broken.calls == 3 and backup.calls == 4


def test_chain_all_down_raises_and_never_uses_mock(tmp_path):
    chain = ProviderChain(
        [Entry(Fake("a", [Unavailable("a: down")]), None)], UsageStore(None), clock=Clock()
    )
    with pytest.raises(AllProvidersFailed) as error:
        chain.generate(Request(["water"]))
    assert error.value.attempts[0].outcome == "a: down"


def test_empty_answer_is_a_result_not_a_reason_to_spend_more_quota(tmp_path):
    first = Fake("a", [[]])
    second = Fake("b", [["Unused."]])
    chain = ProviderChain(
        [Entry(first, None), Entry(second, None)], UsageStore(None), clock=Clock()
    )
    assert chain.generate(Request(["water"])).result.sentences == [] and second.calls == 0
