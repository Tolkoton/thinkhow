"""Live run of task 306 (`-m live`): the owner's «не знаю» in t-84d1517cb1c1 again, through the product.

The topic is read at run time from the users bucket (ADC). Two runs, each through `workspace.reply` with the
router and `VertexLlm(search=True)`, as `web.app` runs them:

- At each «не знаю» (#5, #11, #15) — a local topic with the bucket's conversation, map items and router
  decisions before that turn, then the owner's turn verbatim: what the system does now where it asked again.
  The phase of the map then is not stored; it is read from the old answer before (#4 asks the result —
  `phase_1_outcome`; #10 and #14 ask the pains — `phase_2_opportunities`).
- From #1 — the owner's #1, #3, #5 verbatim, then a synthetic person (`gemini-3.5-flash`) who holds to the
  facts of the owner's turns, up to twelve turns of the person or the end of the card.

Whether the system moves to an assumption and a cheap test with a threshold is read by a person from the
record (`.engine/artifacts/unknown-live/<time>/`), not judged by code.
"""

import json
import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, Field

from thinkhow.access import CurrentUser
from thinkhow.facilitation import respond
from thinkhow.facilitation.types import ProblemMap
from thinkhow.knowledge import current, seed
from thinkhow.platform import llm as model
from thinkhow.platform.config import Settings, load_settings
from thinkhow.platform.llm import make_llm
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import Answered, Delta, TopicRef, create_topic, reply, set_language
from thinkhow.workspace import conversation as conv_file

ROOT = Path(__file__).resolve().parents[2]
CARDS = ROOT / "cards"
OUT = ROOT / ".engine" / "artifacts" / "unknown-live"
TOPIC = "gs://pocket-lawyer-431614-thinkhow-users/104839836105981044615/t-84d1517cb1c1"
USER = CurrentUser(id="live-person", email="live@example.com", is_owner=False)
IN_USD, OUT_USD = 2.2 / 1e6, 11 / 1e6  # PR-19, as in test_research_owner_live.py
PHASE_BEFORE = {5: "phase_1_outcome", 11: "phase_2_opportunities", 15: "phase_2_opportunities"}
VERBATIM = (1, 3, 5)
PERSON_TURNS = 12
PERSON = """Ти граєш людину, яка прийшла до асистента, що допомагає думати. Відповідай від першої особи, як
жива людина в чаті: коротко (одне-три речення), по суті питання асистента, українською. Не називай
способів думати.

# Твоя ситуація (з реплік власника)
Хочеш зробити для керівників невеликих підприємств і фрілансерів персонального асистента на
OpenClaw: курси, де ведеш людину за ручку, поки вона його піднімає й налаштовує, а в пакеті —
думальний асистент і твої фреймворки та скіли: написання сайтів, аналіз офера, побудова лендінгу,
щоб швидко тестувати маркетингові ідеї. Асистент тримає в пам'яті контекст довгих переговорів,
робить транскрипти зустрічей, задачі в Trello, документи, веде Google Диск, малює, робить
відеопрезентації й дослідження. Твоє припущення: усі говорять про ШІ, а як ним толком користуватись,
ніхто не знає, тож керівник має почати користуватись ним сам; асистент вивільняє руки від механічної
роботи до творчої. Розмов із клієнтами в тебе ще не було.

# Як відповідати
- На питання, що може показати лише реальність (що болить клієнтам, яка біль для них головна, чи
  купить хтось, яку ціль ставити), чесно кажи, що не знаєш і це якраз треба з'ясувати.
- Коли асистент пропонує конкретне значення, гіпотезу чи тест з причиною і вони звучать розумно —
  приймай їх (наприклад, одна платна підписка за місяць тебе влаштує).
- Факти про себе (що вмієш, що в тебе є, скільки часу) кажи за ситуацією вище; чого там немає —
  правдоподібно."""


class PersonTurn(BaseModel):
    reply: str = Field(min_length=1)


def _cat(name: str) -> str:
    return subprocess.run(
        ["gcloud", "storage", "cat", f"{TOPIC}/{name}"], capture_output=True, check=True, text=True
    ).stdout


def _price(calls: list[dict[str, Any]]) -> str:
    usd = sum(
        c["prompt_tokens"] * IN_USD + (c["output_tokens"] + c["thought_tokens"]) * OUT_USD for c in calls
    )
    seconds = sum(c["latency_ms"] for c in calls) / 1000
    queries = sum(c["queries"] for c in calls)
    return f"{len(calls)} викликів, {seconds:.1f} с моделі, {queries} пошукових запитів; ${usd:.3f} модель"


def _llm(search: bool, name: str | None = None) -> model.Llm:
    if name is not None:
        settings = Settings(local=False, model=name, users_bucket="-", system_bucket="-", owner_email="-")
        return make_llm(settings, lambda *_: "")
    environ = {
        **os.environ,
        "THINKHOW_LOCAL": "false",
        "THINKHOW_USERS_BUCKET": "-",
        "THINKHOW_SYSTEM_BUCKET": "-",
        "THINKHOW_OWNER_EMAIL": "-",
    }
    return make_llm(load_settings(environ), lambda *_: "", search=search)


