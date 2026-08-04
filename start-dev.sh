#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

if [[ ! -d "$BACKEND_DIR/.venv" ]]; then
  echo "Backend virtual environment not found. Run:"
  echo "  cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  echo "Frontend dependencies not found. Run:"
  echo "  cd frontend && npm install"
  exit 1
fi

cleanup() {
  kill "${BACKEND_PID:-}" "${FRONTEND_PID:-}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

(
  cd "$BACKEND_DIR"
  source .venv/bin/activate
  python manage.py runserver 4000
) &
BACKEND_PID=$!

(
  cd "$FRONTEND_DIR"
  npm run dev
) &
FRONTEND_PID=$!

printf '\nMyDoctor development servers:\n'
printf '  React: http://localhost:3000\n'
printf '  Django: http://localhost:4000\n\n'

wait -n "$BACKEND_PID" "$FRONTEND_PID"
