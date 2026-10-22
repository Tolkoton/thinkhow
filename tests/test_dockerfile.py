"""Seam 2 of skel-guards-deploy: the image the agent cannot build (no Docker daemon) is checked as text."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dockerfile_keeps_the_layout_the_code_expects() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    for line in (
        "FROM python:3.13-slim",
        "COPY src/ /app/src/",
        "COPY cards/ /app/cards/",
        "RUN uv sync --frozen --no-dev",
    ):
        assert line in text, line
    assert text.index("COPY pyproject.toml uv.lock") < text.index("RUN uv sync")
    assert "CMD exec uvicorn thinkhow.web.app:app" in text and "${PORT:-8080}" in text
    assert "USER thinkhow" in text


def test_dockerignore_keeps_secrets_out_and_the_code_in() -> None:
    patterns = (ROOT / ".dockerignore").read_text(encoding="utf-8").split()
    assert ".env*" in patterns and ".venv" in patterns and ".git" in patterns
    assert not {"src", "cards", "src/", "cards/"} & set(patterns)
