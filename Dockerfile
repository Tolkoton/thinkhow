# One image for the Cloud Run service (CMD) and the Cloud Run Job (`--command python --args -m,thinkhow.learning.job,…`).
# Built by Cloud Build: `gcloud builds submit` (docs/deploy.md, step 5).
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV PYTHONPATH=/app/src PATH=/app/.venv/bin:$PATH UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv PYTHONUNBUFFERED=1
WORKDIR /app

COPY pyproject.toml uv.lock /app/
RUN uv sync --frozen --no-dev

COPY src/ /app/src/
COPY cards/ /app/cards/
COPY notes/ /app/notes/

RUN useradd --system --uid 10001 thinkhow
USER thinkhow

CMD exec uvicorn thinkhow.web.app:app --host 0.0.0.0 --port ${PORT:-8080}
