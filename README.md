# Eurovibe

Eurovibe is a Django SSR web app for Eurovision-style friend voting. The current repo state is the Foundation slice: Django project bootstrap, env-based settings, static files, base layout, and health check.

## Requirements

For local development without Docker:

- Python 3.14
- Node.js 24 or newer
- npm

For Docker development:

- Docker
- Docker Compose

## Local Setup

Create a virtual environment and install Python dependencies:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Install frontend dependencies and build the compiled CSS:

```bash
npm install
npm run build:css
```

Create a local env file:

```bash
cp .env.example .env
```

The default `.env.example` uses SQLite, which is enough for local Foundation checks. Django settings are read from these variables:

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `DATABASE_URL`
- `DJANGO_CSRF_TRUSTED_ORIGINS`

Run migrations:

```bash
.venv/bin/python manage.py migrate
```

Start the development server:

```bash
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

Open:

- App: http://127.0.0.1:8000/
- Health check: http://127.0.0.1:8000/healthz/

## Docker Setup

Build and start Django plus Postgres:

```bash
docker compose up --build
```

The compose setup:

- builds Tailwind CSS during the image build;
- installs Python dependencies;
- starts a Postgres 17 container;
- runs `python manage.py migrate`;
- starts Django on `0.0.0.0:8000`.

Open:

- App: http://127.0.0.1:8000/
- Health check: http://127.0.0.1:8000/healthz/

If port `8000` is already in use, pick another host port:

```bash
WEB_PORT=8001 docker compose up --build
```

Then open:

- App: http://127.0.0.1:8001/
- Health check: http://127.0.0.1:8001/healthz/

Stop containers:

```bash
docker compose down
```

Stop containers and remove the local Postgres volume:

```bash
docker compose down -v
```

## Useful Commands

Run Django checks:

```bash
.venv/bin/python manage.py check
```

Collect static files locally:

```bash
.venv/bin/python manage.py collectstatic --noinput
```

Rebuild CSS after editing `assets/css/app.css` or templates:

```bash
npm run build:css
```

Run a one-off Django command inside Docker:

```bash
docker compose run --rm web python manage.py check
```

Run migrations inside Docker:

```bash
docker compose run --rm web python manage.py migrate
```

## Deployment Notes

`render.yaml` contains the Render skeleton. It expects:

- a web service running `gunicorn eurovibe.wsgi:application`;
- managed Postgres exposed through `DATABASE_URL`;
- `DJANGO_DEBUG=False`;
- a generated `DJANGO_SECRET_KEY`;
- `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` set for the Render domain.

No secrets should be committed. Keep real values in `.env`, Docker/Compose environment, or the hosting provider environment.
