"""Helpers for the fact-answer contract tests (slice tester; built from the contract, not the code).

- FaLlm: a fake `platform.llm.Llm`. `generate_json` validates the next planned raw JSON by the schema it was
  given (the router's narrowed schema or a retry schema), so an invalid planned answer is a `ValidationError`
  inside the call; `stream_json` yields the planned deltas, then `Done(raw, usage, found)`. Every call is
  recorded with its system, contents, schema and revision.
- Cards, knowledge, contexts, router answers and decisions, written by hand from the contract «Seam».
- The texts the contract fixes word for word: `answer.md`, the new lines of `router.md` and `research.md`,
  `FACT_RETRY_ASK`, the decision line of `answer`.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from thinkhow.access import CurrentUser
from thinkhow.facilitation.route import RouterAnswer
from thinkhow.facilitation.types import (
    Candidate,
    Decision,
    FacilitationContext,
    MapItem,
    ProblemMap,
    Profile,
    Rev,
    Turn,
)
from thinkhow.knowledge import Card, CurrentKnowledge
from thinkhow.platform import llm as pl
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import TopicRef, create_topic

T0 = datetime(2026, 10, 25, 11, 0, 0, tzinfo=UTC)
ALICE = CurrentUser(id="alice-1", email="alice@example.com", is_owner=False)
REV = Rev(rev=3, n=7)

# --- the texts of the contract, word for word ------------------------------------------------------

ANSWER_MD = (
    "Ти — ThinkHow. Людина прямо питає факт про світ. Знайди його в інтернеті й відповідай коротко, фактом: "
    "два-чотири речення своїми словами, з числами чи назвами, без посилань у тексті (джерела система допише "
    "сама). Не радь, що їй робити, і не оцінюй її варіантів: рішення лишається за нею. Наприкінці — одне "
    "питання: що з цим фактом для неї важливо далі. Знайдений факт коротко додай у map_updates пунктом типу "
    "«fact» (id нового пункту — новий, напр. «i3»; turn — «t<номер з рамки репліки>»)."
)
ROUTER_ANSWER_ITEM = (
    '- "answer" — коли людина прямо питає факт про світ, який можна знайти (ціна, строк, правило, як це '
    "зазвичай роблять), а способу думати ще не обрано, і сама відповідь фактом — те, чого вона хоче. reply — "
    'null; card_id — null. Якщо за питанням стоїть рішення, яке треба продумати, — не "answer", а "offer" '
    'чи "ask".'
)
ROUTER_ASK_RULE = '- В "ask" не питай людину фактів про світ, які можна знайти: для них є "answer".'
RESEARCH_LAST_LINE = "Пункт «fact» — лише для знайденого пошуком; що людина розповіла про себе — не «fact»."
FACT_RETRY_ASK = "Поверни лише зміни карти до своєї відповіді вище."
CARD_RETRY_ASK = "Поверни лише оновлення до своєї відповіді вище: фаза, вихід, зміни карти."
FREE_MODE_LINE = "[Стан] Вільний режим уже триває: людина чула, що картка не підходить. Не кажи цього знову."
ANSWER_LINE_1 = "- репліка #1: answer (відповідь фактом)"
ASK_TAIL = "ask (уточнювальне питання)"

RULE_PL = (
    "Відповідай мовою людини — Polski (pl-PL): цю мову вона обрала для розмов з ThinkHow, "
    "і це правило важливіше за «мовою останньої репліки» вище. "
    "Іншою мовою — лише якщо людина прямо попросить. "
    "Ніколи не відповідай російською — ні на репліку російською, ні на прохання."
)
RULE_NONE = "Ніколи не відповідай російською: на репліку російською відповідай українською."


def flat(text: str) -> str:
    """The text with every run of whitespace made one space (the line breaks of a wrapped paragraph)."""
    return " ".join(text.split())


# --- cards and knowledge ------------------------------------------------------------------------------------


def phase_dict(cid: str, pid: str) -> dict[str, Any]:
    return {
        "id": pid,
        "title": f"Назва фази {pid} картки {cid}",
        "goal": f"мета фази {pid} картки {cid}",
        "how": [f"як іти фазою {pid} картки {cid}"],
        "exit": f"вихід фази {pid} картки {cid}",
    }


def card(cid: str, phase_ids: Sequence[str]) -> Card:
    return Card.model_validate(
        {
            "id": cid,
            "title": f"Заголовок картки {cid}",
            "router": {
                "needs": f"роутер-потреба картки {cid}",
                "when_yes": [f"коли так картки {cid}"],
                "when_no": [f"коли ні картки {cid}"],
                "signals": [f"сигнал картки {cid}"],
            },
            "facilitator": {
                "purpose": f"навіщо фасилітатору картки {cid}",
                "stance": f"позиція фасилітатора картки {cid}",
                "needs": f"на вході фасилітатора картки {cid}",
                "phases": [phase_dict(cid, p) for p in phase_ids],
                "ending": f"кінець картки {cid}",
                "traps": [{"name": "Не той випадок", "text": f"текст пастки картки {cid}"}],
                "pairs_well": f"добре поєднується картки {cid}",
            },
        }
    )


ALPHA = card("alpha", ["a_one", "a_two"])
BETA = card("beta", ["b_one", "b_two"])
PREMORTEM = card("pre-mortem", ["pm_one", "pm_two"])
CARDS = (ALPHA, BETA, PREMORTEM)


def card_texts(c: Card) -> list[str]:
    """Every distinctive text of a card (its router half and its facilitator half)."""
    texts = [
        f"Заголовок картки {c.id}",
        f"роутер-потреба картки {c.id}",
        f"коли так картки {c.id}",
        f"коли ні картки {c.id}",
        f"сигнал картки {c.id}",
        f"навіщо фасилітатору картки {c.id}",
        f"позиція фасилітатора картки {c.id}",
        f"на вході фасилітатора картки {c.id}",
        f"кінець картки {c.id}",
        f"текст пастки картки {c.id}",
        f"добре поєднується картки {c.id}",
    ]
    return texts + [
        f"фази {p} картки {c.id}" for p in ("a_one", "a_two", "b_one", "b_two", "pm_one", "pm_two")
    ]


def knowledge(cards: Sequence[Card] = CARDS, rev: int = 3, n: int = 7) -> CurrentKnowledge:
    return CurrentKnowledge(rev=rev, n=n, cards={c.id: c for c in cards}, memory=[])


PROFILE: dict[str, str] = {
    "intent": "understand_situation",
    "structuredness": "well_structured",
    "reversibility": "unclear",
    "stakes": "low",
    "data": "data_rich",
    "options": "unclear",
    "emotion": "neutral_analytical",
    "social": "individual_personal",
}
PROFILE_OBJ = Profile.model_validate(PROFILE)

HISTORY = [
    Turn(role="user", text="Думаю про нову машину."),
    Turn(role="model", text="Що для вас у ній найважливіше?"),
]
ITEM = MapItem(id="i1", type="goal", text="купити машину", turn="t1")
QUESTION = "Скільки коштує новий Škoda Octavia Combi у Німеччині?"


def context(
    routing: tuple[Decision, ...] | None = (),
    text: str = QUESTION,
    turn_no: int = 3,
    pm: ProblemMap | None = None,
    language: str | None = None,
    history: list[Turn] | None = None,
    card_id: str = "pre-mortem",
) -> FacilitationContext:
    return FacilitationContext(
        card_id=card_id,
        history=list(HISTORY if history is None else history),
        problem_map=pm if pm is not None else ProblemMap(items=[ITEM], phase_id=None, last_turn=2),
        turn_no=turn_no,
        text=text,
        language=language,
        routing=routing,
    )


# --- router answers (raw JSON) and decisions ----------------------------------------------------------------


def router_raw(
    action: str,
    candidates: Sequence[str] = (),
    card_id: str | None = None,
    reply: str | None = None,
    why: str = "людина прямо питає ціну",
) -> str:
    return json.dumps(
        {
            "action": action,
            "profile": PROFILE,
            "candidates": [{"card_id": c, "why": f"Це допоможе ({c})."} for c in candidates],
            "card_id": card_id,
            "reply": reply,
            "why": why,
        },
        ensure_ascii=False,
    )


ROUTER_REPLY = "РОУТЕР-КАЖЕ: ось ціна від роутера, якої людина бачити не мусить."
OFFER_REPLY = "Я зрозумів так: ви обираєте машину. 1) … 2) … Котрий ближчий — чи інше?"


def answer_raw(candidates: Sequence[str] = (), reply: str | None = ROUTER_REPLY) -> str:
    return router_raw("answer", candidates, None, reply)


def offer_raw(*ids: str) -> str:
    return router_raw("offer", ids, None, OFFER_REPLY, "пропоную за профілем")


def d_offer(turn: int, *ids: str) -> Decision:
    return Decision(
        turn=turn,
        rev=REV,
        kind="offer",
        profile=PROFILE_OBJ,
        candidates=[Candidate(card_id=i, why=f"Це допоможе ({i}).") for i in ids],
        card_id=None,
        end=None,
        why="пропоную за профілем",
    )


def d_choose(turn: int, cid: str) -> Decision:
    return Decision(
        turn=turn,
        rev=REV,
        kind="choose",
        profile=PROFILE_OBJ,
        candidates=[],
        card_id=cid,
        end=None,
        why="обрала",
    )


def d_end(turn: int, cid: str, end: str) -> Decision:
    return Decision.model_validate(
        {
            "turn": turn,
            "rev": REV.model_dump(),
            "kind": "end",
            "profile": None,
            "candidates": [],
            "card_id": cid,
            "end": end,
            "why": "картку пройдено" if end == "done" else "картка не підходить",
        }
    )


def d_answer(turn: int) -> Decision:
    return Decision(
        turn=turn,
        rev=REV,
        kind="answer",
        profile=PROFILE_OBJ,
        candidates=[],
        card_id=None,
        end=None,
        why="людина прямо питає ціну",
    )


# --- fact answers (raw JSON) --------------------------------------------------------------------------------

REPLY = "Новий Octavia Combi у Німеччині коштує від 33 000 євро. Що для вас у цій ціні важливо далі?"
DELTAS = ["Новий Octavia Combi у Німеччині коштує від 33 000 євро. ", "Що для вас у цій ціні важливо далі?"]
FACT = {
    "op": "add",
    "id": "i2",
    "type": "fact",
    "text": "Octavia Combi у Німеччині — від 33 000 €.",
    "turn": "t3",
}
FACT_RETRY = {
    "op": "add",
    "id": "i2",
    "type": "fact",
    "text": "Octavia Combi — від 33 000 € (DE).",
    "turn": "t3",
}
FOUND = pl.Found(
    ("Škoda Octavia Combi ціна Німеччина",),
    (
        pl.Source("Preisliste Octavia", "https://a.example/preis"),
        pl.Source("Autobild", "https://b.example/o"),
    ),
    "<div>підказки</div>",
)
LINE = "\n\nДжерела: [Preisliste Octavia](https://a.example/preis), [Autobild](https://b.example/o)"
EMPTY_FOUND = pl.Found((), (), None)


def fact_raw(reply: str = REPLY, updates: Sequence[dict[str, Any]] = (FACT,)) -> str:
    return json.dumps({"reply": reply, "map_updates": list(updates)}, ensure_ascii=False)


def fact_update_raw(updates: Sequence[dict[str, Any]] = (FACT_RETRY,)) -> str:
    return json.dumps({"map_updates": list(updates)}, ensure_ascii=False)


INVALID_WITH_OTHER_REPLY = json.dumps(
    {"reply": "Зовсім інший текст повторної відповіді.", "map_updates": [{"op": "add"}]}, ensure_ascii=False
)
TRUNCATED = '{"reply": "Новий Octavia Combi у Німеччині коштує від 33 000'


# --- the model double ---------------------------------------------------------------------------------------

USAGE = pl.Usage(prompt_tokens=10, output_tokens=5, thought_tokens=0)


@dataclass
class Stream:
    deltas: list[str]
    raw: str
    found: pl.Found | None = None


@dataclass
class Call:
    kind: str  # "generate" or "stream"
    system: str
    contents: list[pl.Turn]
    schema: type[BaseModel]
    rev: pl.KnowledgeRev | None

    @property
    def is_router(self) -> bool:
        return (
            self.kind == "generate"
            and isinstance(self.schema, type)
            and issubclass(self.schema, RouterAnswer)
        )


@dataclass
class FaLlm:
    generate: list[str | BaseException] = field(default_factory=list)
    streams: list[Stream | BaseException] = field(default_factory=list)
    calls: list[Call] = field(default_factory=list)

    @property
    def router_calls(self) -> list[Call]:
        return [c for c in self.calls if c.is_router]

    @property
    def stream_calls(self) -> list[Call]:
        return [c for c in self.calls if c.kind == "stream"]

    @property
    def retry_calls(self) -> list[Call]:
        return [c for c in self.calls if c.kind == "generate" and not c.is_router]

    def stream_json(
        self, system: str, contents: Sequence[pl.Turn], schema: type[BaseModel], rev: pl.KnowledgeRev | None
    ) -> Iterator[pl.ReplyDelta | pl.Done]:
        self.calls.append(Call("stream", system, list(contents), schema, rev))
        if not self.streams:
            raise AssertionError("stream_json was called more times than the scenario planned")
        return self._stream(self.streams.pop(0))

    def _stream(self, plan: Stream | BaseException) -> Iterator[pl.ReplyDelta | pl.Done]:
        if isinstance(plan, BaseException):
            raise plan
        for d in plan.deltas:
            yield pl.ReplyDelta(text=d)
        yield pl.Done(plan.raw, USAGE, plan.found)

    def generate_json(
        self, system: str, contents: Sequence[pl.Turn], schema: type[Any], rev: pl.KnowledgeRev | None
    ) -> Any:
        self.calls.append(Call("generate", system, list(contents), schema, rev))
        if not self.generate:
            raise AssertionError("generate_json was called more times than the scenario planned")
        planned = self.generate.pop(0)
        if isinstance(planned, BaseException):
            raise planned
        return schema.model_validate_json(planned)


def no_lead(ctx: FacilitationContext, k: CurrentKnowledge, llm: pl.Llm) -> Iterator[Any]:
    raise AssertionError("the card's lead was called on the path of `answer`")


# --- the workspace side -------------------------------------------------------------------------------------


def topic(store: LocalStorage) -> TopicRef:
    return TopicRef(ALICE.id, create_topic(store, ALICE, "Тема", T0))


def topic_path(ref: TopicRef, name: str) -> str:
    return f"{ref.uid}/{ref.topic_id}/{name}"


def read_json(store: LocalStorage, ref: TopicRef, name: str) -> Any:
    data = store.read("users", topic_path(ref, name))
    return None if data is None else json.loads(data)


def read_routing(store: LocalStorage, ref: TopicRef) -> list[Decision] | None:
    doc = read_json(store, ref, "routing.json")
    if doc is None:
        return None
    return [Decision.model_validate(d) for d in doc["decisions"]]


def put_routing(store: LocalStorage, ref: TopicRef, decisions: Sequence[Decision]) -> None:
    doc = {"decisions": [d.model_dump(mode="json") for d in decisions]}
    store.write(
        "users",
        topic_path(ref, "routing.json"),
        json.dumps(doc, ensure_ascii=False).encode(),
        "application/json",
    )
