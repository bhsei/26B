"""First Gemini Flash example for the AAC sentence provider.

Run from the repository root:
    python -m src.ai.gemini_quickstart            # model info + 3 example calls
    python -m src.ai.gemini_quickstart --list     # Flash models available to your key
    python -m src.ai.gemini_quickstart --image path/to/synthetic_photo.jpg
    python -m src.ai.gemini_quickstart --save                 # append to generations.jsonl
    python -m src.ai.gemini_quickstart --save results/run1.jsonl

Uses 3 generateContent requests of the free daily quota per run (0 with --list).
Use synthetic photos only: free-tier inputs may be used by Google to improve products.
"""

import argparse
import base64
import json
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image, ImageDraw

from src.ai.gemini_common import (
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_body,
    describe_error,
    generate,
    load_api_key,
    make_client,
    parse_error,
    parse_sentences,
    save_records,
    thinking_config,
)


def synthetic_cafe_photo() -> Image.Image:
    """A drawn café table with a cup and a glass; no real photo is needed."""
    image = Image.new("RGB", (640, 480), (232, 218, 196))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 300, 640, 480), fill=(140, 96, 60))
    draw.text((230, 40), "CAFE  MENU: coffee  tea  water", fill=(40, 40, 40))
    draw.rectangle((180, 220, 260, 300), fill=(250, 250, 250), outline=(80, 80, 80))
    draw.ellipse((260, 240, 290, 270), outline=(80, 80, 80), width=5)
    draw.polygon([(400, 180), (460, 180), (450, 300), (410, 300)], fill=(200, 225, 240))
    return image


def to_jpeg_384(image: Image.Image) -> bytes:
    # Small upload; the token cost is set by mediaResolution=LOW in the request.
    image = image.convert("RGB")
    image.thumbnail((384, 384))
    output = BytesIO()
    image.save(output, format="JPEG", quality=85)
    return output.getvalue()


def user_parts(symbols, intention, scene, avoid, jpeg: bytes | None) -> list[dict]:
    data = {"symbols": symbols, "intention": intention, "scene_hint": scene, "avoid": avoid}
    parts = [{"text": json.dumps(data)}]
    if jpeg:
        parts.append(
            {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(jpeg).decode()}}
        )
    return parts


def show_model(client, model: str) -> bool:
    response = client.get(f"/models/{model}")
    if response.status_code != 200:
        print(describe_error(parse_error(response.status_code, response.text)))
        print("Model not available to this key. Try: python -m src.ai.gemini_quickstart --list")
        return False
    info = response.json()
    print(f"Model: {info.get('name')}  ({info.get('displayName', '')})")
    print(f"  input token limit:  {info.get('inputTokenLimit')}")
    print(f"  output token limit: {info.get('outputTokenLimit')}")
    print(f"  methods: {', '.join(info.get('supportedGenerationMethods', []))}")
    return True


def list_flash_models(client) -> None:
    params = {"pageSize": 100}
    while True:
        response = client.get("/models", params=params)
        if response.status_code != 200:
            print(describe_error(parse_error(response.status_code, response.text)))
            return
        data = response.json()
        for m in data.get("models", []):
            if "flash" in m["name"] and "generateContent" in m.get(
                "supportedGenerationMethods", []
            ):
                print(f"{m['name'].removeprefix('models/'):40} in={m.get('inputTokenLimit')}")
        if not data.get("nextPageToken"):
            return
        params["pageToken"] = data["nextPageToken"]


CASES = [
    {"title": "Text only: symbol 'water', café", "symbols": ["water"], "intention": "",
     "scene_hint": "A café", "with_image": False},
    {"title": "Photo + symbol 'water'", "symbols": ["water"], "intention": "",
     "scene_hint": "A café", "with_image": True},
    {"title": "Negation: 'I do not want sugar'", "symbols": ["coffee"],
     "intention": "I do not want sugar", "scene_hint": "A café", "with_image": True},
]


