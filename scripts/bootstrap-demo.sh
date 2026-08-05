#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/backend"
python3 manage.py migrate --noinput
python3 seed.py
python3 manage.py verify_demo_data
python3 manage.py check
printf '\nDemo database ready.\nAdmin: admin@healthpilot.test / AdminPass!2026\nStandard accounts: DemoPass!2026\n'
