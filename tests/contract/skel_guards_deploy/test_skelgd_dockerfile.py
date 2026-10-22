"""Contract tests of skel-guards-deploy: the `Dockerfile` and `.dockerignore`, read statically (slice tester;
from the contract). Seam 2: the agent cannot build the image, so what the contract
names is checked in the files.
"""

import re

from skelgd_files import dockerfile_instructions, env_values, ignored, without_flags


def test_the_image_is_based_on_python_3_13_slim() -> None:
    froms = [without_flags(args)[0] for word, args in dockerfile_instructions() if word == "FROM"]
    assert froms, "no FROM"
    assert froms[-1] == "python:3.13-slim" or froms[-1].startswith(
        ("python:3.13-slim@", "python:3.13-slim ")
    ), froms


def test_uv_is_copied_from_the_official_image_and_nothing_is_piped_into_a_shell() -> None:
    ins = dockerfile_instructions()
    assert any(word == "COPY" and "--from=ghcr.io/astral-sh/uv" in args for word, args in ins)
    assert not any(
        word == "RUN" and "curl" in args and re.search(r"\|\s*(ba)?sh\b", args) for word, args in ins
    )


def test_pyproject_and_lock_are_copied_before_a_frozen_no_dev_uv_sync() -> None:
    ins = dockerfile_instructions()
    sync = [
        i
        for i, (w, a) in enumerate(ins)
        if w == "RUN" and "uv sync" in a and "--frozen" in a and "--no-dev" in a
    ]
    assert sync, "no RUN uv sync --frozen --no-dev"
    copied = {
        src for w, a in ins[: sync[0]] if w == "COPY" and "--from" not in a for src in without_flags(a)[:-1]
    }
    assert {"pyproject.toml", "uv.lock"} <= {s.removeprefix("./") for s in copied}, copied


def test_src_and_cards_are_copied_by_two_instructions_verbatim() -> None:
    copies = [without_flags(a) for w, a in dockerfile_instructions() if w == "COPY"]
    assert ["src/", "/app/src/"] in copies
    assert ["cards/", "/app/cards/"] in copies


def test_env_sets_pythonpath_path_and_the_two_uv_values() -> None:
    env = env_values(dockerfile_instructions())
    assert env.get("PYTHONPATH") == "/app/src"
    assert env.get("PATH", "").startswith("/app/.venv/bin:")
    assert env.get("UV_PYTHON_DOWNLOADS") == "never"
    assert env.get("UV_LINK_MODE") == "copy"


def test_the_image_runs_as_a_user_that_is_not_root() -> None:
    users = [a.split()[0] for w, a in dockerfile_instructions() if w == "USER"]
    assert users, "no USER"
    assert users[-1].split(":")[0] not in ("root", "0")


def test_cmd_execs_uvicorn_on_the_web_app_and_the_cloud_run_port() -> None:
    cmds = [a for w, a in dockerfile_instructions() if w == "CMD"]
    assert cmds, "no CMD"
    cmd = cmds[-1]
    assert re.search(r"\bexec\s+uvicorn\b", cmd), cmd
    assert "thinkhow.web.app:app" in cmd
    assert "--host 0.0.0.0" in cmd
    assert "${PORT:-8080}" in cmd


def test_dockerignore_excludes_secrets_venv_git_and_the_named_dirs() -> None:
    for path in (
        ".env",
        ".env.local",
        ".venv",
        ".git",
        ".engine",
        ".claude",
        "tests",
        "sketches",
        "tasks",
        "docs",
        ".local-data",
    ):
        assert ignored(path), path


def test_dockerignore_does_not_exclude_src_or_cards() -> None:
    for path in ("src", "src/thinkhow", "src/thinkhow/web/app.py", "cards", "cards/pre-mortem.yaml"):
        assert not ignored(path), path
