"""Check the Gemini free-tier rate limits for one model with real requests.

Google does not return rate-limit headers. When a limit is hit, the 429 response
names the quota (for example GenerateRequestsPerMinutePerProjectPerModel-FreeTier),
its value and the retry delay. This script reads those details.

Run from the repository root:
    python -m src.ai.gemini_rate_limit burst                  # until the first 429 (max 15)
    python -m src.ai.gemini_rate_limit burst --wait-retry     # then confirm recovery
    python -m src.ai.gemini_rate_limit paced --rpm 5 --minutes 2
    python -m src.ai.gemini_rate_limit burst --csv rate_limit_log.csv

Every request counts against the daily quota (RPD). Each request is tiny
(a few input tokens, at most 20 output tokens, lowest thinking level), so tokens per minute are not tested.
"""

import argparse
import csv
import sys
from time import monotonic, sleep

from src.ai.gemini_common import (
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT,
    build_body,
    describe_error,
    generate,
    load_api_key,
    make_client,
    parse_error,
    thinking_config,
)


def ping_body(model: str) -> dict:
    return build_body(
        [{"text": "Reply with the single word OK."}],
        max_output_tokens=20,
        thinking=thinking_config(model),
    )


class Recorder:
    def __init__(self, csv_path: str | None):
        self.rows: list[dict] = []
        self.csv_path = csv_path
        self.start = monotonic()

    def send(self, client, model: str):
        try:
            response, elapsed = generate(client, model, ping_body(model))
        except Exception as exc:  # noqa: BLE001 - report network errors, keep going
            self.rows.append(self._row(None, 0.0, type(exc).__name__))
            print(f"#{len(self.rows):3}  t={self.rows[-1]['t_s']:7.2f}s  {type(exc).__name__}")
            return None, None
        error = None
        tokens = ""
        if response.status_code == 200:
            tokens = response.json().get("usageMetadata", {}).get("totalTokenCount", "")
        else:
            error = parse_error(response.status_code, response.text)
        quota = ";".join(v.get("quotaId", "") for v in error.violations) if error else ""
        self.rows.append(self._row(response.status_code, elapsed, quota, tokens))
        row = self.rows[-1]
        print(f"#{len(self.rows):3}  t={row['t_s']:7.2f}s  HTTP {row['status']}"
              f"  {row['latency_s']:.2f}s  {quota or ''}")
        return response, error

    def _row(self, status, elapsed, note, tokens=""):
        return {
            "n": len(self.rows) + 1,
            "t_s": round(monotonic() - self.start, 2),
            "status": status,
            "latency_s": round(elapsed, 2),
            "total_tokens": tokens,
            "note": note,
        }

    def save(self):
        if not self.csv_path or not self.rows:
            return
        with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(self.rows[0]))
            writer.writeheader()
            writer.writerows(self.rows)
        print(f"Log written to {self.csv_path}")

    def ok_count(self) -> int:
        return sum(1 for r in self.rows if r["status"] == 200)


def burst(client, args, rec: Recorder) -> int:
    print(f"Burst on {args.model}: sequential requests until a 429 (max {args.max_requests}).")
    for _ in range(args.max_requests):
        response, error = rec.send(client, args.model)
        if error is None:
            continue
        print(describe_error(error))
        if error.status == 503:
            print("  model overloaded (temporary, not a quota limit); continuing")
            continue
        if error.status != 429:
            print("Stopped: not a rate-limit error (check key, model ID or region).")
            return 1
        window = rec.rows[-1]["t_s"]
        print(f"\nResult: {rec.ok_count()} successful requests in {window:.1f} s before the 429.")
        if error.is_daily:
            print("The daily quota (RPD) is exhausted. Try again after the daily reset.")
            return 0
        if args.wait_retry:
            # The first retryDelay can be too short (1 s seen, then 58 s): retry up to 3 times.
            for _ in range(3):
                delay = (error.retry_delay_s or 60.0) + 1.0
                print(f"Waiting {delay:.0f} s (retry delay + 1 s) to confirm recovery...")
                sleep(delay)
                _, again = rec.send(client, args.model)
                if again is None or again.status != 429:
                    print("Recovered: request accepted again." if again is None
                          else describe_error(again))
                    break
                print("Still limited:\n" + describe_error(again))
                error = again
        return 0
    print(f"\nNo 429 after {args.max_requests} requests in {rec.rows[-1]['t_s']:.1f} s. "
          "The per-minute limit is higher than this; raise --max-requests to find it.")
    return 0


def paced(client, args, rec: Recorder) -> int:
    interval = 60.0 / args.rpm
    total = int(args.rpm * args.minutes)
    print(f"Paced on {args.model}: {total} requests at {args.rpm} per minute "
          f"(one every {interval:.1f} s).")
    limited = 0
    for i in range(total):
        due = rec.start + i * interval
        if (wait := due - monotonic()) > 0:
            sleep(wait)
        _, error = rec.send(client, args.model)
        if error is not None:
            print(describe_error(error))
            if error.status == 503:
                continue
            if error.status != 429 or error.is_daily:
                return 1
            limited += 1
    if limited:
        print(f"\nResult: {limited} of {total} requests were rate limited at {args.rpm} RPM.")
    else:
        print(f"\nResult: {args.rpm} RPM sustained for {args.minutes} min without a 429.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode", choices=["burst", "paced"])
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-requests", type=int, default=15)
    parser.add_argument("--wait-retry", action="store_true")
    parser.add_argument("--rpm", type=float, default=5.0)
    parser.add_argument("--minutes", type=float, default=1.0)
    parser.add_argument("--csv", help="optional CSV log path")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="read timeout, s")
    args = parser.parse_args()

    rec = Recorder(args.csv)
    with make_client(load_api_key(), read_timeout=args.timeout) as client:
        try:
            code = burst(client, args, rec) if args.mode == "burst" else paced(client, args, rec)
        except KeyboardInterrupt:
            code = 130
    rec.save()
    print(f"Requests sent: {len(rec.rows)} (all count against today's quota).")
    return code


if __name__ == "__main__":
    sys.exit(main())
