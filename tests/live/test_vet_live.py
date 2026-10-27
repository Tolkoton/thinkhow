"""knowledge-versions exit criterion 3 (PR-32): the person-details check on the real model (`pytest -m live`).

Writes what the model answered to .engine/artifacts/knowledge-versions/vet-live.txt.
"""

import os
from pathlib import Path

import pytest

from thinkhow.knowledge import MemoryRecord
from thinkhow.learning.vet import vet_with
from thinkhow.platform.config import load_settings
from thinkhow.platform.llm import make_llm

OUT = Path(__file__).resolve().parents[2] / ".engine" / "artifacts" / "knowledge-versions" / "vet-live.txt"
PERSONAL = MemoryRecord(
    id="pre-mortem-facilitator",
    title="Втрата грошей на першому запуску",
    cards=["pre-mortem"],
    noticed="Олена з Львова втратила 3000 € на запуску кав'ярні на Площі Ринок, бо не перевірила оренду.",
    do="Питай про оренду одразу.",
    basis="розмова від 12 жовтня",
)
GENERAL = MemoryRecord(
    id="pre-mortem-facilitator",
    title="Коли людина не може уявити провалу",
    cards=["pre-mortem"],
    noticed="Люди, що вже вклали гроші в план, часто не можуть назвати жодної причини провалу.",
    do="Запропонуй уявити, що минув рік і план провалився, і спитай, яка новина про це була б першою.",
    basis="Klein G. Performing a Project Premortem. HBR, 2007",
)


@pytest.mark.live
def test_the_model_refuses_a_note_with_a_persons_details_and_lets_a_general_one_pass() -> None:
    environ = {**os.environ, "THINKHOW_LOCAL": "false", "THINKHOW_USERS_BUCKET": "-"}
    settings = load_settings(environ | {"THINKHOW_SYSTEM_BUCKET": "-", "THINKHOW_OWNER_EMAIL": "-"})
    vet = vet_with(make_llm(settings, script=lambda *_: ""))
    personal, general = vet([PERSONAL]), vet([GENERAL])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        f"model: {settings.model}; region: {settings.location}\n"
        f"personal note -> {personal!r}\ngeneral note -> {general!r}\n",
        encoding="utf-8",
    )
    assert personal is not None
    assert general is None
