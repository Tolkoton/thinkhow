"""Live tracer of slice router (`-m live`): the owner's topic t-d824f508a729 through the router, real model.

The person's turns of the owner's topic go in one by one while the router asks; after the first offer the
person answers «Давай перше.». Every run writes its conversation, routing.json and the record of the model
calls to a new file in .engine/artifacts/spikes/ (none is overwritten). The detector of method names is
tested here too, without the `live` mark, against all 18 cards of cards/.
"""

import functools
import json
import os
import re
import unicodedata
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import BaseModel, ValidationError

from thinkhow.access import CurrentUser
from thinkhow.facilitation import RouterAnswer, respond
from thinkhow.knowledge import current, seed
from thinkhow.platform import llm as model
from thinkhow.platform.config import load_settings
from thinkhow.platform.llm import LlmUnavailable, make_llm
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import Answered, Delta, TopicRef, create_topic, reply, set_language

ROOT = Path(__file__).resolve().parents[2]
CARDS = ROOT / "cards"
SPIKES = ROOT / ".engine" / "artifacts" / "spikes"
OWNER_TOPIC = json.loads(
    (ROOT / "tests" / "fixtures" / "facilitator_free_mode" / "owner_topic.json").read_text("utf-8")
)
CHOICE = "Давай перше."

# (а) the detector of task 301, on the normalised text
METHOD_301 = "|".join(
    [
        r"мортем|mortem|\bwrap\b|зважен\w*\s+матриц|матриц\w*\s+рішень",
        r"мозков\w*\s+штурм|backcasting|scamper|pdca|woop",
    ]
)
# (в) each card's own name, word stems instead of endings (slice router, Seam 5)
OWN_NAMES: dict[str, str] = {
    "first-principles": r"перш\w* принцип",
    "issue-tree": r"дерев\w* питан",
    "five-whys": r"п'ят\w* чому",
    "is-is-not": r"є/не є",
    "wrap-decision": r"\bwrap\b",
    "weighted-matrix": r"зважен\w* порівнян|матриц\w* рішен",
    "reversible-doors": r"двер\w* в один|10/10/10",
    "evaporating-cloud": r"хмар\w* що розвію",
    "pre-mortem": r"мортем|mortem",
    "consider-opposite": r"подума\w* протилежн|steelman",
    "socratic-questioning": r"сократ",
    "scamper": r"scamper|скампер",
    "mental-contrasting": r"якщо-то|ментальн\w* контраст",
    "goal-to-plan": r"\bgrow\b|backcasting|від мети до перших крок",
    "jobs-to-be-done": r"\bjtbd\b|jobs to be done|робот\w* яку наймають",
    "opportunity-tree": r"дерев\w* можливост|\brice\b|\bost\b",
}
NO_OWN_NAME: dict[str, str] = {"complexity-sensemaking": r"сенсмейк", "reflective-cycle": r"гіббс"}
# one variant of each own name with a typographic apostrophe and dash, no comma, an inflected form
VARIANTS: dict[str, str] = {
    "first-principles": "з перших принципів",
    "issue-tree": "розкладемо в дерево питань",
    "five-whys": "методом п’яти «чому»",
    "is-is-not": "таблиця «Є / не є»",
    "wrap-decision": "процес WRAP",
    "weighted-matrix": "зважене порівняння варіантів",
    "reversible-doors": "двері в один бік",
    "evaporating-cloud": "хмари, що розвіюється",
    "pre-mortem": "проведемо пре-мортем",
    "consider-opposite": "подумаймо протилежне",
    "socratic-questioning": "сократівськими питаннями",
    "scamper": "за SCAMPER",
    "mental-contrasting": "плану «якщо — то»",
    "goal-to-plan": "від мети до перших кроків",
    "jobs-to-be-done": "роботу, яку «наймають»",
    "opportunity-tree": "дерево можливостей",
}


def normalise(text: str) -> str:
    """Lower case; one apostrophe; one dash; no quotes or commas; no spaces around / and -; single spaces."""
    t = unicodedata.normalize("NFC", text).lower()
    t = re.sub(r"[’ʼ`‘]", "'", t)
    t = re.sub(r"[—–‑]", "-", t)
    t = re.sub(r"[«»„“”\"]", "", t).replace(",", "")
    t = re.sub(r"\s*/\s*", "/", t)
    t = re.sub(r"\s*-\s*", "-", t)
    return re.sub(r"\s+", " ", t)


def _id_pattern(card_id: str) -> str:
    return r"\b" + r"[- ]".join(re.escape(part) for part in card_id.split("-")) + r"\b"


