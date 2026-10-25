"""Live tests of facilitator-free-mode (`-m live`): two whole conversations through the product, real model.

A — the person's seven turns of the owner's topic t-d824f508a729 (no plan yet): the facilitator says at most
once that the card does not fit, names no method and leads in free mode. B — the first five turns of PoC 101
(a plan and a deadline): Pre-mortem goes by its phases. Each run writes its whole conversation to
.engine/artifacts/spikes/ and never overwrites an earlier one; one run each, no re-run for a PASS.
The detectors (Seam 5) are tested here too, without the `live` mark, so the ordinary run checks them.
"""

import functools
import json
import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from thinkhow.access import CurrentUser
from thinkhow.facilitation import respond
from thinkhow.knowledge import current, seed
from thinkhow.platform.config import load_settings
from thinkhow.platform.llm import make_llm
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import Answered, Delta, TopicRef, create_topic, reply, set_language

ROOT = Path(__file__).resolve().parents[2]
CARDS = ROOT / "cards"
SPIKES = ROOT / ".engine" / "artifacts" / "spikes"
POC_SESSION = ROOT / "sketches" / "gemini-eu" / "runs" / "session.jsonl"

SENTENCE = re.compile(r"[^.?!]+")
CHANGE = re.compile(r"змін\w*\s+(метод|підхід)|інш\w*\s+(метод|підхід)", re.I)
SUBJECT = re.compile(r"метод|підхід|картк", re.I)
DOES_NOT_FIT = re.compile(r"не\s+(підх|підій|підійш|пасу|годит|працю|спрацю|допомож)", re.I)
METHOD_NAME = re.compile(
    r"мортем|mortem|\bWRAP\b|зважен\w*\s+матриц|матриц\w*\s+рішень|мозков\w*\s+штурм|backcasting|SCAMPER|PDCA|WOOP",
    re.I,
)

# The owner's topic t-d824f508a729, verbatim: the person's turns #1, #3, …, #13 and the facilitator's
# old answers #2–#14 (each of them announced «час змінити метод»).
OWNER_TOPIC = json.loads(
    (ROOT / "tests" / "fixtures" / "facilitator_free_mode" / "owner_topic.json").read_text("utf-8")
)
OWNER_TURNS: list[str] = OWNER_TOPIC["person_turns"]
OLD_ANSWERS: list[str] = OWNER_TOPIC["old_answers"]


def announces(reply_text: str) -> bool:
    """A sentence says the method or approach does not fit, or that it is time to change it (Seam 5)."""
    return any(
        CHANGE.search(s) or (SUBJECT.search(s) and DOES_NOT_FIT.search(s))
        for s in SENTENCE.findall(reply_text)
    )


def names_a_method(reply_text: str) -> bool:
    return METHOD_NAME.search(reply_text) is not None


def test_every_old_answer_of_the_owners_topic_announces() -> None:
    assert all(announces(a) for a in OLD_ANSWERS)


@pytest.mark.parametrize(
    "text",
    [
        "час змінити метод з Pre-mortem на WRAP",
        "цей підхід зараз не підходить",
        "Цей підхід зараз не підійде, бо плану ще немає.",
        "Зараз цей метод нам не допоможе.",
        "Тут потрібен інший підхід до вибору.",
    ],
)
def test_announcing_sentences_are_caught(text: str) -> None:
    assert announces(text)


@pytest.mark.parametrize("text", ["зважену матрицю рішень", "примортем", "мозковий штурм"])
def test_method_names_are_caught(text: str) -> None:
    assert names_a_method(text)


@pytest.mark.parametrize(
    "text",
    [
        "Які з ідей вам не підходять?",
        "Які ще є інші способи заробити?",
        "Інший спосіб оцінити — порахувати години на тиждень; спробуємо?",
        "Можна оцінити так: складіть таблицю варіантів і критеріїв",
        "один зі способів (методів) оцінки — …",
        "складіть матрицю: варіанти × критерії",
    ],
)
def test_ordinary_free_mode_sentences_are_not_caught(text: str) -> None:
    assert not announces(text)
    assert not names_a_method(text)