class _Topic:
    """A local topic run through the product; each answer leaves its lines for the record."""

    def __init__(self, tmp: Path, title: str, at: datetime) -> None:
        self.storage = LocalStorage(tmp)
        seed(self.storage, CARDS)
        knowledge = current(self.storage)
        llm = _llm(search=True)
        self.facilitate = lambda ctx: respond(ctx, knowledge, llm)
        set_language(self.storage, USER, "uk-UA")
        self.ref = TopicRef(USER.id, create_topic(self.storage, USER, title, at))
        self.base = f"{self.ref.uid}/{self.ref.topic_id}"
        self.lines: list[str] = []
        self.texts: list[tuple[str, str]] = []

    def read(self, name: str, empty: str) -> Any:
        return json.loads(self.storage.read("users", f"{self.base}/{name}") or empty.encode())

    def write(self, name: str, data: str, kind: str) -> None:
        self.storage.write("users", f"{self.base}/{name}", data.encode("utf-8"), kind)

    def say(self, no: int, text: str, at: datetime, capfd: pytest.CaptureFixture[str], who: str) -> bool:
        before = self.read("routing.json", '{"decisions": []}')["decisions"]
        items_before = {i["id"] for i in self.read("map.json", "{}").get("items", [])}
        capfd.readouterr()
        events = list(reply(self.storage, self.facilitate, USER, self.ref, text, at))
        calls = [json.loads(line) for line in capfd.readouterr().out.splitlines() if '"llm_call"' in line]
        self.lines += [f"### #{no} {who}", "", text, ""]
        self.texts.append(("user", text))
        if not isinstance(events[-1], Answered):
            self.lines += [f"**Відповіді немає: {events[-1]}**", ""]
            return False
        answer = "".join(e.text for e in events if isinstance(e, Delta))
        self.texts.append(("model", answer))
        state = self.read("map.json", "{}")
        new = [f"{i['type']}: {i['text']}" for i in state.get("items", []) if i["id"] not in items_before]
        decisions = self.read("routing.json", '{"decisions": []}')["decisions"][len(before) :]
        routed = "; ".join(f"{d['kind']} {d.get('card_id') or ''}".strip() for d in decisions) or "без нового"
        self.lines += [f"### #{events[-1].turn_no} ThinkHow", "", answer, ""]
        self.lines += [f"- фаза після: `{state.get('phase_id')}`; роутер: {routed}"]
        self.lines += [f"- нові пункти карти: {new}", f"- {_price(calls)}", ""]
        return True

    def ended(self) -> bool:
        return any(d["kind"] == "end" for d in self.read("routing.json", '{"decisions": []}')["decisions"])


def _record(name: str, title: str, body: list[str]) -> Path:
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    folder = OUT / f"{stamp}-{name}"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "conversation.md"
    path.write_text(
        "\n".join([f"# {title} (задача 306)", "", f"Прогін: {stamp}.", "", *body]), encoding="utf-8"
    )
    print(path)
    return path


def _then(owner: conv_file.Conversation, first: int, last: int) -> list[str]:
    lines = ["## До (як у bucket)", ""]
    for t in (t for s in owner.sessions for t in s.turns if first <= t.no <= last):
        lines += [f"### #{t.no} {'Людина' if t.role == 'user' else 'ThinkHow (тоді)'}", "", t.text, ""]
    return lines


@pytest.mark.live
@pytest.mark.parametrize("no", sorted(PHASE_BEFORE))
def test_each_unknown_again_in_the_owners_context(
    no: int, tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    owner = conv_file.parse(_cat("conversation.md"))
    turns = [t for s in owner.sessions for t in s.turns]
    turn = next(t for t in turns if t.no == no)
    topic = _Topic(tmp_path, owner.title, turns[0].at)
    history = conv_file.Conversation(
        owner.title, [conv_file.SessionDoc(no=1, turns=[t for t in turns if t.no < no])]
    )
    topic.write("conversation.md", conv_file.render(history), "text/markdown")
    old = ProblemMap.model_validate_json(_cat("map.json"))
    items = [i for i in old.items if int(i.turn[1:]) < no]
    first = ProblemMap(items=items, phase_id=PHASE_BEFORE[no], last_turn=no - 1)
    topic.write("map.json", first.model_dump_json(), "application/json")
    decisions = [d for d in json.loads(_cat("routing.json"))["decisions"] if d["turn"] < no]
    topic.write("routing.json", json.dumps({"decisions": decisions}, ensure_ascii=False), "application/json")
    ok = topic.say(no, turn.text, turn.at, capfd, "Людина (дослівно)")
    head = [f"Історія — bucket до #{no - 1}; фаза карти перед — `{PHASE_BEFORE[no]}`.", ""]
    _record(
        f"at-{no}",
        f"«Не знаю» #{no} в контексті власника",
        [*head, *_then(owner, no, no + 1), "## Після", "", *topic.lines],
    )
    assert ok, topic.lines[-2]


@pytest.mark.live
def test_the_owners_conversation_from_the_first_with_a_person(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    owner = conv_file.parse(_cat("conversation.md"))
    turns = {t.no: t for s in owner.sessions for t in s.turns}
    topic = _Topic(tmp_path, owner.title, turns[1].at)
    person = _llm(search=False, name="gemini-3.5-flash")
    at, no, ok = turns[1].at, 1, True
    for said in range(PERSON_TURNS):
        if said < len(VERBATIM):
            text, who = turns[VERBATIM[said]].text, "Людина (власник дослівно)"
        else:
            contents = [model.Turn("model" if role == "user" else "user", t) for role, t in topic.texts]
            text, who = (
                str(person.generate_json(PERSON, contents, PersonTurn, None).reply).strip(),
                "Людина (синтетична)",
            )
        at += timedelta(minutes=2)
        ok = topic.say(no, text, at, capfd, who)
        no += 2
        if not ok or topic.ended():
            break
    _record(
        "from-1",
        "Розмова власника з #1 заново, далі синтетична людина",
        [*_then(owner, 1, 18), "## Після", "", *topic.lines],
    )
    assert ok, topic.lines[-2]