def names_a_method(text: str) -> bool:
    t = normalise(text)
    ids = [_id_pattern(cid) for cid in [*OWN_NAMES, *NO_OWN_NAME]]
    patterns = [METHOD_301, *ids, *OWN_NAMES.values(), *NO_OWN_NAME.values()]
    return any(re.search(p, t) for p in patterns)


def _card_ids() -> list[str]:
    return sorted(yaml.safe_load(f.read_text("utf-8"))["id"] for f in CARDS.glob("*.yaml"))


def test_the_detector_knows_every_card_by_id_and_by_name() -> None:
    ids = _card_ids()
    assert sorted([*OWN_NAMES, *NO_OWN_NAME]) == ids
    for card_id in ids:
        assert names_a_method(f"Спробуймо {card_id}."), card_id
        assert names_a_method(f"Спробуймо {card_id.replace('-', ' ')}."), card_id
    for card_id, variant in VARIANTS.items():
        assert names_a_method(f"Можемо піти {variant}."), card_id
    titles = {
        yaml.safe_load(f.read_text("utf-8"))["id"]: yaml.safe_load(f.read_text("utf-8"))["title"]
        for f in CARDS.glob("*.yaml")
    }
    for card_id in OWN_NAMES:
        assert names_a_method(titles[card_id]), (card_id, titles[card_id])


@pytest.mark.parametrize(
    "text",
    [
        "Схоже, у вас кілька ідей і треба вирішити, з якої почати.",
        "1) Спокійно порівняти ідеї за тим, що для вас важливо. 2) Уявити, що обраний план не спрацював.",
        "Котрий спосіб ближчий — чи хочете інакше?",
    ],
)
def test_ordinary_router_sentences_are_not_caught(text: str) -> None:
    assert not names_a_method(text)


@dataclass
class Call:
    schema: str
    outcome: str
    cause: str = ""


@dataclass
class RecordingLlm:
    """The real model, every call recorded: whose schema, what came back, why the model was unavailable."""

    inner: model.Llm
    calls: list[Call] = field(default_factory=list)

    def stream_json(
        self,
        system: str,
        contents: Sequence[model.Turn],
        schema: type[BaseModel],
        rev: model.KnowledgeRev | None,
    ) -> Iterator[model.ReplyDelta | model.Done]:
        try:
            yield from self.inner.stream_json(system, contents, schema, rev)
        except LlmUnavailable as exc:
            self.calls.append(Call("facilitator", "unavailable", _cause(exc)))
            raise
        self.calls.append(Call("facilitator", "ok"))

    def generate_json(
        self, system: str, contents: Sequence[model.Turn], schema: type[Any], rev: model.KnowledgeRev | None
    ) -> Any:
        whose = "router" if issubclass(schema, RouterAnswer) else "facilitator"
        try:
            answer = self.inner.generate_json(system, contents, schema, rev)
        except ValidationError as exc:
            self.calls.append(Call(whose, "invalid", str(exc.errors()[0].get("msg", ""))))
            raise
        except LlmUnavailable as exc:
            self.calls.append(Call(whose, "unavailable", _cause(exc)))
            raise
        self.calls.append(Call(whose, "ok"))
        return answer

    def search_text(
        self, system: str, prompt: str, rev: model.KnowledgeRev | None
    ) -> tuple[str, model.Found | None]:
        return self.inner.search_text(system, prompt, rev)


def _cause(exc: Exception) -> str:
    cause = exc.__cause__
    code = getattr(cause, "code", None)
    return f"{type(cause).__name__}:{code}" if cause is not None else ""


def _routing(storage: LocalStorage, ref: TopicRef) -> list[dict[str, Any]]:
    data = storage.read("users", f"{ref.uid}/{ref.topic_id}/routing.json")
    return [] if data is None else list(json.loads(data)["decisions"])


