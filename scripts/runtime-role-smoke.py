#!/usr/bin/env python3
"""Authenticate every seeded role and verify its active context against a running API."""
import argparse
import json
import sys
import urllib.error
import urllib.request

ACCOUNTS = {
    "admin": "admin@healthpilot.test", "patient": "patient1@healthpilot.test", "doctor": "dr.nakato@healthpilot.test",
    "clinical_officer": "clinical.officer@healthpilot.test", "dentist": "dentist@healthpilot.test",
    "medical_director": "medical.director@healthpilot.test", "nurse": "nurse@healthpilot.test",
    "midwife": "midwife@healthpilot.test", "theatre_nurse": "theatre.nurse@healthpilot.test",
    "anaesthetist": "anaesthetist@healthpilot.test", "radiologist": "radiologist@healthpilot.test",
    "radiographer": "radiographer@healthpilot.test", "physiotherapist": "physio@healthpilot.test",
    "nutritionist": "nutrition@healthpilot.test", "psychologist": "psychology@healthpilot.test",
    "paramedic": "paramedic@healthpilot.test", "ambulance_dispatcher": "dispatcher@healthpilot.test",
    "receptionist": "reception@healthpilot.test", "records_officer": "records@healthpilot.test",
    "cashier": "cashier@healthpilot.test", "accountant": "accountant@healthpilot.test",
    "finance_manager": "finance.manager@healthpilot.test", "facility_manager": "manager@healthpilot.test",
    "procurement_officer": "procurement@healthpilot.test", "storekeeper": "storekeeper@healthpilot.test",
    "quality_officer": "quality@healthpilot.test", "compliance_officer": "compliance@healthpilot.test",
    "hr_officer": "hr@healthpilot.test", "it_support": "it@healthpilot.test",
    "pharmacist": "pharmacist.staff@healthpilot.test", "lab_technician": "labtech@healthpilot.test",
    "insurance_officer": "insurance.officer@healthpilot.test", "claims_reviewer": "claims@healthpilot.test",
    "hospital": "hospital@healthpilot.test", "pharmacy": "pharmacy@healthpilot.test",
    "lab": "lab@healthpilot.test", "insurance": "insurance@healthpilot.test",
}

def request(url, method="GET", payload=None, token=None):
    body = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if token: headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as response:
        return response.status, json.loads(response.read().decode() or "{}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:4010/api")
    args = parser.parse_args()
    failures=[]; mfa=[]
    for role, email in ACCOUNTS.items():
        password = "AdminPass!2026" if role == "admin" else "DemoPass!2026"
        try:
            status, login = request(f"{args.base}/auth/token/", "POST", {"email": email, "password": password})
            if login.get("mfa_required"):
                mfa.append(role)
                continue
            token = login.get("access")
            if status != 200 or not token:
                failures.append(f"{role}: login did not return an access token")
                continue
            _, me = request(f"{args.base}/auth/me/", token=token)
            active = (me.get("active_context") or {}).get("role_code") or me.get("role")
            if active != role:
                failures.append(f"{role}: API returned active role {active!r}")
            request(f"{args.base}/journeys/dashboard/", token=token)
        except urllib.error.HTTPError as exc:
            failures.append(f"{role}: HTTP {exc.code} {exc.read().decode(errors='ignore')[:160]}")
        except Exception as exc:
            failures.append(f"{role}: {exc}")
    if failures:
        print("Role smoke failures:")
        for failure in failures: print(f"- {failure}")
        return 1
    print(f"Role smoke: {len(ACCOUNTS)-len(mfa)} authenticated roles passed; MFA challenge correctly returned for {', '.join(mfa) or 'none'}")
    return 0
if __name__ == "__main__": sys.exit(main())
