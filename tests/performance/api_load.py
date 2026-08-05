#!/usr/bin/env python3
"""Authenticated API latency gate for HealthPilot.

Runs a mixed read workload against a seeded, running stack and fails when
latency or error-rate thresholds are exceeded. This is the executable
performance gate; the long-duration variant is ``scripts/soak-test.py``.

Usage:
    python tests/performance/api_load.py --base http://127.0.0.1:4000/api

Exit code is non-zero when any threshold is breached.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import statistics
import sys
import time
import urllib.error
import urllib.request

PASSWORD = "DemoPass!2026"
# Representative read endpoints exercised per role context.
READS = (
    "/auth/me/",
    "/appointments/",
    "/notifications/",
    "/journeys/dashboard/",
)
ACTORS = (
    "patient1@healthpilot.test",
    "dr.nakato@healthpilot.test",
    "nurse@healthpilot.test",
    "reception@healthpilot.test",
    "cashier@healthpilot.test",
    "records@healthpilot.test",
)


def call(url, method="GET", payload=None, token=None, timeout=30):
    started = time.perf_counter()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode() if payload is not None else None,
        method=method,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        status = exc.code
    return status, (time.perf_counter() - started) * 1000


def login(base, email):
    status, _ = call(f"{base}/auth/token/", "POST", {"email": email, "password": PASSWORD})
    if status != 200:
        raise RuntimeError(f"login failed for {email}: HTTP {status}")
    req = urllib.request.Request(
        f"{base}/auth/token/",
        data=json.dumps({"email": email, "password": PASSWORD}).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode())["access"]


def percentile(values, pct):
    ordered = sorted(values)
    return ordered[max(0, int(len(ordered) * pct) - 1)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:4000/api")
    parser.add_argument("--requests", type=int, default=240)
    parser.add_argument("--concurrency", type=int, default=12)
    parser.add_argument("--max-p95-ms", type=float, default=1500.0)
    parser.add_argument("--max-error-rate", type=float, default=0.01)
    args = parser.parse_args()

    tokens = {email: login(args.base, email) for email in ACTORS}
    plan = []
    for index in range(args.requests):
        email = ACTORS[index % len(ACTORS)]
        plan.append((args.base + READS[index % len(READS)], tokens[email]))

    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        results = list(pool.map(lambda item: call(item[0], token=item[1]), plan))
    elapsed = time.perf_counter() - started

    statuses = [status for status, _ in results]
    durations = [duration for _, duration in results]
    errors = sum(1 for status in statuses if status >= 500)
    # 403 is an expected authorization denial on shared cross-role read lists.
    denied = sum(1 for status in statuses if status == 403)
    client_errors = sum(1 for status in statuses if 400 <= status < 500 and status != 403)
    error_rate = errors / len(statuses)
    p50 = percentile(durations, 0.50)
    p95 = percentile(durations, 0.95)

    print(
        f"API load gate: {len(results)} requests in {elapsed:.1f}s "
        f"({len(results) / elapsed:.1f} req/s); p50={p50:.0f}ms p95={p95:.0f}ms "
        f"max={max(durations):.0f}ms; 5xx={errors} 403={denied} other-4xx={client_errors}"
    )

    failures = []
    if p95 > args.max_p95_ms:
        failures.append(f"p95 {p95:.0f}ms exceeds {args.max_p95_ms:.0f}ms")
    if error_rate > args.max_error_rate:
        failures.append(f"5xx rate {error_rate:.3%} exceeds {args.max_error_rate:.3%}")
    if client_errors:
        failures.append(f"{client_errors} unexpected 4xx responses on authenticated reads")
    if failures:
        print("PERFORMANCE GATE FAILED: " + "; ".join(failures))
        return 1
    print("Performance gate passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
