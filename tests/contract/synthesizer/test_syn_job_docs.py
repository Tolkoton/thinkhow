"""Contract tests of the Job command `synthesize` in local mode and of the documents (slice tester)."""

from pathlib import Path

import pytest
from syn_fakes import NOW, one_obs, write_cards

from thinkhow.knowledge import ChangeRecord, current
from thinkhow.learning.job import run
from thinkhow.platform.storage import LocalStorage

REPO = Path(__file__).resolve().parents[3]


def environ(root: Path) -> dict[str, str]:
    return {
        "THINKHOW_LOCAL": "true",
        "THINKHOW_LOCAL_DIR": str(root),
        "THINKHOW_OWNER_EMAIL": "owner@localhost",
    }


def test_the_job_synthesize_in_local_mode_applies_the_scripted_facilitator_note(tmp_path: Path) -> None:
    root = tmp_path / "local"
    cards = write_cards(tmp_path / "cards")
    assert run(["seed"], environ(root), cards, lambda: NOW) == 0
    storage = LocalStorage(root)
    first = one_obs(storage, "tp-1", 1, "знахідка-1")
    second = one_obs(storage, "tp-2", 1, "знахідка-2")
    assert run(["synthesize"], environ(root), cards, lambda: NOW) == 0
    now = current(storage)
    assert now.rev == 2
    assert len(now.memory) == 1
    made = now.memory[0]
    assert made.audience == "facilitator"
    assert len(made.cards) == 1 and made.cards[0] in {"alpha", "beta", "gamma"}
    raw = storage.read("system", "knowledge/changes/000002.json")
    assert raw is not None
    record = ChangeRecord.model_validate_json(raw)
    assert record.by == "synthesizer"
    assert len(record.observations) == 1 and record.observations[0] in {first.id, second.id}
    assert storage.list("system", "learning/synthesis/") != []
    assert run(["synthesize"], environ(root), cards, lambda: NOW) == 0  # nothing new: nothing written
    assert current(storage).rev == 2


def test_the_job_usage_names_synthesize(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(["nonsense"], environ(tmp_path), REPO / "cards", lambda: NOW) == 2
    assert "seed|cards|analyze|synthesize" in capsys.readouterr().err


def test_the_deploy_documents_have_the_daily_synthesize_schedule() -> None:
    deploy = (REPO / "docs" / "deploy.md").read_text(encoding="utf-8")
    sonko = (REPO / "docs" / "deploy-sonko.md").read_text(encoding="utf-8")
    assert "thinkhow-synthesize-daily" in deploy
    assert "thinkhow-synthesize-daily" in sonko
    step = deploy[deploy.index("thinkhow-synthesize-daily") :][:1500]
    assert "args" in step
    assert "synthesize" in step.replace("thinkhow-synthesize-daily", "")


def test_the_architecture_documents_say_the_synthesizer_runs_daily() -> None:
    index = (REPO / ".engine" / "architecture" / "INDEX.md").read_text(encoding="utf-8")
    f12 = [line for line in index.splitlines() if line.startswith("| F12 ")]
    assert len(f12) == 1
    assert "щоденне (задача 309)" in f12[0]
    assert "тижневе" not in f12[0]
    amap = (REPO / ".engine" / "architecture" / "architecture-map.md").read_text(encoding="utf-8")
    sched = [line for line in amap.splitlines() if "sched[" in line and "синтезатор" in line]
    assert len(sched) == 1
    assert "щодня" in sched[0]
    assert "щотижня" not in sched[0]