def run_case(client, model, case, jpeg, thinking, image_label) -> dict:
    """Call the model for one case, print the result and return a record for --save."""
    title = case["title"]
    image = jpeg if case["with_image"] else None
    parts = user_parts(case["symbols"], case["intention"], case["scene_hint"], [], image)
    record = {
        "time_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "thinking": thinking,
        "case": title,
        "input": {k: case[k] for k in ("symbols", "intention", "scene_hint")},
        "image": image_label if image else None,
        "status": None,
        "latency_s": None,
        "sentences": [],
        "finish_reason": None,
        "usage": None,
        "error": None,
    }
    body = build_body(
        parts,
        system=SYSTEM_PROMPT,
        json_output=True,
        thinking=thinking,
        low_media_resolution=image is not None,
    )
    try:
        response, elapsed = generate(client, model, body)
    except httpx.TimeoutException:
        print(f"\n== {title}\n  timed out; try again, raise --timeout or use another --model")
        record["error"] = "timeout"
        return record
    except httpx.HTTPError as exc:
        print(f"\n== {title}\n  network error: {type(exc).__name__} (check connection/proxy)")
        record["error"] = type(exc).__name__
        return record
    record["status"] = response.status_code
    record["latency_s"] = round(elapsed, 2)
    print(f"\n== {title}  ({elapsed:.2f} s)")
    if response.status_code != 200:
        error = parse_error(response.status_code, response.text)
        print(describe_error(error))
        if response.status_code == 503:
            print("  model overloaded (temporary); retry later or use another --model")
        record["error"] = {
            "api_status": error.api_status,
            "quota": [v.get("quotaId") for v in error.violations],
            "message": error.message[:300],
        }
        return record
    data = response.json()
    record["sentences"] = parse_sentences(data)
    for sentence in record["sentences"] or ["(no suggestions)"]:
        print(f"  - {sentence}")
    usage = data.get("usageMetadata", {})
    details = {d.get("modality"): d.get("tokenCount") for d in usage.get("promptTokensDetails", [])}
    record["usage"] = {
        "prompt": usage.get("promptTokenCount"),
        "prompt_by_modality": details,
        "output": usage.get("candidatesTokenCount"),
        "thinking": usage.get("thoughtsTokenCount", 0),
        "total": usage.get("totalTokenCount"),
    }
    print(
        f"  tokens: prompt={usage.get('promptTokenCount')} "
        f"({', '.join(f'{k}={v}' for k, v in details.items())})"
        f"  output={usage.get('candidatesTokenCount')}"
        f"  thinking={usage.get('thoughtsTokenCount', 0)}  total={usage.get('totalTokenCount')}"
    )
    finish = (data.get("candidates") or [{}])[0].get("finishReason")
    record["finish_reason"] = finish
    if finish and finish != "STOP":
        print(f"  finish reason: {finish}")
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--list", action="store_true", help="list Flash models and exit")
    parser.add_argument("--image", type=Path, help="synthetic photo (default: drawn café)")
    parser.add_argument(
        "--thinking-level", help="minimal/low/medium/high (default: lowest the model allows)"
    )
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="read timeout, s")
    parser.add_argument(
        "--save",
        type=Path,
        nargs="?",
        const=Path("generations.jsonl"),
        help="append every generation to a JSONL file (default name: generations.jsonl)",
    )
    args = parser.parse_args()
    thinking = thinking_config(args.model, args.thinking_level)

    with make_client(load_api_key(), read_timeout=args.timeout) as client:
        if args.list:
            list_flash_models(client)
            return
        if not show_model(client, args.model):
            return
        photo = Image.open(args.image) if args.image else synthetic_cafe_photo()
        jpeg = to_jpeg_384(photo)
        # Only the file name is recorded, never the image itself.
        label = args.image.name if args.image else "synthetic drawn café"
        records = [run_case(client, args.model, c, jpeg, thinking, label) for c in CASES]
    if args.save:
        save_records(args.save, records)
        print(f"\nSaved {len(records)} generations to {args.save}")


if __name__ == "__main__":
    main()
