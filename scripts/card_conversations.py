"""One live conversation per card (task 302, slice router-eval) and the owner's topic t-d824f508a729 through
the router: a synthetic person (`gemini-3.5-flash`) talks to the product's `workspace.reply`.

Run: `PYTHONPATH=src uv run python scripts/card_conversations.py [--cards <id>…] [--owner] [--switch <id>]
[--turns N]`. Each conversation goes to .engine/artifacts/card-conversations/<time>/<name>.md, with index.md.
`converse_card`, `converse_owner` take the product model, the person's model and the Knowledge as parameters.
"""

import argparse
import functools
import importlib.util
import json
import sys
import tempfile
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from thinkhow.access import CurrentUser
from thinkhow.facilitation import Candidate, Decision, respond
from thinkhow.knowledge import CurrentKnowledge, current, seed
from thinkhow.platform import llm as model
from thinkhow.platform.config import Settings
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import Answered, Delta, Failed, TopicRef, create_topic, reply, retry, set_language

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "tests" / "fixtures" / "routing" / "cases.yaml"
OWNER = ROOT / "tests" / "fixtures" / "facilitator_free_mode" / "owner_topic.json"
OUT = ROOT / ".engine" / "artifacts" / "card-conversations"
PERSON_MODEL = "gemini-3.5-flash"
SWITCH_TEXT = "Давай інакше, цей спосіб мені зараз не допомагає."
RETRIES = 2
JSON = "application/json"

PERSON_RULES = """Ти граєш людину, яка прийшла до асистента, що допомагає думати. Твоя ситуація — нижче.
Відповідай від першої особи, як жива людина в чаті: коротко (одне-три речення) і по суті питання асистента,
з конкретними подробицями своєї ситуації (вигадуй правдоподібні, коли бракує, і тримайся вже сказаного).
Не вирішуй за асистента, не називай жодних способів думати і не проси їх назвати. Пиши українською."""
HOW_FOR_CARD = "Коли асистент пропонує кілька способів, обери той, що найкраще пасує до твоєї ситуації."
HOW_FOR_OWNER = (
    "Обирай те, що тобі зараз справді ближче: спершу розібратися з варіантами заробітку, "
    "потім — що з них обрати, "
    "далі — що може піти не так з обраним і з чого почати."
)


