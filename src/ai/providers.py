"""Sentence providers for the standalone AI prototype (not used by the backend yet).

Each provider makes one call per request and returns at most three cleaned sentences.
Failures become RateLimited (quota, try another provider) or Unavailable (network,
model missing, upstream error). Messages never contain keys, photos or user text.
"""

import base64
import json
import re
from dataclasses import dataclass, field
from time import perf_counter

import httpx

from src.ai.gemini_common import (
    EXAMPLES_RULE,
    JSON_RULE,
    SYSTEM_PROMPT,
    build_body,
    generate,
    make_client,
    parse_error,
    parse_sentences,
    thinking_config,
)

MAX_SENTENCE_CHARS = 300
NEGATION = re.compile(r"\b(not|no|never|without|none)\b|n't\b", re.IGNORECASE)


@dataclass
class Request:
    symbols: list[str]
    intention: str = ""
    scene_hint: str = ""
    avoid: list[str] = field(default_factory=list)
    jpeg: bytes | None = None
    examples: list[str] = field(default_factory=list)


@dataclass
class Result:
    sentences: list[str]
    image_analyzed: bool
    provider: str = ""
    latency_s: float = 0.0
    usage: dict = field(default_factory=dict)


class ProviderError(Exception):
    """Base class; the message is safe to print (status codes and short reasons only)."""


class RateLimited(ProviderError):
    def __init__(self, message: str, retry_after_s: float | None = None, daily: bool = False):
        super().__init__(message)
        self.retry_after_s = retry_after_s
        self.daily = daily


class Unavailable(ProviderError):
    pass


def system_prompt(request: Request, json_rule: bool = False) -> str:
    prompt = SYSTEM_PROMPT
    if request.examples:
        prompt += EXAMPLES_RULE
    if json_rule:
        prompt += JSON_RULE
    return prompt


def user_json(request: Request) -> str:
    """User input travels as named JSON fields, never inside the instructions."""
    data = {
        "symbols": request.symbols,
        "intention": request.intention,
        "scene_hint": request.scene_hint,
        "avoid": request.avoid[-12:],
    }
    if request.examples:
        data["examples"] = request.examples
    return json.dumps(data, ensure_ascii=False)


def sentences_from_text(text: str) -> list[str]:
    """Tolerant parser: the whole text as JSON, else the first {...} block in it."""
    candidates = [text]
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            sentences = json.loads(candidate).get("sentences", [])
        except (ValueError, AttributeError):
            continue
        if isinstance(sentences, list):
            return [s for s in sentences if isinstance(s, str)]
    return []


def clean_sentences(request: Request, sentences: list[str]) -> list[str]:
    """Same limits as the backend, plus the negation and repeat checks of the AI plan."""
    avoid = {s.strip().casefold() for s in request.avoid}
    negative = bool(NEGATION.search(" ".join([request.intention, *request.symbols])))
    result = []
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence or len(sentence) > MAX_SENTENCE_CHARS:
            continue
        if sentence.casefold() in avoid or sentence in result:
            continue
        # A negative wish must stay negative (REQ-ML-003).
        if negative and not NEGATION.search(sentence):
            continue
        result.append(sentence)
    return result[:3]


def network_error(name: str, error: httpx.HTTPError) -> Unavailable:
    if isinstance(error, httpx.TimeoutException):
        return Unavailable(f"{name}: timed out")
    if isinstance(error, httpx.ConnectError):
        return Unavailable(f"{name}: cannot connect")
    return Unavailable(f"{name}: network error ({type(error).__name__})")


def retry_after_header(response: httpx.Response) -> float | None:
    try:
        return float(response.headers.get("retry-after", ""))
    except ValueError:
        return None


class GeminiProvider:
    """Native generateContent call: response schema, low media resolution, least thinking."""

    def __init__(self, model: str, api_key: str, timeout: float = 30.0, transport=None):
        self.name = f"gemini:{model}"
        self.model = model
        self.client = make_client(api_key, read_timeout=timeout, transport=transport)

    def generate(self, request: Request) -> Result:
        parts = [{"text": user_json(request)}]
        if request.jpeg:
            data = base64.b64encode(request.jpeg).decode()
            parts.append({"inline_data": {"mime_type": "image/jpeg", "data": data}})
        body = build_body(
            parts,
            system=system_prompt(request),
            json_output=True,
            thinking=thinking_config(self.model),
            low_media_resolution=request.jpeg is not None,
        )
        try:
            response, latency = generate(self.client, self.model, body)
        except httpx.HTTPError as error:
            raise network_error(self.name, error) from None
        if response.status_code == 429:
            error = parse_error(429, response.text)
            kind = "daily" if error.is_daily else "per-minute"
            raise RateLimited(f"{self.name}: {kind} quota", error.retry_delay_s, error.is_daily)
        if response.status_code != 200:
            error = parse_error(response.status_code, response.text)
            raise Unavailable(
                f"{self.name}: HTTP {response.status_code} {error.api_status}".strip()
            )
        data = response.json()
        meta = data.get("usageMetadata", {})
        # A safety block or an empty answer is "no suggestion", not an error.
        return Result(
            sentences=clean_sentences(request, parse_sentences(data)),
            image_analyzed=request.jpeg is not None,
            provider=self.name,
            latency_s=latency,
            usage={
                "prompt": meta.get("promptTokenCount"),
                "output": meta.get("candidatesTokenCount"),
            },
        )