def _conversation(tmp_path: Path, turns: list[str]) -> list[tuple[str, str, str | None]]:
    """Flow: seed → a person (uk-UA) → a topic → each turn by workspace.reply → (turn, answer, phase)."""
    storage = LocalStorage(tmp_path)
    seed(storage, CARDS)
    environ = {
        **os.environ,
        "THINKHOW_LOCAL": "false",
        "THINKHOW_USERS_BUCKET": "-",
        "THINKHOW_SYSTEM_BUCKET": "-",
        "THINKHOW_OWNER_EMAIL": "-",
    }
    llm = make_llm(load_settings(environ), script=lambda *_: "")
    facilitate = functools.partial(respond, knowledge=current(storage), llm=llm)
    user = CurrentUser(id="live-person", email="live@example.com", is_owner=False)
    set_language(storage, user, "uk-UA")
    now = datetime(2026, 10, 24, 8, 0, tzinfo=UTC)
    ref = TopicRef(user.id, create_topic(storage, user, "Жива розмова", now))
    rows: list[tuple[str, str, str | None]] = []
    for text in turns:
        now += timedelta(minutes=1)
        events = list(reply(storage, facilitate, user, ref, text, now))
        assert isinstance(events[-1], Answered), events[-1]
        answer = "".join(e.text for e in events if isinstance(e, Delta))
        problem_map = json.loads(storage.read("users", f"{ref.uid}/{ref.topic_id}/map.json") or b"{}")
        rows.append((text, answer, problem_map["phase_id"]))
    return rows


def _write(name: str, title: str, rows: list[tuple[str, str, str | None]]) -> Path:
    """The whole conversation into a new file; an earlier run's file is never overwritten."""
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    path = SPIKES / f"facilitator-free-mode-live-{name}-{stamp}.md"
    lines = [f"# {title}", "", f"Прогін {stamp}, модель — справжня (Vertex, eu), шлях — workspace.reply.", ""]
    for n, (text, answer, phase) in enumerate(rows, 1):
        lines += [
            f"## Репліка {n}",
            "",
            f"**Людина:** {text}",
            "",
            f"**Фасилітатор** (фаза: `{phase}`): {answer}",
            "",
        ]
    with path.open("x", encoding="utf-8") as out:
        out.write("\n".join(lines))
    return path


@pytest.mark.live
def test_A_owners_topic_without_a_plan_goes_free_mode_and_announces_at_most_once(tmp_path: Path) -> None:
    rows = _conversation(tmp_path, OWNER_TURNS)
    print(_write("A", "Live A — тема власника t-d824f508a729, репліки людини #1–#13", rows))
    answers = [answer for _, answer, _ in rows]
    phases = [phase for _, _, phase in rows]
    announced = [i for i, a in enumerate(answers) if announces(a)]
    first_free = next((i for i, p in enumerate(phases) if p is None), None)
    assert len(announced) <= 1, announced
    assert announced in ([], [first_free]), (announced, first_free)
    # task 205 (owner, 2026-10-25): the facilitator names methods; task 301's «no method names» is gone
    for i in (3, 4):  # the answers to #7 and #9
        assert not ("участ" in answers[i].lower() and "продаж" in answers[i].lower()), answers[i]
    assert not [a for a in answers if "як ви хочете продовжити" in a.lower()]
    assert phases[6] is None


@pytest.mark.live
def test_B_a_plan_with_a_deadline_goes_by_the_pre_mortem_phases(tmp_path: Path) -> None:
    poc = [json.loads(line) for line in POC_SESSION.read_text(encoding="utf-8").splitlines()]
    turns = [row["user"] for row in sorted(poc, key=lambda r: r["turn"]) if 1 <= row["turn"] <= 5]
    rows = _conversation(tmp_path, turns)
    print(_write("B", "Live B — план і строк (PoC 101, репліки людини 1–5)", rows))
    order = ["phase_1_time_travel", "phase_2_blind_spots", "phase_3_triage", "phase_4_mitigation_tripwires"]
    phases = [phase for _, _, phase in rows]
    assert all(p in order for p in phases), phases
    indices = [order.index(p) for p in phases if p is not None]
    assert indices == sorted(indices), phases
    assert phases[-1] != "phase_1_time_travel", phases
    assert not [a for _, a, _ in rows if announces(a) or names_a_method(a)]
