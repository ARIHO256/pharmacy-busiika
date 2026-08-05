#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RELEASE_VERSION="${RELEASE_VERSION:-$(date +%Y.%m.%d)}"
SOAK_HOURS="${SOAK_HOURS:-4}"
KEEP_STACK="${KEEP_STACK:-false}"
SAFE_RELEASE="$(printf %s "$RELEASE_VERSION" | tr -cd "[:alnum:]_")"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-healthpilot_acceptance_${SAFE_RELEASE}}"

cd "$ROOT"
command -v docker >/dev/null 2>&1 || { echo "Docker is required for the production acceptance gate." >&2; exit 3; }
docker compose version >/dev/null

cleanup() {
  if [[ "$KEEP_STACK" != "true" ]]; then docker compose down --volumes --remove-orphans >/dev/null 2>&1 || true; fi
}
trap cleanup EXIT

echo "[1/12] Static architecture, role, route and workflow completion audits"
bash scripts/validate-static.sh
python3 scripts/workflow-completion-audit.py
python3 scripts/authorization-audit.py
node scripts/frontend-acceptance.mjs

echo "[2/12] Build every service image in an isolated Compose project"
docker compose down --volumes --remove-orphans >/dev/null 2>&1 || true
docker compose build --pull

echo "[3/12] Start PostgreSQL and infrastructure dependencies"
docker compose up -d postgres redis minio minio-init clamav orthanc redpanda rabbitmq mailpit
for attempt in {1..90}; do
  if docker compose exec -T postgres pg_isready -U "${POSTGRES_USER:-healthpilot}" -d "${POSTGRES_DB:-healthpilot}" >/dev/null 2>&1; then break; fi
  sleep 2
done
docker compose exec -T postgres pg_isready -U "${POSTGRES_USER:-healthpilot}" -d "${POSTGRES_DB:-healthpilot}"

echo "[4/12] Clean PostgreSQL migration, drift check and demonstration seed"
docker compose run --rm backend python manage.py check --deploy
docker compose run --rm backend python manage.py makemigrations --check --dry-run
docker compose run --rm backend python manage.py migrate --noinput
docker compose run --rm backend python seed.py
docker compose run --rm backend python manage.py verify_demo_data

echo "[5/12] Full backend suite with organization and privilege isolation"
docker compose run --rm backend python manage.py test --verbosity=2

echo "[6/12] Start the complete platform"
docker compose up -d
for attempt in {1..120}; do
  if curl -fsS http://127.0.0.1:4000/readyz >/dev/null 2>&1 && curl -fsS http://127.0.0.1:3000 >/dev/null 2>&1; then break; fi
  sleep 2
done
curl -fsS http://127.0.0.1:4000/readyz >/dev/null
curl -fsS http://127.0.0.1:3000 >/dev/null
bash scripts/stack-health-check.sh

echo "[7/12] Every seeded role login and active-context smoke"
python3 scripts/runtime-role-smoke.py --base http://127.0.0.1:4000/api

echo "[8/12] Browser journeys, button persistence, accessibility, responsive, print and offline"
python3 tests/e2e/playwright_acceptance.py --base http://127.0.0.1:3000

echo "[9/12] Provider sandbox configuration and harmless connectivity"
python3 scripts/provider-sandbox-check.py

echo "[10/12] Backup and restore exercise"
docker compose run --rm backend python manage.py backup_platform --reason "release-$RELEASE_VERSION"
docker compose run --rm backend python manage.py verify_backup --latest

echo "[11/12] Multi-service soak for ${SOAK_HOURS} hours"
python3 scripts/soak-test.py --base http://127.0.0.1:4000/api --hours "$SOAK_HOURS"
bash scripts/stack-health-check.sh

echo "[12/12] Formal human/legal/clinical/security release acceptance"
docker compose exec -T backend python manage.py verify_production_readiness --release "$RELEASE_VERSION" --environment production

echo "Production acceptance gate passed for $RELEASE_VERSION."
