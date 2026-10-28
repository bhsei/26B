"""Suggestions with backup models and reuse of accepted sentences (standalone prototype).

Run from the repository root:
    python -m src.ai.suggest --symbols water --scene "A café"
    python -m src.ai.suggest --symbols water --scene "A café" --photo
    python -m src.ai.suggest --symbols coffee --intention "I do not want sugar" --accept 1
    python -m src.ai.suggest --status            # daily counts and cooldowns, no calls

Flow: reuse an accepted sentence if the same request was answered before (no AI call);
otherwise ask the providers in order, with the closest accepted sentences as examples.
Data files go to ai_data/ (git-ignored). Use synthetic inputs and photos only.
"""

import argparse
import sys
from pathlib import Path

from PIL import Image

from src.ai.chain import AllProvidersFailed, Entry, ProviderChain, UsageStore
from src.ai.gemini_common import ROOT, env_value
from src.ai.gemini_quickstart import synthetic_cafe_photo, to_jpeg_384
from src.ai.providers import GeminiProvider, OllamaProvider, OpenAICompatibleProvider, Request
from src.ai.retrieval import MemoryStore

DATA = ROOT / "ai_data"
# Each Gemini model has its own free quota (20 a day measured for 3.5 Flash), so
# several models on one key multiply the daily requests before the local backup.
DEFAULT_ORDER = (
    "gemini:gemini-3.5-flash-lite,gemini:gemini-3.1-flash-lite,"
    "gemini:gemini-3.5-flash,gemini:gemini-3.8-flash,ollama:qwen3-vl:2b"
)
DEFAULT_DAILY_CAP = 16  # 80 % of the measured 20 per day, so a demo never hits the limit
ZAI_URL = "https://api.z.ai/api/paas/v4"


def build_entries(order: str, daily_cap: int) -> tuple[list[Entry], list[str]]:
    """Providers from "kind:model,..."; missing keys are reported, not fatal."""
    entries, notes = [], []
    gemini_key = env_value("GEMINI_API_KEY")
    for spec in filter(None, (s.strip() for s in order.split(","))):
        kind, _, model = spec.partition(":")
        if kind == "gemini":
            if not gemini_key:
                notes.append(f"{spec}: left out, GEMINI_API_KEY is not set")
                continue
            entries.append(Entry(GeminiProvider(model, gemini_key), daily_cap))
        elif kind == "ollama":
            url = env_value("OLLAMA_URL") or "http://127.0.0.1:11434"
            entries.append(Entry(OllamaProvider(model, url), None))
        elif kind == "zai":
            key = env_value("ZAI_API_KEY")
            if not key:
                notes.append(f"{spec}: left out, ZAI_API_KEY is not set")
                continue
            entries.append(Entry(OpenAICompatibleProvider("zai", ZAI_URL, model, key), daily_cap))
        else:
            notes.append(f"{spec}: unknown provider kind (use gemini, ollama or zai)")
    return entries, notes


def show(attempt) -> None:
    # Provider errors already start with the provider name.
    print(f"  {attempt.provider}: {attempt.outcome.removeprefix(attempt.provider + ': ')}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--symbols", nargs="*", default=[])
    parser.add_argument("--intention", default="")
    parser.add_argument("--scene", default="")
    photo = parser.add_mutually_exclusive_group()
    photo.add_argument("--photo", action="store_true", help="attach the drawn café photo")
    photo.add_argument("--image", type=Path, help="attach a synthetic photo file")
    parser.add_argument("--avoid", nargs="*", default=[], help="sentences already shown")
    parser.add_argument("--order", default=env_value("AI_PROVIDER_ORDER") or DEFAULT_ORDER)
    parser.add_argument("--daily-cap", type=int, default=DEFAULT_DAILY_CAP)
    parser.add_argument("--budget", type=float, default=240.0, help="seconds for all attempts")
    parser.add_argument("--memory", type=Path, default=DATA / "accepted.jsonl")
    parser.add_argument("--no-reuse", action="store_true", help="always call a model")
    parser.add_argument("--no-examples", action="store_true", help="no RAG examples in prompt")
    parser.add_argument("--accept", type=int, help="store suggestion N as accepted")
    parser.add_argument("--status", action="store_true", help="show quota state and exit")
    args = parser.parse_args()

    entries, notes = build_entries(args.order, args.daily_cap)
    for note in notes:
        print(note)
    chain = ProviderChain(entries, UsageStore(DATA / "usage.json"), budget_s=args.budget)
    if args.status:
        print("\n".join(chain.status()))
        return 0
    if not args.symbols and not args.intention.strip():
        parser.error("give --symbols or --intention")

    jpeg = None
    if args.image:
        jpeg = to_jpeg_384(Image.open(args.image))
    elif args.photo:
        jpeg = to_jpeg_384(synthetic_cafe_photo())
    request = Request(args.symbols, args.intention.strip(), args.scene.strip(), args.avoid, jpeg)
    memory = MemoryStore(args.memory)

    sentences = [] if args.no_reuse else memory.reuse(request)
    if sentences:
        print("Reused accepted sentences (no AI call):")
    else:
        if not args.no_examples:
            request.examples = memory.examples(request)
            if request.examples:
                print(f"Examples from past accepted sentences: {request.examples}")
        try:
            outcome = chain.generate(request)
        except AllProvidersFailed as error:
            for attempt in error.attempts:
                show(attempt)
            print("No provider could answer. Try again later.")
            return 1
        for attempt in outcome.attempts:
            show(attempt)
        result = outcome.result
        sentences = result.sentences
        usage = ", ".join(f"{k} {v}" for k, v in result.usage.items() if v is not None)
        print(
            f"{result.provider} in {result.latency_s:.1f} s"
            f"{f' ({usage} tokens)' if usage else ''}, image analysed: {result.image_analyzed}"
        )
    if not sentences:
        print("No suggestions. Change the symbols or the intention.")
        return 0
    for i, sentence in enumerate(sentences, 1):
        print(f"  {i}. {sentence}")

    choice = args.accept
    if choice is None and sys.stdin.isatty():
        try:
            answer = input("Accept which (number, Enter for none)? ").strip()
        except EOFError:  # On Windows NUL counts as a terminal.
            answer = ""
        choice = int(answer) if answer.isdigit() else None
    if choice and 1 <= choice <= len(sentences):
        memory.accept(request, sentences[choice - 1])
        print(f"Stored as accepted: {sentences[choice - 1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