class OllamaProvider:
    """Local model through the native /api/chat endpoint (offline backup, CPU only)."""

    def __init__(
        self,
        model: str,
        url: str = "http://127.0.0.1:11434",
        timeout: float = 180.0,
        keep_alive: str = "10m",
        transport=None,
    ):
        self.name = f"ollama:{model}"
        self.model = model
        self.keep_alive = keep_alive
        # The first call loads the model and encodes the image on the CPU: long read timeout.
        self.client = httpx.Client(
            base_url=url, timeout=httpx.Timeout(timeout, connect=3.0), transport=transport
        )
        self.think = False

    def body(self, request: Request) -> dict:
        message = {"role": "user", "content": user_json(request)}
        if request.jpeg:
            message["images"] = [base64.b64encode(request.jpeg).decode()]
        schema = {
            "type": "object",
            "properties": {"sentences": {"type": "array", "items": {"type": "string"}}},
            "required": ["sentences"],
        }
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt(request, json_rule=True)},
                message,
            ],
            "stream": False,
            "format": schema,
            "options": {"num_predict": 150, "temperature": 0.7},
            "keep_alive": self.keep_alive,
        }
        if self.think is not None:
            body["think"] = self.think
        return body

    def generate(self, request: Request) -> Result:
        start = perf_counter()
        try:
            response = self.client.post("/api/chat", json=self.body(request))
            # Models without a thinking switch reject the "think" field; ask once without it.
            if response.status_code == 400 and "think" in response.text and self.think is not None:
                self.think = None
                response = self.client.post("/api/chat", json=self.body(request))
        except httpx.HTTPError as error:
            raise network_error(self.name, error) from None
        if response.status_code == 404:
            raise Unavailable(f"{self.name}: model not found, run: ollama pull {self.model}")
        if response.status_code != 200:
            # Ollama reports out-of-memory as a 500 with a text message.
            hint = " (not enough memory?)" if "memory" in response.text.lower() else ""
            raise Unavailable(f"{self.name}: HTTP {response.status_code}{hint}")
        data = response.json()
        text = (data.get("message") or {}).get("content", "")
        return Result(
            sentences=clean_sentences(request, sentences_from_text(text)),
            image_analyzed=request.jpeg is not None,
            provider=self.name,
            latency_s=perf_counter() - start,
            usage={"prompt": data.get("prompt_eval_count"), "output": data.get("eval_count")},
        )


class OpenAICompatibleProvider:
    """Chat-completions API with an image, for a hosted backup such as Z.ai GLM-4.6V-Flash.

    Not tested against a live service yet (no key). Vendor options go in `extra`.
    """

    def __init__(
        self,
        name: str,
        base_url: str,
        model: str,
        api_key: str,
        timeout: float = 30.0,
        extra: dict | None = None,
        transport=None,
    ):
        self.name = f"{name}:{model}"
        self.model = model
        self.extra = extra or {}
        self.client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(timeout, connect=5.0),
            transport=transport,
        )

    def generate(self, request: Request) -> Result:
        content = [{"type": "text", "text": user_json(request)}]
        if request.jpeg:
            url = "data:image/jpeg;base64," + base64.b64encode(request.jpeg).decode()
            content.append({"type": "image_url", "image_url": {"url": url}})
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt(request, json_rule=True)},
                {"role": "user", "content": content},
            ],
            "max_tokens": 150,
            "response_format": {"type": "json_object"},
            **self.extra,
        }
        start = perf_counter()
        try:
            response = self.client.post("/chat/completions", json=body)
        except httpx.HTTPError as error:
            raise network_error(self.name, error) from None
        if response.status_code == 429:
            raise RateLimited(f"{self.name}: rate limited", retry_after_header(response))
        if response.status_code != 200:
            raise Unavailable(f"{self.name}: HTTP {response.status_code}")
        data = response.json()
        choices = data.get("choices") or [{}]
        text = (choices[0].get("message") or {}).get("content") or ""
        usage = data.get("usage") or {}
        return Result(
            sentences=clean_sentences(request, sentences_from_text(text)),
            image_analyzed=request.jpeg is not None,
            provider=self.name,
            latency_s=perf_counter() - start,
            usage={"prompt": usage.get("prompt_tokens"), "output": usage.get("completion_tokens")},
        )