def _write(
    rows: list[dict[str, Any]], routing: list[dict[str, Any]], calls: list[Call], verdict: str, log: list[str]
) -> Path:
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    path = SPIKES / f"router-live-{stamp}.md"
    lines = [
        "# Live tracer роутера — тема власника t-d824f508a729",
        "",
        f"Прогін {stamp}, модель — справжня (Vertex, `eu`), шлях — `workspace.reply`, Знання — 18 карток.",
        "",
        f"Клас результату: **{verdict}**",
        "",
    ]
    for n, row in enumerate(rows, 1):
        lines += [
            f"## Репліка {n}",
            "",
            f"**Людина:** {row['text']}",
            "",
            f"**Відповідь** ({row['who']}): {row['answer']}",
            "",
        ]
    lines += [
        "## routing.json",
        "",
        "```json",
        json.dumps({"decisions": routing}, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Виклики моделі",
        "",
    ]
    lines += [f"- {c.schema}: {c.outcome} {c.cause}".rstrip() for c in calls]
    lines += ["", "## Рядки журналу `llm_call` (час і токени — P4)", "", "```", *log, "```"]
    with path.open("x", encoding="utf-8") as out:
        out.write("\n".join(lines) + "\n")
    return path


def _classify(
    rows: list[dict[str, Any]],
    routing: list[dict[str, Any]],
    calls: list[Call],
    card_phases: dict[str, list[str]],
    rev: dict[str, int],
) -> str:
    """The run's class (slice router, Exit criterion): i FALSIFIED, ii not done, iii done, iv repeat."""
    router_invalid = sum(1 for c in calls if c.schema == "router" and c.outcome == "invalid")
    router_refused = [
        c
        for c in calls
        if c.schema == "router"
        and c.outcome == "unavailable"
        and re.search(r":4\d\d$", c.cause)
        and not c.cause.endswith(":429")
    ]
    if router_invalid >= 2 or router_refused:
        return "i"
    if any(not row["answered"] for row in rows):
        return "iv"
    kinds = [d["kind"] for d in routing]
    if "offer" not in kinds:
        return "ii: no offer"
    first_offer = kinds.index("offer")
    if "choose" in kinds[:first_offer]:
        return "ii: choose before an offer"
    last_offer = max(i for i, k in enumerate(kinds) if k == "offer")
    offer = routing[last_offer]
    if offer["candidates"][0]["card_id"] == "pre-mortem":
        return "ii: pre-mortem first"
    texts = [row["answer"] for row in rows if row["who"] == "router"]
    if not any(names_a_method(t) for t in texts):  # task 205: the offer names each method
        return "ii: no method named"
    chooses = [d for d in routing[last_offer + 1 :] if d["kind"] == "choose"]
    if not chooses or chooses[0]["card_id"] != offer["candidates"][0]["card_id"]:
        return "ii: «Давай перше.» did not choose the first candidate"
    if rows[-1]["phase"] not in card_phases[chooses[0]["card_id"]]:
        return "ii: the facilitator's phase is not of the chosen card"
    if offer["rev"] != rev or chooses[0]["rev"] != rev:
        return "ii: routing.json without the run's revision"
    return "iii"


@pytest.mark.live
def test_the_owners_topic_goes_through_the_router(tmp_path: Path, capfd: pytest.CaptureFixture[str]) -> None:
    storage = LocalStorage(tmp_path)
    seed(storage, CARDS)
    environ = {
        **os.environ,
        "THINKHOW_LOCAL": "false",
        "THINKHOW_USERS_BUCKET": "-",
        "THINKHOW_SYSTEM_BUCKET": "-",
        "THINKHOW_OWNER_EMAIL": "-",
    }
    knowledge = current(storage)
    llm = RecordingLlm(make_llm(load_settings(environ), script=lambda *_: ""))
    facilitate = functools.partial(respond, knowledge=knowledge, llm=llm)
    user = CurrentUser(id="live-person", email="live@example.com", is_owner=False)
    set_language(storage, user, "uk-UA")
    now = datetime(2026, 10, 24, 15, 0, tzinfo=UTC)
    ref = TopicRef(user.id, create_topic(storage, user, "Заробити", now))
    rows: list[dict[str, Any]] = []
    turns = list(OWNER_TOPIC["person_turns"])
    while True:
        routing = _routing(storage, ref)
        offered = any(d["kind"] == "offer" for d in routing)
        if offered and not any(d["kind"] == "choose" for d in routing):
            text = CHOICE
        elif offered or not turns:
            break
        else:
            text = turns.pop(0)
        now += timedelta(minutes=1)
        before = len(routing)
        events = list(reply(storage, facilitate, user, ref, text, now))
        answered = isinstance(events[-1], Answered)
        after = _routing(storage, ref)[before:]
        problem_map = json.loads(storage.read("users", f"{ref.uid}/{ref.topic_id}/map.json") or b"{}")
        who = "фасилітатор" if any(d["kind"] == "choose" for d in after) else "router"
        answer = "".join(e.text for e in events if isinstance(e, Delta))
        rows.append(
            {
                "text": text,
                "answer": answer,
                "who": who,
                "answered": answered,
                "phase": problem_map.get("phase_id"),
            }
        )
        if not answered or text == CHOICE:
            break
    routing = _routing(storage, ref)
    phases = {cid: [p.id for p in card.facilitator.phases] for cid, card in knowledge.cards.items()}
    verdict = _classify(rows, routing, llm.calls, phases, {"rev": knowledge.rev, "n": knowledge.n})
    out = capfd.readouterr().out
    log = [line for line in out.splitlines() if '"llm_call"' in line]
    print(out, end="")
    print(_write(rows, routing, llm.calls, verdict, log))
    assert verdict == "iii", verdict
