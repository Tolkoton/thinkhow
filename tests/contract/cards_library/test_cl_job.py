"""Contract tests of cards-library: the Job command `cards`, Goal 2 on the real `cards/`, docs/deploy.md §7.
Slice tester; written from the contract, not the code."""

import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cl_fakes import (
    REPO,
    REPO_CARDS,
    LogCapture,
    change_files,
    install_log_capture,
    local_environ,
    new_change,
    snapshot,
    write_cards,
)

from thinkhow.knowledge import KnowledgeMissing, card_prompt, current, seed
from thinkhow.learning.job import run
from thinkhow.platform.storage import LocalStorage

NOW = datetime(2026, 10, 24, 12, 0, 0, tzinfo=UTC)
GOAL_IDS = [
    "first-principles", "issue-tree", "complexity-sensemaking", "five-whys", "is-is-not", "wrap-decision",
    "weighted-matrix", "reversible-doors", "evaporating-cloud", "pre-mortem", "consider-opposite",
    "socratic-questioning", "scamper", "mental-contrasting", "reflective-cycle", "goal-to-plan",
    "jobs-to-be-done", "opportunity-tree",
    # Task 307, product-cards «Goal» 1: «рівно 25 файлів: 18 id задачі 302 і 7 id вище» (objection 1).
    "customer-interviews", "demand-test", "positioning", "offer-design", "value-pricing", "traction-channels",
    "unit-economics",
]  # fmt: skip


@pytest.fixture
def logs(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> LogCapture:
    return install_log_capture(monkeypatch, capsys)


def test_job_cards_logs_cards_published_with_rev_and_returns_0_then_rev_null(
    tmp_path: Path, logs: LogCapture
) -> None:
    root = tmp_path / "local"
    assert seed(LocalStorage(root), write_cards(tmp_path / "c1", {"alpha": "Альфа"})) is True
    folder = write_cards(tmp_path / "c2", {"alpha": "Альфа нова", "beta": "Бета"})
    assert run(["cards"], local_environ(root), folder, lambda: NOW) == 0
    assert run(["cards"], local_environ(root), folder, lambda: NOW) == 0
    published = logs.events("cards_published")
    assert len(published) == 2
    assert "rev" in published[0] and "rev" in published[1]
    assert published[0]["rev"] == 2
    assert published[1]["rev"] is None


def test_job_cards_on_unseeded_knowledge_does_not_catch_knowledge_missing(
    tmp_path: Path, logs: LogCapture
) -> None:
    folder = write_cards(tmp_path / "c", {"alpha": "Альфа"})
    with pytest.raises(KnowledgeMissing):
        run(["cards"], local_environ(tmp_path / "local"), folder, lambda: NOW)


def test_job_usage_names_seed_cards_analyze(tmp_path: Path, logs: LogCapture) -> None:
    assert run(["frobnicate"], local_environ(tmp_path), REPO_CARDS, lambda: NOW) == 2
    assert "seed|cards|analyze" in logs.err()


def test_goal2_revision_1_with_pre_mortem_becomes_revision_2_with_18_cards_and_the_same_pre_mortem_file(
    tmp_path: Path, logs: LogCapture
) -> None:
    root = tmp_path / "local"
    only_pre_mortem = tmp_path / "rev1"
    only_pre_mortem.mkdir()
    shutil.copy(REPO_CARDS / "pre-mortem.yaml", only_pre_mortem / "pre-mortem.yaml")
    store = LocalStorage(root)
    assert seed(store, only_pre_mortem) is True
    before = change_files(store)
    assert run(["cards"], local_environ(root), REPO_CARDS, lambda: NOW) == 0
    now = current(store)
    assert now.rev == 2
    assert sorted(now.cards) == sorted(GOAL_IDS)
    assert new_change(store, before).cards["pre-mortem"] == "knowledge/cards/pre-mortem/v1.json"
    assert all(card_prompt(card).strip() for card in now.cards.values())
    files = snapshot(root)
    assert run(["cards"], local_environ(root), REPO_CARDS, lambda: NOW) == 0
    assert snapshot(root) == files
    assert [line["rev"] for line in logs.events("cards_published")] == [2, None]


def section_7() -> str:
    doc = (REPO / "docs" / "deploy.md").read_text(encoding="utf-8")
    start = doc.index("\n## 7.")
    end = doc.index("\n## 8.", start)
    return doc[start:end]


def test_deploy_doc_section_7_runs_cards_after_seed_then_restarts_the_service() -> None:
    text = section_7()
    assert "thinkhow.learning.job,seed" in text
    assert "thinkhow.learning.job,cards" in text
    after_seed = text.index("thinkhow.learning.job,seed")
    cards_at = text.index("thinkhow.learning.job,cards")
    assert cards_at > after_seed
    rest = text[cards_at:]
    assert re.search(r"перезапус", rest, re.IGNORECASE), "no words about restarting the service after `cards`"
    assert "cards_published" in text
