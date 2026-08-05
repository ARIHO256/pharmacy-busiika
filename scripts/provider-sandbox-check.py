#!/usr/bin/env python3
"""Perform harmless connectivity tests for configured production/sandbox providers.

No payment, message, or patient record is created by this script.  It validates
credentials by using token, balance, metadata, HEAD, PING, or health endpoints.
Provider transaction/callback/reconciliation evidence is still required by the
formal release-acceptance gate.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import socket
import ssl
import sys
import urllib.parse
import urllib.request

STATIC_REQUIRED = {
    "mtn_momo": ["MTN_MOMO_BASE_URL", "MTN_MOMO_SUBSCRIPTION_KEY", "MTN_MOMO_API_USER", "MTN_MOMO_API_KEY"],
    "airtel_money": ["AIRTEL_MONEY_BASE_URL", "AIRTEL_MONEY_CLIENT_ID", "AIRTEL_MONEY_CLIENT_SECRET"],
    "flutterwave": ["FLUTTERWAVE_SECRET_KEY", "FLUTTERWAVE_WEBHOOK_SECRET_HASH"],
    "paystack": ["PAYSTACK_SECRET_KEY", "PAYSTACK_WEBHOOK_SECRET"],
    "whatsapp": ["WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID"],
    "zoom": ["ZOOM_ACCOUNT_ID", "ZOOM_CLIENT_ID", "ZOOM_CLIENT_SECRET"],
    "object_storage": ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_STORAGE_BUCKET_NAME", "AWS_S3_ENDPOINT_URL"],
    "pacs": ["ORTHANC_BASE_URL", "ORTHANC_USERNAME", "ORTHANC_PASSWORD"],
    "malware_scanning": ["CLAMAV_HOST", "CLAMAV_PORT"],
    "event_delivery": ["OUTBOX_SIGNING_SECRET"],
}
ALL_PROVIDERS = tuple(sorted((*STATIC_REQUIRED.keys(), "sms", "push")))


def dynamic_required(provider):
    if provider == "sms":
        name = os.getenv("SMS_PROVIDER", "").lower()
        return {
            "africastalking": ["AFRICASTALKING_USERNAME", "AFRICASTALKING_API_KEY", "AFRICASTALKING_SENDER_ID"],
            "twilio": ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER"],
            "webhook": ["SMS_WEBHOOK_URL", "SMS_WEBHOOK_TOKEN"],
        }.get(name, ["SMS_PROVIDER"])
    if provider == "push":
        name = os.getenv("PUSH_PROVIDER", "fcm").lower()
        if name == "webhook":
            return ["PUSH_WEBHOOK_URL", "PUSH_WEBHOOK_TOKEN"]
        return ["FCM_PROJECT_ID", "FCM_SERVICE_ACCOUNT_FILE|FCM_SERVICE_ACCOUNT_JSON"]
    return STATIC_REQUIRED[provider]


def value_present(key):
    if "|" in key:
        return any(value_present(item) for item in key.split("|"))
    value = os.getenv(key, "").strip()
    return bool(value) and not any(token in value.lower() for token in ("change-me", "example.invalid", "demo_", "replace-me"))


def missing_keys(keys):
    return [key for key in keys if not value_present(key)]


def request_json(url, *, method="GET", payload=None, form=None, headers=None, timeout=20):
    body = None
    request_headers = {"Accept": "application/json", **(headers or {})}
    if payload is not None:
        body = json.dumps(payload).encode()
        request_headers.setdefault("Content-Type", "application/json")
    elif form is not None:
        body = urllib.parse.urlencode(form).encode()
        request_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    request = urllib.request.Request(url, data=body, method=method, headers=request_headers)
    with urllib.request.urlopen(request, timeout=timeout, context=ssl.create_default_context()) as response:
        raw = response.read(4096).decode(errors="ignore")
        try: data = json.loads(raw) if raw else {}
        except json.JSONDecodeError: data = {"raw": raw[:500]}
        return response.status, data


def basic(user, password):
    return "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()


def check(provider):
    if provider == "mtn_momo":
        status, data = request_json(
            os.environ["MTN_MOMO_BASE_URL"].rstrip("/") + "/collection/token/",
            method="POST",
            headers={"Authorization": basic(os.environ["MTN_MOMO_API_USER"], os.environ["MTN_MOMO_API_KEY"]), "Ocp-Apim-Subscription-Key": os.environ["MTN_MOMO_SUBSCRIPTION_KEY"]},
        )
        return status == 200 and bool(data.get("access_token")), "token"
    if provider == "airtel_money":
        status, data = request_json(os.environ["AIRTEL_MONEY_BASE_URL"].rstrip("/") + "/auth/oauth2/token", method="POST", payload={"client_id": os.environ["AIRTEL_MONEY_CLIENT_ID"], "client_secret": os.environ["AIRTEL_MONEY_CLIENT_SECRET"], "grant_type": "client_credentials"})
        return status in {200, 201} and bool(data.get("access_token") or data.get("data", {}).get("access_token")), "token"
    if provider == "flutterwave":
        status, data = request_json(os.getenv("FLUTTERWAVE_V3_BASE_URL", "https://api.flutterwave.com/v3").rstrip("/") + "/balances/UGX", headers={"Authorization": f"Bearer {os.environ['FLUTTERWAVE_SECRET_KEY']}"})
        return status == 200 and data.get("status") == "success", "balance metadata"
    if provider == "paystack":
        status, data = request_json(os.getenv("PAYSTACK_BASE_URL", "https://api.paystack.co").rstrip("/") + "/balance", headers={"Authorization": f"Bearer {os.environ['PAYSTACK_SECRET_KEY']}"})
        return status == 200 and bool(data.get("status")), "balance metadata"
    if provider == "sms":
        name = os.getenv("SMS_PROVIDER", "").lower()
        if name == "africastalking":
            status, data = request_json(f"https://api.africastalking.com/version1/user?username={urllib.parse.quote(os.environ['AFRICASTALKING_USERNAME'])}", headers={"apiKey": os.environ["AFRICASTALKING_API_KEY"]})
            return status == 200 and "UserData" in data, "account metadata"
        if name == "twilio":
            sid = os.environ["TWILIO_ACCOUNT_SID"]
            status, data = request_json(f"https://api.twilio.com/2010-04-01/Accounts/{sid}.json", headers={"Authorization": basic(sid, os.environ["TWILIO_AUTH_TOKEN"])})
            return status == 200 and bool(data.get("sid")), "account metadata"
        status, _ = request_json(os.environ["SMS_WEBHOOK_URL"], method="HEAD", headers={"Authorization": f"Bearer {os.environ['SMS_WEBHOOK_TOKEN']}"})
        return status < 400, "webhook health"
    if provider == "whatsapp":
        version = os.getenv("WHATSAPP_GRAPH_VERSION", "v21.0")
        phone_id = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
        status, data = request_json(f"https://graph.facebook.com/{version}/{phone_id}?fields=display_phone_number,verified_name", headers={"Authorization": f"Bearer {os.environ['WHATSAPP_ACCESS_TOKEN']}"})
        return status == 200 and bool(data.get("id") or data.get("display_phone_number")), "phone metadata"
    if provider == "push":
        if os.getenv("PUSH_PROVIDER", "fcm").lower() == "webhook":
            status, _ = request_json(os.environ["PUSH_WEBHOOK_URL"], method="HEAD", headers={"Authorization": f"Bearer {os.environ['PUSH_WEBHOOK_TOKEN']}"})
            return status < 400, "webhook health"
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
        scopes = ["https://www.googleapis.com/auth/firebase.messaging"]
        raw = os.getenv("FCM_SERVICE_ACCOUNT_JSON", "").strip()
        credentials = service_account.Credentials.from_service_account_info(json.loads(raw), scopes=scopes) if raw else service_account.Credentials.from_service_account_file(os.environ["FCM_SERVICE_ACCOUNT_FILE"], scopes=scopes)
        credentials.refresh(Request())
        return bool(credentials.token), "OAuth token"
    if provider == "zoom":
        url = "https://zoom.us/oauth/token?" + urllib.parse.urlencode({"grant_type": "account_credentials", "account_id": os.environ["ZOOM_ACCOUNT_ID"]})
        status, data = request_json(url, method="POST", headers={"Authorization": basic(os.environ["ZOOM_CLIENT_ID"], os.environ["ZOOM_CLIENT_SECRET"])})
        return status == 200 and bool(data.get("access_token")), "OAuth token"
    if provider == "object_storage":
        import boto3
        client = boto3.client("s3", endpoint_url=os.environ["AWS_S3_ENDPOINT_URL"], aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"], aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"], region_name=os.getenv("AWS_S3_REGION_NAME", "us-east-1"))
        client.head_bucket(Bucket=os.environ["AWS_STORAGE_BUCKET_NAME"])
        return True, "head bucket"
    if provider == "pacs":
        status, data = request_json(os.environ["ORTHANC_BASE_URL"].rstrip("/") + "/system", headers={"Authorization": basic(os.environ["ORTHANC_USERNAME"], os.environ["ORTHANC_PASSWORD"])})
        return status == 200 and bool(data.get("Name") or data.get("Version")), "system metadata"
    if provider == "malware_scanning":
        with socket.create_connection((os.environ["CLAMAV_HOST"], int(os.environ["CLAMAV_PORT"])), timeout=10) as sock:
            sock.sendall(b"zPING\0")
            response = sock.recv(64)
        return b"PONG" in response, "clamd ping"
    if provider == "event_delivery":
        secret = os.environ["OUTBOX_SIGNING_SECRET"]
        if len(secret) < 32: return False, "signing secret is shorter than 32 characters"
        health = os.getenv("OUTBOX_HEALTHCHECK_URL", "").strip()
        if health:
            status, _ = request_json(health, method="HEAD")
            return status < 400, "destination health"
        return True, "local signing configuration"
    raise ValueError(provider)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--require", action="append", choices=ALL_PROVIDERS)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    env_required = [value.strip() for value in os.getenv("HEALTHPILOT_REQUIRED_PROVIDERS", "").split(",") if value.strip()]
    selected = args.require or env_required or list(ALL_PROVIDERS)
    unknown = sorted(set(selected) - set(ALL_PROVIDERS))
    if unknown:
        print(f"Unknown providers: {', '.join(unknown)}", file=sys.stderr); return 2
    results = {}; failed = []
    for provider in selected:
        missing = missing_keys(dynamic_required(provider))
        result = {"configured": not missing, "missing": missing, "connectivity": "not_attempted", "check": ""}
        if not missing:
            try:
                ok, check_name = check(provider)
                result["connectivity"] = "passed" if ok else "failed"
                result["check"] = check_name
            except Exception as exc:
                result["connectivity"] = "failed"
                result["check"] = str(exc)
        if missing or result["connectivity"] != "passed": failed.append(provider)
        results[provider] = result
    output = {"provider_mode": os.getenv("HEALTHPILOT_PROVIDER_MODE", "unset"), "required": selected, "results": results, "passed": not failed}
    print(json.dumps(output, indent=2))
    if failed:
        print("Provider sandbox acceptance blocked: " + ", ".join(failed), file=sys.stderr); return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
