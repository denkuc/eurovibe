# syntax=docker/dockerfile:1

FROM node:24-bookworm-slim AS frontend

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY assets ./assets
COPY eurovibe ./eurovibe
COPY templates ./templates
COPY tailwind.config.js ./
RUN npm run build:css


FROM python:3.14-slim AS app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_DEBUG=False
ENV DJANGO_SECRET_KEY=docker-build-secret

WORKDIR /app

RUN useradd --create-home --shell /usr/sbin/nologin appuser

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=frontend /app/static/css/app.css ./static/css/app.css

RUN python manage.py collectstatic --noinput

ENV DJANGO_SECRET_KEY=change-me-at-runtime

EXPOSE 8000

USER appuser

CMD ["gunicorn", "eurovibe.wsgi:application", "--bind", "0.0.0.0:8000"]
