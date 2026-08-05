#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATIC_ONLY=false
KEEP_DATABASE=false
for arg in "$@"; do
  case "$arg" in
    --static-only) STATIC_ONLY=true ;;
    --keep-database) KEEP_DATABASE=true ;;
    *) echo "Unknown argument: $arg" >&2; exit 2 ;;
  esac
done

cd "$ROOT"
echo "[1/8] Static source, migration, role and route validation"
bash scripts/validate-static.sh

if "$STATIC_ONLY"; then
  echo "Static-only developer gate completed. This does not certify PostgreSQL, Docker, providers, soak testing, or human acceptance; run scripts/production-acceptance-gate.sh for promotion."
  exit 0
fi

PYTHON="${BACKEND_PYTHON:-}"
if [[ -z "$PYTHON" ]]; then
  if [[ -x backend/.venv/bin/python ]]; then PYTHON="backend/.venv/bin/python"; else PYTHON="python3"; fi
fi
if [[ "$PYTHON" == */* ]]; then
  PYTHON="$(cd "$(dirname "$PYTHON")" && pwd)/$(basename "$PYTHON")"
else
  PYTHON="$(command -v "$PYTHON" || true)"
fi
if [[ -z "$PYTHON" || ! -x "$PYTHON" ]]; then
  echo "Unable to resolve an executable Python interpreter." >&2
  exit 3
fi
if ! "$PYTHON" -c 'import django, rest_framework, channels, celery' >/dev/null 2>&1; then
  cat >&2 <<EOF
Backend dependencies are unavailable to $PYTHON.
Install backend/requirements.txt, then rerun scripts/release-gate.sh.
Use --static-only only when a restricted environment cannot download packages.
EOF
  exit 3
fi

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/healthpilot-release.XXXXXX")"
SERVER_PID=""
cleanup() {
  if [[ -n "${SERVER_PID:-}" ]]; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  if ! "$KEEP_DATABASE"; then rm -rf "$TMP_DIR"; else echo "Release database retained at $TMP_DIR"; fi
}
trap cleanup EXIT

export DJANGO_SETTINGS_MODULE=config.settings
export DJANGO_DEBUG=true
export DJANGO_SECRET_KEY="release-gate-only-not-for-production-$(date +%s)"
export DB_ENGINE=django.db.backends.sqlite3
export DB_NAME="$TMP_DIR/release.sqlite3"
export EMAIL_BACKEND=django.core.mail.backends.locmem.EmailBackend
export CLAMAV_ENABLED=false
export CLAMAV_REQUIRED=false
export REDIS_URL=""
export CACHE_URL=""
export CHANNEL_REDIS_URL=""
export USE_INMEMORY_CHANNEL_LAYER=true
export CELERY_TASK_ALWAYS_EAGER=true
export CELERY_TASK_EAGER_PROPAGATES=true
export MOCK_PAYMENTS=true
export SECURE_SSL_REDIRECT=false
export SESSION_COOKIE_SECURE=false
export CSRF_COOKIE_SECURE=false

pushd backend >/dev/null
echo "[2/8] Django configuration and migration drift"
"$PYTHON" manage.py check
"$PYTHON" manage.py makemigrations --check --dry-run

echo "[3/8] Clean database migration"
"$PYTHON" manage.py migrate --noinput

echo "[4/8] Full demonstration seed and coverage assertion"
"$PYTHON" seed.py
"$PYTHON" manage.py verify_demo_data

echo "[5/8] Django automated tests"
"$PYTHON" manage.py test --verbosity=1

echo "[6/8] Seeded 37-role login, context and API smoke test"
"$PYTHON" manage.py runserver 127.0.0.1:4010 --noreload >"$TMP_DIR/runserver.log" 2>&1 &
SERVER_PID=$!
for attempt in {1..30}; do
  if curl -fsS http://127.0.0.1:4010/readyz >/dev/null 2>&1; then break; fi
  sleep 1
done
python3 ../scripts/runtime-role-smoke.py --base http://127.0.0.1:4010/api
python3 ../scripts/http-load-smoke.py --base http://127.0.0.1:4010 --requests 50 --concurrency 5
kill "$SERVER_PID" 2>/dev/null || true
wait "$SERVER_PID" 2>/dev/null || true
SERVER_PID=""
popd >/dev/null

echo "[7/8] Frontend dependency lock and production build"
pushd frontend >/dev/null
npm ci
npm run build
popd >/dev/null

echo "[8/8] Container manifest validation"
if command -v docker >/dev/null 2>&1; then
  docker compose -f docker-compose.yml config >/dev/null
else
  echo "Docker is unavailable; YAML syntax passed in the static gate, but Docker Compose runtime validation was skipped."
fi

echo "Developer release gate passed. Production promotion still requires scripts/production-acceptance-gate.sh."
