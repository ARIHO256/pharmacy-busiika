# Public Landing Page and Local Port Configuration

## What changed

The React application now exposes a public marketing website at `/` instead of immediately redirecting unauthenticated visitors to the sign-in page.

The design is inspired by the supplied premium dark marketplace reference, but it has been rebuilt specifically for MyDoctor and does not copy the original page content or imagery.

### Landing-page sections

- Responsive dark connected-health navigation
- Healthcare-focused hero and original local SVG clinician artwork
- Appointment, consultation, health-record and privacy status cards
- Animated healthcare capability ticker
- Connected service catalogue
- Patient care journey and privacy features
- Healthcare network visualisation
- Provider call to action
- Final account-creation call to action
- Responsive footer

### Application routes

- `/` — public MyDoctor landing page
- `/dashboard` — sends an authenticated user to the correct role portal
- `/login` — sign in
- `/register` — patient or provider registration
- `/patient`, `/doctor`, `/pharmacy`, `/lab`, `/hospital`, `/insurance`, `/admin` — existing protected portals

## Local development ports

### React and Vite

Vite is configured in `frontend/vite.config.js` to run on:

```text
http://localhost:3000
```

The development proxy sends `/api` and `/media` requests to Django on port 4000.

### Django

`backend/manage.py` adds `0.0.0.0:4000` when `runserver` is called without an explicit address or port:

```bash
cd backend
python manage.py runserver
```

To override it:

```bash
python manage.py runserver 127.0.0.1:4500
```

or set:

```bash
DJANGO_RUNSERVER_ADDRPORT=127.0.0.1:4500
```

### CORS and CSRF

Django's development defaults and `.env.example` now trust:

```text
http://localhost:3000
http://127.0.0.1:3000
```

## Start both applications

After installing backend and frontend dependencies:

```bash
./start-dev.sh
```

The script starts React on port 3000 and Django on port 4000, and stops both processes when the script exits.

## Main implementation files

```text
frontend/src/pages/LandingPage.jsx
frontend/src/pages/LandingPage.css
frontend/src/assets/doctor-hero.svg
frontend/src/App.jsx
frontend/vite.config.js
backend/config/settings.py
backend/manage.py
start-dev.sh
```
