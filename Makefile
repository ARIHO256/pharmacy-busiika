.PHONY: backend-install backend-dev migrate seed test check frontend-install frontend-dev frontend-build dev

backend-install:
	cd backend && python3 -m pip install -r requirements.txt

migrate:
	cd backend && python3 manage.py migrate

seed:
	cd backend && python3 seed.py

check:
	cd backend && python3 manage.py check && python3 manage.py makemigrations --check --dry-run

test:
	cd backend && python3 manage.py test

frontend-install:
	cd frontend && npm ci

frontend-build:
	cd frontend && npm run build

backend-dev:
	cd backend && python3 manage.py runserver

frontend-dev:
	cd frontend && npm run dev

dev:
	@echo "Run in two terminals: make backend-dev and make frontend-dev"
