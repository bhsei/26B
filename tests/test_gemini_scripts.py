import base64
import json
from argparse import Namespace

import httpx

from src.ai import gemini_quickstart, gemini_rate_limit
from src.ai.gemini_common import (
    build_body,
    load_api_key,
    make_client,
    parse_error,
    parse_sentences,
    save_records,
    thinking_config,
)

RATE_LIMITED = json.dumps(
    {
        "error": {
            "code": 429,
            "status": "RESOURCE_EXHAUSTED",
            "message": "You exceeded your current quota.",
            "details": [
                {
                    "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                    "violations": [
                        {
                            "quotaMetric": "generate_content_free_tier_requests",
                            "quotaId": "GenerateRequestsPerMinutePerProjectPerModel-FreeTier",
                            "quotaDimensions": {"model": "gemini-2.5-flash"},
                            "quotaValue": "10",
                        }
                    ],
                },
                {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "37s"},
            ],
        }
    }
)


def test_parse_rate_limit_error():
    error = parse_error(429, RATE_LIMITED)
    assert error.api_status == "RESOURCE_EXHAUSTED"
    assert error.violations[0]["quotaValue"] == "10"
    assert error.retry_delay_s == 37.0
    assert not error.is_daily


def test_parse_non_json_error():
    error = parse_error(502, "<html>Bad gateway</html>")
    assert error.status == 502 and error.violations == []


def test_key_from_env_file(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text('AI_PROVIDER=mock\nGEMINI_API_KEY="fake-key"\n', encoding="utf-8")
    assert load_api_key(env) == "fake-key"


def test_key_is_sent_in_header_not_url():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["header"] = request.headers.get("x-goog-api-key")
        return httpx.Response(200, json={})

    client = make_client("fake-key", transport=httpx.MockTransport(handler))
    client.get("/models/gemini-2.5-flash")
    assert seen["header"] == "fake-key"
    assert "fake-key" not in seen["url"]


def test_saved_generations_have_results_but_no_key_or_image(tmp_path):
    answer = {
        "candidates": [
            {
                "content": {"parts": [{"text": json.dumps({"sentences": ["Water, please."]})}]},
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 412,
            "candidatesTokenCount": 36,
            "totalTokenCount": 448,
            "promptTokensDetails": [{"modality": "IMAGE", "tokenCount": 266}],
        },
    }
    responses = iter([httpx.Response(200, json=answer), httpx.Response(429, text=RATE_LIMITED)])
    client = make_client("fake-key", transport=httpx.MockTransport(lambda r: next(responses)))
    jpeg = gemini_quickstart.to_jpeg_384(gemini_quickstart.synthetic_cafe_photo())
    case = gemini_quickstart.CASES[1]
    records = [
        gemini_quickstart.run_case(client, "gemini-3.5-flash", case, jpeg, {}, "cafe.jpg")
        for _ in range(2)
    ]
    path = tmp_path / "out" / "generations.jsonl"
    save_records(path, records)
    save_records(path, records[:1])  # appends, does not overwrite

    text = path.read_text(encoding="utf-8")
    lines = [json.loads(line) for line in text.splitlines()]
    assert len(lines) == 3
    assert lines[0]["sentences"] == ["Water, please."]
    assert lines[0]["usage"]["prompt_by_modality"] == {"IMAGE": 266}
    assert lines[0]["input"]["symbols"] == ["water"] and lines[0]["image"] == "cafe.jpg"
    assert lines[1]["status"] == 429 and lines[1]["sentences"] == []
    assert "FreeTier" in lines[1]["error"]["quota"][0]
    assert "fake-key" not in text
    assert base64.b64encode(jpeg).decode()[:40] not in text


def test_lowest_thinking_per_model():
    assert thinking_config("gemini-2.5-flash") == {"thinkingBudget": 0}
    assert thinking_config("gemini-3.5-flash") == {"thinkingLevel": "minimal"}
    assert thinking_config("gemini-3.8-flash") == {"thinkingLevel": "low"}
    assert thinking_config("gemini-3.5-flash", "high") == {"thinkingLevel": "high"}


def test_body_requests_json_low_thinking_and_low_media_resolution():
    body = build_body(
        [{"text": "hi"}],
        system="rules",
        json_output=True,
        thinking=thinking_config("gemini-3.5-flash"),
        low_media_resolution=True,
    )
    config = body["generationConfig"]
    assert config["thinkingConfig"] == {"thinkingLevel": "minimal"}
    assert config["mediaResolution"] == "MEDIA_RESOLUTION_LOW"
    assert config["responseMimeType"] == "application/json"
    assert body["systemInstruction"]["parts"][0]["text"] == "rules"


def test_burst_continues_after_overload(capsys):
    statuses = iter([503, 200, 429])

    def handler(request):
        status = next(statuses)
        body = RATE_LIMITED if status == 429 else '{"error": {"status": "UNAVAILABLE"}}'
        return httpx.Response(status, text=body if status != 200 else "{}")

    client = make_client("fake-key", transport=httpx.MockTransport(handler))
    args = Namespace(model="gemini-3.5-flash", max_requests=15, wait_retry=False)
    recorder = gemini_rate_limit.Recorder(None)
    assert gemini_rate_limit.burst(client, args, recorder) == 0
    assert recorder.ok_count() == 1 and len(recorder.rows) == 3
    assert "overloaded" in capsys.readouterr().out


def test_parse_sentences_limits_and_tolerates_bad_json():
    text = json.dumps({"sentences": ["A.", " ", "B.", "C.", "D."]})
    data = {"candidates": [{"content": {"parts": [{"text": text}]}}]}
    assert parse_sentences(data) == ["A.", "B.", "C."]
    bad = {"candidates": [{"content": {"parts": [{"text": "not json"}]}}]}
    assert parse_sentences(bad) == []


def test_burst_stops_at_first_429(capsys):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] <= 3:
            return httpx.Response(200, json={"usageMetadata": {"totalTokenCount": 9}})
        return httpx.Response(429, text=RATE_LIMITED)

    client = make_client("fake-key", transport=httpx.MockTransport(handler))
    args = Namespace(model="gemini-2.5-flash", max_requests=15, wait_retry=False)
    recorder = gemini_rate_limit.Recorder(None)
    assert gemini_rate_limit.burst(client, args, recorder) == 0
    assert calls["n"] == 4 and recorder.ok_count() == 3
    out = capsys.readouterr().out
    assert "limit=10" in out and "retry after: 37.0 s" in out
