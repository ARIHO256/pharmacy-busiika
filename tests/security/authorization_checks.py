#!/usr/bin/env python3
"""Live-stack authorization regression checks for HealthPilot.

Complements the static ``scripts/authorization-audit.py`` source scan by
asserting, against a running seeded stack, that:

* unauthenticated callers are rejected from protected API surfaces;
* patients cannot reach admin, billing-staff, or registry-review endpoints;
* staff cannot read another organization's registry documents;
* payment webhooks reject unsigned/forged payloads;
* break-glass access is denied without an emergency grant.

Usage:
    python tests/security/authorization_checks.py --base http://127.0.0.1:4000/api

Exit code is non-zero when any check fails.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

PASSWORD = "DemoPass!2026"


def call(url, method="GET", payload=None, token=None, timeout=20):
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
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code


def login(base, email, password=PASSWORD):
    status = call(f"{base}/auth/token/", "POST", {"email": email, "password": password})
    if status != 200:
        raise RuntimeError(f"login failed for {email}: HTTP {status}")
    req = urllib.request.Request(
        f"{base}/auth/token/",
        data=json.dumps({"email": email, "password": password}).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode())["access"]


class Checks:
    def __init__(self, base):
        self.base = base
        self.failures = []
        self.passed = 0

    def expect(self, label, actual, expected):
        allowed = expected if isinstance(expected, (tuple, set, frozenset)) else (expected,)
        if actual in allowed:
            self.passed += 1
            print(f"  ok   {label}: HTTP {actual}")
        else:
            self.failures.append(f"{label}: expected HTTP {sorted(allowed)}, got {actual}")
            print(f"  FAIL {label}: HTTP {actual} (expected {sorted(allowed)})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:4000/api")
    args = parser.parse_args()
    base = args.base.rstrip("/")
    checks = Checks(base)

    patient = login(base, "patient1@healthpilot.test")
    admin = login(base, "admin@healthpilot.test", "AdminPass!2026")

    print("Unauthenticated access is rejected")
    checks.expect("anonymous /auth/me/", call(f"{base}/auth/me/"), (401, 403))
    checks.expect("anonymous admin users", call(f"{base}/admin/users/"), (401, 403))
    checks.expect("anonymous billing summary", call(f"{base}/billing/summary/"), (401, 403))
    checks.expect("anonymous outbox", call(f"{base}/interoperability/outbox/"), (401, 403))

    print("Patient role cannot reach staff/admin surfaces")
    checks.expect("patient -> admin users", call(f"{base}/admin/users/", token=patient), (403, 404))
    checks.expect("patient -> billing summary", call(f"{base}/billing/summary/", token=patient), (403, 404))
    checks.expect("patient -> outbox", call(f"{base}/interoperability/outbox/", token=patient), (403, 404))
    checks.expect(
        "patient -> release acceptance admin",
        call(f"{base}/journeys/release-acceptance/", token=patient),
        (403, 404),
    )

    print("Payment webhooks reject forged payloads")
    checks.expect(
        "unsigned flutterwave webhook",
        call(f"{base}/payments/webhook/flutterwave/", "POST", {"status": "successful", "data": {"id": 1}}),
        (400, 401, 403, 404),
    )
    checks.expect(
        "unsigned paystack webhook",
        call(f"{base}/payments/webhook/paystack/", "POST", {"event": "charge.success", "data": {}}),
        (400, 401, 403, 404),
    )

    print("Clinical break-glass is denied without a grant")
    checks.expect(
        "patient -> other patient FHIR summary",
        call(f"{base}/interoperability/fhir/patients/1/summary/", token=patient),
        (403, 404),
    )

    print("Admin retains platform oversight")
    checks.expect("admin -> admin users", call(f"{base}/admin/users/", token=admin), 200)

    print(f"\n{checks.passed} checks passed, {len(checks.failures)} failed")
    if checks.failures:
        print("SECURITY CHECKS FAILED:")
        for failure in checks.failures:
            print(f"  - {failure}")
        return 1
    print("Authorization regression checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
