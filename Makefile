.PHONY: backend-install backend-dev migrate seed demo test check validate release-gate frontend-install frontend-dev frontend-build docker-up docker-down dev postgres-gate production-gate stack-health

backend-install:
	cd backend && python3 -m pip install -r requirements.txt

migrate:
	cd backend && python3 manage.py migrate

seed:
	cd backend && python3 seed.py

demo:
	./scripts/bootstrap-demo.sh

validate:
	./scripts/validate-static.sh

release-gate:
	./scripts/release-gate.sh

check:
	cd backend && python3 manage.py check && python3 manage.py makemigrations --check --dry-run

test:
	cd backend && python3 manage.py test

frontend-install:
	cd frontend && npm ci

frontend-build:
	cd frontend && npm run build

backend-dev:
	cd backend && python3 manage.py runserver 4000

frontend-dev:
	cd frontend && npm run dev

dev:
	@echo "Run in two terminals: make backend-dev and make frontend-dev"

docker-up:
	docker compose up --build

docker-down:
	docker compose down

postgres-gate:
	./scripts/postgres-runtime-gate.sh

stack-health:
	./scripts/stack-health-check.sh

production-gate:
	./scripts/production-acceptance-gate.sh