def _names_a_method() -> Callable[[str], bool]:
    """The detector of S2 (the card ids and own names of `cards/`), loaded from its live test by path,
    without a copy."""
    spec = importlib.util.spec_from_file_location(
        "router_live_detector", ROOT / "tests" / "live" / "test_router_live.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    detector: Callable[[str], bool] = module.names_a_method
    return detector


names_a_method = _names_a_method()


class PersonTurn(BaseModel):
    reply: str = Field(min_length=1)


@dataclass
class Row:
    """One turn: who spoke, the text, the facilitator's phase, the router's new decisions."""

    who: str  # людина | роутер | фасилітатор | система
    text: str
    phase: str | None = None
    decisions: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Conversation:
    """One conversation and what index.md says about it (contract Seam `card_conversations.py`, Seam 5)."""

    name: str
    target: str | None
    led: str | None  # the card of the last `choose` in routing.json
    offered: bool
    seeded: bool  # «вели без вибору роутером»
    phases: list[str]
    last_phase: bool
    done: bool
    broken: str = ""  # «обірвано: <reason>»
    note: str = ""  # «обрано іншу картку (<id>)», «картка закінчилась до перемикання», …
    rows: list[Row] = field(default_factory=list)
    routing: list[dict[str, Any]] = field(default_factory=list)
    named: bool = False  # «людина назвала метод»
    switched: bool = False


def person_instruction(situation: str, how_to_choose: str) -> str:
    """The synthetic person's system text: no method names, no card ids."""
    return f"{PERSON_RULES}\n\n# Твоя ситуація\n{situation}\n\n# Як обирати\n{how_to_choose}\n"


def choice_text(decisions: list[dict[str, Any]], target: str | None) -> str | None:
    """«Давай перше.» when the target is the last offer's first candidate, «Давай <n>.» for another place."""
    offers = [d for d in decisions if d["kind"] == "offer"]
    if not offers or target is None:
        return None
    ids = [c["card_id"] for c in offers[-1]["candidates"]]
    if target not in ids:
        return None
    place = ids.index(target)
    return "Давай перше." if place == 0 else f"Давай {place + 1}."


@dataclass
class _Topic:
    storage: LocalStorage
    user: CurrentUser
    ref: TopicRef
    now: datetime

    def routing(self) -> list[dict[str, Any]]:
        data = self.storage.read("users", f"{self.ref.uid}/{self.ref.topic_id}/routing.json")
        return [] if data is None else list(json.loads(data)["decisions"])

    def phase(self) -> str | None:
        data = self.storage.read("users", f"{self.ref.uid}/{self.ref.topic_id}/map.json")
        return None if data is None else json.loads(data).get("phase_id")


def _topic(title: str) -> _Topic:
    storage = LocalStorage(Path(tempfile.mkdtemp(prefix="thinkhow-conv-")))
    user = CurrentUser(id="synthetic", email="synthetic@example.com", is_owner=False)
    set_language(storage, user, "uk-UA")  # reply takes the language from the person's profile
    now = datetime(2026, 10, 24, 16, 0, tzinfo=UTC)
    return _Topic(storage, user, TopicRef(user.id, create_topic(storage, user, title, now)), now)


def _seed_choice(topic: _Topic, knowledge: CurrentKnowledge, target: str) -> None:
    """The test stand writes routing.json before the first turn: an offer of the card, its choice (Q3, A)."""

    def decision(kind: str) -> dict[str, Any]:
        return Decision.model_validate(
            {
                "turn": 0,
                "rev": {"rev": knowledge.rev, "n": knowledge.n},
                "kind": kind,
                "profile": None,
                "candidates": [Candidate(card_id=target, why="(засіяний вибір стенду)").model_dump()]
                if kind == "offer"
                else [],
                "card_id": target if kind == "choose" else None,
                "end": None,
                "why": "(засіяний вибір стенду: роутер картку не пропонував)",
            }
        ).model_dump(mode="json")

    path = f"{topic.ref.uid}/{topic.ref.topic_id}/routing.json"
    data = json.dumps({"decisions": [decision("offer"), decision("choose")]}, ensure_ascii=False)
    topic.storage.write("users", path, data.encode("utf-8"), JSON)


def _person_says(person: model.Llm, situation: str, how: str, rows: list[Row]) -> str:
    """The synthetic person's next turn: the conversation so far with the roles turned round."""
    contents = [
        model.Turn("model" if r.who == "людина" else "user", r.text) for r in rows if r.who != "система"
    ]
    answer = person.generate_json(person_instruction(situation, how), contents, PersonTurn, None)
    return str(answer.reply).strip()


def _answer(topic: _Topic, facilitate: Any, text: str) -> list[Any]:
    """One turn of the person by the product; a Failed answer is retried by «Спробуйте ще раз» up to twice."""
    topic.now += timedelta(minutes=1)
    events = list(reply(topic.storage, facilitate, topic.user, topic.ref, text, topic.now))
    for _ in range(RETRIES):
        if not isinstance(events[-1], Failed):
            break
        topic.now += timedelta(seconds=30)
        events = list(retry(topic.storage, facilitate, topic.user, topic.ref, topic.now))
    return events


def _drive(
    knowledge: CurrentKnowledge,
    llm: model.Llm,
    person: model.Llm,
    topic: _Topic,
    opener: str,
    situation: str,
    how: str,
    target: str | None,
    turns: int,
    switch: bool,
) -> Conversation:
    """Flow: the person's turn → the product → the routing and the phase → stop or the next turn."""
    facilitate = functools.partial(respond, knowledge=knowledge, llm=llm)
    conv = Conversation(
        name=target or "",
        target=target,
        led=None,
        offered=False,
        seeded=False,
        phases=[],
        last_phase=False,
        done=False,
    )
    text, chosen_at, count = opener, None, 0
    while True:
        count += 1
        conv.rows.append(Row("людина", text))
        conv.named = conv.named or (count > 1 and names_a_method(text))
        before = len(topic.routing())
        events = _answer(topic, facilitate, text)
        if isinstance(events[-1], Failed):
            conv.broken = events[-1].reason
            conv.rows.append(Row("система", f"(обірвано: {conv.broken})"))
            break
        assert isinstance(events[-1], Answered), events[-1]
        decisions = topic.routing()
        new = decisions[before:]
        who = "роутер" if new and new[-1]["kind"] in ("offer", "ask", "answer") else "фасилітатор"
        answer = "".join(e.text for e in events if isinstance(e, Delta))
        conv.rows.append(Row(who, answer, topic.phase() if who == "фасилітатор" else None, new))
        led = _led(decisions)
        if chosen_at is None and any(d["kind"] == "choose" for d in new):
            chosen_at = count
        if target is not None and any(d["kind"] == "end" and d["card_id"] == led for d in new):
            if not (switch and conv.switched):
                if switch:
                    conv.note = "картка закінчилась до перемикання"
                break
        if switch and conv.switched and any(d["kind"] == "offer" for d in new):
            break
        if count >= turns:
            break
        if switch and chosen_at is not None and not conv.switched and count == chosen_at + 2:
            text, conv.switched = SWITCH_TEXT, True
            continue
        if chosen_at is None and decisions and decisions[-1]["kind"] == "offer" and target is not None:
            text = choice_text(decisions, target) or "Давай перше."
            continue
        text = _person_says(person, situation, how, conv.rows)
    return _judge(conv, knowledge, topic.routing())


def _led(decisions: list[dict[str, Any]]) -> str | None:
    chooses = [d for d in decisions if d["kind"] == "choose"]
    return chooses[-1]["card_id"] if chooses else None


def _judge(conv: Conversation, knowledge: CurrentKnowledge, routing: list[dict[str, Any]]) -> Conversation:
    """The card actually led (the last choose) is what phases and the end are judged by."""
    conv.routing = routing
    conv.led = _led(routing)
    conv.offered = conv.target is not None and any(
        d["kind"] == "offer" and d["turn"] > 0 and conv.target in [c["card_id"] for c in d["candidates"]]
        for d in routing
    )
    for r in conv.rows:
        if r.who == "фасилітатор" and r.phase and (not conv.phases or conv.phases[-1] != r.phase):
            conv.phases.append(r.phase)
    if conv.led is not None and conv.led in knowledge.cards:
        conv.last_phase = knowledge.cards[conv.led].facilitator.phases[-1].id in conv.phases
        conv.done = any(
            d["kind"] == "end" and d["card_id"] == conv.led and d["end"] == "done" for d in routing
        )
    # the router's own pick is its first choose after the offer; a later choose follows «Давай інакше»
    picked = next((d["card_id"] for d in routing if d["kind"] == "choose" and d["turn"] > 0), conv.led)
    if conv.target and picked and picked != conv.target and not conv.note:
        conv.note = f"обрано іншу картку ({picked})"
    return conv


def converse_card(
    knowledge: CurrentKnowledge,
    llm: model.Llm,
    person: model.Llm,
    target: str,
    opener: str,
    turns: int = 12,
    switch: bool = False,
    seeded: bool = False,
) -> Conversation:
    """One conversation for the target card through workspace.reply in a temporary local storage."""
    topic = _topic("Розмова")
    if seeded:
        _seed_choice(topic, knowledge, target)
    conv = _drive(knowledge, llm, person, topic, opener, opener.strip(), HOW_FOR_CARD, target, turns, switch)
    conv.seeded = seeded
    return conv


def converse_owner(
    knowledge: CurrentKnowledge, llm: model.Llm, person: model.Llm, turns: int = 20
) -> Conversation:
    """The owner's topic: his turn #1 verbatim, then the synthetic person with the facts of his 7 turns."""
    owner = json.loads(OWNER.read_text(encoding="utf-8"))
    facts = "\n".join(f"- {t}" for t in owner["person_turns"])
    situation = (
        "Ти AI-інженер, тобі треба зараз заробити багато грошей; роботу знайти не вдається. "
        "Ось що ти вже казав "
        f"про себе (тримайся цього):\n{facts}"
    )
    conv = _drive(
        knowledge,
        llm,
        person,
        _topic("Заробити"),
        owner["person_turns"][0],
        situation,
        HOW_FOR_OWNER,
        None,
        turns,
        False,
    )
    conv.name = "owner-t-d824f508a729"
    return conv


def _marks(c: Conversation) -> str:
    marks = []
    if c.seeded:
        marks.append("вели без вибору роутером (не запропоновано)")
    elif c.target and not c.offered:
        marks.append("картку не запропоновано")
    if c.note:
        marks.append(c.note)
    if c.broken:
        marks.append(f"обірвано: {c.broken}")
    if c.named:
        marks.append("людина назвала метод")
    if c.switched:
        # the switch follows the first choose, so the row judges the card switched FROM, not the last one led
        left = next(d["card_id"] for d in c.routing if d["kind"] == "choose")
        after = [d for d in c.routing if d["kind"] == "end" and d["card_id"] == left]
        new_offer = (
            any(
                d["kind"] == "offer" and left not in [x["card_id"] for x in d["candidates"]]
                for d in c.routing[c.routing.index(after[-1]) + 1 :]
            )
            if after
            else False
        )
        marks.append(
            f"після «давай інакше»: end — {'так' if after else 'ні'}, нове offer без картки — "
            f"{'так' if new_offer else 'ні'}"
        )
    return "; ".join(marks)


def index(conversations: list[Conversation], stamp: str) -> str:
    """index.md over all conversations."""
    lines = [
        "# Живі розмови по картках",
        "",
        f"Прогін {stamp}. Модель продукту — `gemini-4-argon` (Vertex `eu`);",
        f"синтетична людина — `{PERSON_MODEL}`.",
        "",
        "| розмова | цільова | вели | запропоновано | фази | остання фаза | end: done | реплік людини "
        "| позначки |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for c in conversations:
        people = sum(r.who == "людина" for r in c.rows)
        lines.append(
            f"| [{c.name}]({c.name}.md) | `{c.target or '—'}` | `{c.led or '—'}` | "
            f"{'так' if c.offered else 'ні'} | {' → '.join(c.phases)} | {'так' if c.last_phase else 'ні'} | "
            f"{'так' if c.done else 'ні'} | {people} | "
            f"{_marks(c)} |"
        )
    return "\n".join(lines) + "\n"


def write(folder: Path, c: Conversation, title: str) -> None:
    lines = [
        f"# {title}",
        "",
        f"Модель продукту — `gemini-4-argon` (Vertex `eu`); синтетична людина — "
        f"`{PERSON_MODEL}`; шлях — `workspace.reply` продукту.",
        "",
        f"Позначки: {_marks(c) or '—'}",
        "",
    ]
    for n, r in enumerate(c.rows, 1):
        phase = f" (фаза `{r.phase}`)" if r.who == "фасилітатор" else ""
        lines += [f"**{n}. {r.who}{phase}:** {r.text}", ""]
        for d in r.decisions:
            ids = ", ".join(x["card_id"] for x in d["candidates"])
            lines += [
                f"> рішення роутера: `{d['kind']}` {d.get('card_id') or ''} {ids} "
                f"{d.get('end') or ''}".rstrip(),
                "",
            ]
    lines += [
        "## routing.json",
        "",
        "```json",
        json.dumps({"decisions": c.routing}, ensure_ascii=False, indent=1),
        "```",
        "",
    ]
    with (folder / f"{c.name}.md").open("x", encoding="utf-8") as out:
        out.write("\n".join(lines))


def _settings(name: str) -> Settings:
    return Settings(local=False, model=name, users_bucket="-", system_bucket="-", owner_email="-")


def _for_card(
    knowledge: CurrentKnowledge,
    llm: model.Llm,
    person: model.Llm,
    cases: list[dict[str, Any]],
    target: str,
    turns: int,
) -> list[Conversation]:
    """Q3: the first positive case; not led — the 2nd and 3rd (B); then a seeded choice (A)."""
    openers = [c["text"].strip() for c in cases if c["kind"] == "positive" and c["expect"] == target]
    tried: list[Conversation] = []
    for n, opener in enumerate(openers[:3], 1):
        conv = converse_card(knowledge, llm, person, target, opener, turns)
        conv.name = target if n == 1 else f"{target}-спроба-{n}"
        tried.append(conv)
        if conv.led == target and not conv.broken:
            return tried
    conv = converse_card(knowledge, llm, person, target, openers[0], turns, seeded=True)
    conv.name = f"{target}-засіяно"
    return [*tried, conv]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cards", nargs="*", default=None)
    parser.add_argument("--owner", action="store_true")
    parser.add_argument("--switch", default=None)
    parser.add_argument("--turns", type=int, default=12)
    args = parser.parse_args()
    llm = model.make_llm(_settings("gemini-4-argon"), lambda *_: "")
    person = model.make_llm(_settings(PERSON_MODEL), lambda *_: "")
    storage = LocalStorage(Path(tempfile.mkdtemp(prefix="thinkhow-k-")))
    seed(storage, ROOT / "cards")
    knowledge = current(storage)
    cases = yaml.safe_load(CASES.read_text(encoding="utf-8"))["cases"]
    targets = args.cards if args.cards is not None else sorted(knowledge.cards)
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    folder = OUT / stamp
    folder.mkdir(parents=True)
    with ThreadPoolExecutor(max_workers=6) as pool:
        groups = list(pool.map(lambda t: _for_card(knowledge, llm, person, cases, t, args.turns), targets))
    conversations = [c for group in groups for c in group]
    if args.switch:
        opener = next(
            c["text"].strip() for c in cases if c["kind"] == "positive" and c["expect"] == args.switch
        )
        conv = converse_card(knowledge, llm, person, args.switch, opener, 20, switch=True)
        conv.name = f"switch-{args.switch}"
        conversations.append(conv)
    if args.owner:
        conversations.append(converse_owner(knowledge, llm, person))
    for c in conversations:
        title = (
            "Тема власника t-d824f508a729 новим роутером"
            if c.target is None
            else f"Жива розмова — `{c.name}`"
        )
        write(folder, c, title)
    (folder / "index.md").write_text(index(conversations, stamp), encoding="utf-8")
    print(folder / "index.md")


if __name__ == "__main__":
    main()
