"""step-results exit criterion 3: recognizing a step's result on the real model (`pytest -m live`).

Three replies after the question about the step «поговорити з трьома власниками кав'ярень»: one that it did
not work, one that it went unexpectedly, one about something else. Writes
.engine/artifacts/step-results/live.txt.
"""

import os
from pathlib import Path

import pytest

from thinkhow.facilitation import recognize_step
from thinkhow.platform.config import load_settings
from thinkhow.platform.llm import make_llm

OUT = Path(__file__).resolve().parents[2] / ".engine" / "artifacts" / "step-results" / "live.txt"
STEP = "поговорити з трьома власниками кав'ярень про оренду"
QUESTION = (
    f"Минулого разу ви обрали крок: «{STEP}». Як він вийшов і чи стало ясніше, що робити далі? Можна не "
    "відповідати — просто пишіть далі."
)
REPLIES = {
    "not_worked": "Не вийшло: ніхто з трьох не захотів говорити, тож я досі нічого не знаю про оренду.",
    "unexpected": (
        "Поговорив, але несподівано: оренда — дрібниця, усі скаржаться на брак персоналу. Стало трохи ясніше."
    ),
    "other": "Слухай, а скільки взагалі коштує хороша кавомашина для маленької кав'ярні?",
}


@pytest.mark.live
def test_the_model_recognizes_not_worked_unexpected_and_no_answer() -> None:
    environ = {**os.environ, "THINKHOW_LOCAL": "false", "THINKHOW_USERS_BUCKET": "-"}
    settings = load_settings(environ | {"THINKHOW_SYSTEM_BUCKET": "-", "THINKHOW_OWNER_EMAIL": "-"})
    llm = make_llm(settings, script=lambda *_: "")
    found = {key: recognize_step(STEP, QUESTION, text, llm) for key, text in REPLIES.items()}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        f"model: {settings.model}; region: {settings.location}\n"
        + "".join(f"{key}: {REPLIES[key]!r}\n  -> {found[key]!r}\n" for key in REPLIES),
        encoding="utf-8",
    )
    assert found["not_worked"].answered and found["not_worked"].outcome == "not_worked"
    assert found["unexpected"].answered and found["unexpected"].outcome == "unexpected"
    assert not found["other"].answered
