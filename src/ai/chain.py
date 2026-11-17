"""Fallback chain over several providers (AI plan, failure modes F-05 to F-08, F-16, F-17).

Order matters: the first provider that is not cooling down, not over its daily cap and
not switched off by the circuit breaker gets the request. Daily counts and cooldowns
are kept in a small JSON file so separate runs of the scripts share the same quota view.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import time

from src.ai.providers import ProviderError, RateLimited, Request, Result

# Gemini resets daily quotas at midnight Pacific time. A fixed UTC-8 is used because
# Windows Python has no time-zone database by default; in summer the reset is seen
# one hour late, which only makes the cap more careful.
QUOTA_DAY = timezone(timedelta(hours=-8))
DEFAULT_COOLDOWN_S = 60.0
FAILURES_BEFORE_PAUSE = 3
PAUSE_S = 300.0


def quota_day(now: float) -> str:
    return datetime.fromtimestamp(now, QUOTA_DAY).date().isoformat()


def next_quota_day(now: float) -> float:
    day = datetime.fromtimestamp(now, QUOTA_DAY).date() + timedelta(days=1)
    return datetime(day.year, day.month, day.day, tzinfo=QUOTA_DAY).timestamp()


class UsageStore:
    """{"day": "...", "counts": {name: n}, "cooldown_until": {name: epoch}} on disk."""

    def __init__(self, path: Path | None):
        self.path = path
        self.data = {"day": "", "counts": {}, "cooldown_until": {}}
        if path and path.exists():
            try:
                self.data.update(json.loads(path.read_text(encoding="utf-8")))
            except ValueError:
                pass  # A broken file only loses today's counts.

    def roll(self, now: float) -> None:
        if self.data["day"] != quota_day(now):
            self.data["day"] = quota_day(now)
            self.data["counts"] = {}

    def count(self, name: str) -> int:
        return self.data["counts"].get(name, 0)

    def add(self, name: str) -> None:
        self.data["counts"][name] = self.count(name) + 1
        self.save()

    def cooldown_until(self, name: str) -> float:
        return self.data["cooldown_until"].get(name, 0.0)

    def cool_down(self, name: str, until: float) -> None:
        self.data["cooldown_until"][name] = until
        self.save()

    def save(self) -> None:
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, indent=1), encoding="utf-8")


@dataclass
class Entry:
    provider: object
    daily_cap: int | None = None  # None: no local cap (Ollama)
    failures: int = 0
    paused_until: float = 0.0

    @property
    def name(self) -> str:
        return self.provider.name


@dataclass
class Attempt:
    provider: str
    outcome: str  # "ok", "skipped: ...", or the error message


@dataclass
class ChainResult:
    result: Result
    attempts: list[Attempt] = field(default_factory=list)


class AllProvidersFailed(Exception):
    def __init__(self, attempts: list[Attempt]):
        super().__init__("No provider could generate suggestions.")
        self.attempts = attempts


class ProviderChain:
    def __init__(self, entries: list[Entry], usage: UsageStore, budget_s: float = 60.0, clock=time):
        self.entries = entries
        self.usage = usage
        self.budget_s = budget_s
        self.clock = clock

    def skip_reason(self, entry: Entry, now: float) -> str:
        if self.usage.cooldown_until(entry.name) > now:
            wait = self.usage.cooldown_until(entry.name) - now
            return f"skipped: quota cooldown, {wait:.0f} s left"
        if entry.daily_cap is not None and self.usage.count(entry.name) >= entry.daily_cap:
            return f"skipped: local daily cap {entry.daily_cap} reached"
        if entry.paused_until > now:
            return "skipped: paused after repeated failures"
        return ""

    def generate(self, request: Request) -> ChainResult:
        start = self.clock()
        self.usage.roll(start)
        attempts = []
        for entry in self.entries:
            now = self.clock()
            if now - start > self.budget_s:
                attempts.append(Attempt(entry.name, "skipped: time budget used"))
                continue
            reason = self.skip_reason(entry, now)
            if reason:
                attempts.append(Attempt(entry.name, reason))
                continue
            # Count before calling: a failed request still uses the provider's quota.
            if entry.daily_cap is not None:
                self.usage.add(entry.name)
            try:
                result = entry.provider.generate(request)
            except RateLimited as error:
                # No retry loop on 429: wait out the delay and use the next provider now.
                now = self.clock()
                if error.daily:
                    until = next_quota_day(now)
                else:
                    until = now + (error.retry_after_s or DEFAULT_COOLDOWN_S)
                self.usage.cool_down(entry.name, until)
                attempts.append(Attempt(entry.name, str(error)))
                continue
            except ProviderError as error:
                entry.failures += 1
                if entry.failures >= FAILURES_BEFORE_PAUSE:
                    entry.paused_until = self.clock() + PAUSE_S
                    entry.failures = 0
                attempts.append(Attempt(entry.name, str(error)))
                continue
            entry.failures = 0
            attempts.append(Attempt(entry.name, "ok"))
            return ChainResult(result, attempts)
        # Never fall back to mock templates: they would look like a real AI answer.
        raise AllProvidersFailed(attempts)

    def status(self) -> list[str]:
        now = self.clock()
        self.usage.roll(now)
        lines = []
        for entry in self.entries:
            cap = (
                "no cap"
                if entry.daily_cap is None
                else f"{self.usage.count(entry.name)}/{entry.daily_cap}"
            )
            state = self.skip_reason(entry, now) or "ready"
            lines.append(f"{entry.name:34} {cap:>8}  {state}")
        return lines
