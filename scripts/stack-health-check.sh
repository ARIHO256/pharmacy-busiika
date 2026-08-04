#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

command -v docker >/dev/null 2>&1 || { echo "Docker is required." >&2; exit 3; }

echo "Checking container health states"
docker compose ps --format json > /tmp/mydoctor-compose-ps.json
python3 - <<'PY'
import json
from pathlib import Path
raw=Path('/tmp/mydoctor-compose-ps.json').read_text().strip()
rows=[]
if raw:
    try: rows=json.loads(raw)
    except json.JSONDecodeError: rows=[json.loads(line) for line in raw.splitlines() if line.strip()]
if isinstance(rows, dict): rows=[rows]
errors=[]
for row in rows:
    name=row.get('Service') or row.get('Name')
    state=(row.get('State') or '').lower()
    health=(row.get('Health') or '').lower()
    if state not in {'running','exited'}: errors.append(f'{name}: state={state}')
    if health and health not in {'healthy',''}: errors.append(f'{name}: health={health}')
if errors: raise SystemExit('\n'.join(errors))
print(f'Compose states: {len(rows)} services inspected')
PY

curl -fsS http://127.0.0.1:4000/healthz >/dev/null
curl -fsS http://127.0.0.1:4000/readyz >/dev/null
curl -fsS http://127.0.0.1:3000/ >/dev/null
curl -fsS http://127.0.0.1:8025/api/v1/info >/dev/null
curl -fsS http://127.0.0.1:9090/-/ready >/dev/null
curl -fsS http://127.0.0.1:3001/api/health >/dev/null
FLOWER_AUTH="${FLOWER_BASIC_AUTH:-admin:change-me}"
curl -fsS -u "$FLOWER_AUTH" http://127.0.0.1:5555/ >/dev/null
curl -fsS -u "${ORTHANC_USERNAME:-mydoctor}:${ORTHANC_PASSWORD:-change-this-orthanc-password}" http://127.0.0.1:8042/system >/dev/null

docker compose exec -T postgres pg_isready -U "${POSTGRES_USER:-mydoctor}" -d "${POSTGRES_DB:-mydoctor}" >/dev/null
docker compose exec -T redis redis-cli -a "${REDIS_PASSWORD:-change-this-redis-password}" ping | grep -q PONG
docker compose exec -T rabbitmq rabbitmq-diagnostics -q ping >/dev/null
docker compose exec -T redpanda rpk cluster health --brokers=redpanda:9092 | grep -q 'Healthy:.*true'
docker compose exec -T clamav clamdscan --ping 1 >/dev/null
docker compose exec -T worker celery -A config inspect ping --timeout=15 | grep -q pong

echo "All application, worker, broker, storage, PACS, mail, and monitoring health checks passed."
