#!/usr/bin/env sh
set -eu

python manage.py migrate --noinput
python manage.py collectstatic --noinput

if [ "${LOAD_DEMO_DATA:-false}" = "true" ]; then
  python seed.py
fi

exec daphne -b "${ASGI_HOST:-0.0.0.0}" -p "${ASGI_PORT:-4000}" config.asgi:application
