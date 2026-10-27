"""The image and the deploy documents of starting-notes (slice tester): checked as text."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
NOTES_ARGS = re.compile(r"--args=\S*,notes(?![\w-])")


def test_the_dockerfile_copies_the_notes_folder() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY notes/ /app/notes/" in text


def test_the_deploy_documents_run_the_job_notes_once_after_seed_and_cards() -> None:
    deploy = (ROOT / "docs" / "deploy.md").read_text(encoding="utf-8")
    sonko = (ROOT / "docs" / "deploy-sonko.md").read_text(encoding="utf-8")
    found = NOTES_ARGS.search(deploy)
    assert found, "docs/deploy.md has no `--args …,notes` step"
    assert deploy.index("thinkhow.learning.job,seed") < found.start()
    assert deploy.index("thinkhow.learning.job,cards") < found.start()
    assert NOTES_ARGS.search(sonko) or "thinkhow.learning.job,notes" in sonko, (
        "docs/deploy-sonko.md has no `--args …,notes` step"
    )
