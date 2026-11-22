"""Encrypted, append-only offline capture queue. Server review is required before records apply.

Run with the backend virtualenv. Keys and API tokens are supplied through environment
variables and are never written into the local SQLite database.
"""
import argparse
import json
import os
import sqlite3
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from cryptography.fernet import Fernet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["enqueue", "sync", "status"])
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--server", required=True, help="HTTPS server origin, without /api")
    parser.add_argument("--node", type=int, required=True)
    args = parser.parse_args()
    parsed = urlsplit(args.server)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
        parser.error("--server must be an HTTPS origin without credentials or path")
    key = os.getenv("FACILITY_NODE_KEY")
    if not key:
        parser.error("FACILITY_NODE_KEY must contain a Fernet key stored separately from the database")
    cipher = Fernet(key.encode())
    os.umask(0o077)
    db = sqlite3.connect(args.database)
    args.database.chmod(0o600)
    with db:
        db.execute("CREATE TABLE IF NOT EXISTS binding (server TEXT NOT NULL, node INTEGER NOT NULL)")
        binding = db.execute("SELECT server, node FROM binding").fetchone()
        if binding and binding != (args.server.rstrip("/"), args.node):
            parser.error("This queue is bound to a different server or facility node")
        if not binding:
            db.execute("INSERT INTO binding VALUES (?, ?)", (args.server.rstrip("/"), args.node))
        db.execute("CREATE TABLE IF NOT EXISTS queue (change_id TEXT PRIMARY KEY, payload BLOB NOT NULL, status TEXT NOT NULL DEFAULT 'pending')")
    if args.command == "enqueue":
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict) or payload.get("kind") not in {"observation", "nursing_note"} or not payload.get("patient") or not isinstance(payload.get("payload"), dict):
            parser.error("stdin must contain patient, kind and payload")
        payload["change_id"] = str(uuid.uuid4())
        raw = json.dumps(payload, sort_keys=True).encode()
        if len(raw) > 32000:
            parser.error("Payload exceeds the offline capture limit")
        with db:
            db.execute("INSERT INTO queue (change_id, payload) VALUES (?, ?)", (payload["change_id"], cipher.encrypt(raw)))
        print(payload["change_id"])
    elif args.command == "status":
        print(json.dumps(dict(db.execute("SELECT status, COUNT(*) FROM queue GROUP BY status"))))
    else:
        token = os.getenv("FACILITY_NODE_ACCESS_TOKEN")
        if not token:
            parser.error("FACILITY_NODE_ACCESS_TOKEN is required for synchronization")
        submitted = 0
        with httpx.Client(timeout=20, follow_redirects=False, trust_env=False) as client:
            for change_id, encrypted in db.execute("SELECT change_id, payload FROM queue WHERE status = 'pending' ORDER BY rowid LIMIT 100").fetchall():
                payload = json.loads(cipher.decrypt(encrypted))
                response = client.post(f"{args.server.rstrip('/')}/api/v1/operations/offline-nodes/{args.node}/submit/",
                    headers={"Authorization": f"Bearer {token}"}, json=payload)
                if response.status_code not in {200, 201}:
                    # Do not print clinical payloads, access tokens, or provider error bodies.
                    print(f"Synchronization stopped: HTTP {response.status_code}; queued records retained.", file=sys.stderr)
                    return 1
                with db:
                    db.execute("UPDATE queue SET status = 'submitted' WHERE change_id = ?", (change_id,))
                submitted += 1
        print(json.dumps({"submitted_for_review": submitted}))
    db.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (httpx.HTTPError, ValueError, sqlite3.Error):
        print("Operation failed; queued records retained. Verify connectivity, configuration and encryption key.", file=sys.stderr)
        raise SystemExit(1)
