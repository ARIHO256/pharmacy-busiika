#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
command -v docker >/dev/null 2>&1 || { echo "Docker required" >&2; exit 3; }
docker compose up -d postgres redis
docker compose run --rm backend python manage.py check
docker compose run --rm backend python manage.py makemigrations --check --dry-run
docker compose run --rm backend python manage.py migrate --noinput
docker compose run --rm backend python seed.py
docker compose run --rm backend python manage.py verify_demo_data
docker compose run --rm backend python manage.py test --verbosity=1
