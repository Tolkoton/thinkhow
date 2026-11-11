"""Helpers for the deep-research-confirm-first contract tests (slice tester; from the contract, not the code).

The sealed helpers of research-quick (`rq_fakes`: cards alpha/beta, knowledge, the topic, routing.json,
research.json, map.json) and of fact-answer (`fa_fakes`: router answers, the fact answer) are reused as they
are: their folders are put on `sys.path`.

- `api(module, name)`: a name of the contract's Seam that the skeleton may not have yet, looked up when the
  test runs (so a missing name fails the test in its body, not the whole file at import).
- DcLlm: a fake `platform.llm.Llm`. `generate_json` answers by the schema it was given: `RouterAnswer`
  from `router`, `DeepPlan` from `plans`, `DeepReport` from `reports`, the schema named `DeepConsent` from
  `consents`, any other from `updates`; each planned raw JSON is validated by that schema (an invalid one is a
  `ValidationError` inside the call); a planned exception is raised. `stream_json` yields the planned deltas,
  then `Done(raw, usage, found)`. `search_text` answers by its prompt from `searches`. Every call is recorded
  (thread-safe: the searches run in parallel). A call nobody planned raises `AssertionError`.
- Scenario values written by hand: the research question, three plans (3, 2 and 4 sub-questions), the
  proposals' texts as the contract builds them (written out, not computed), findings, sources, the report.
"""

from __future__ import annotations

import importlib
import json
import sys
import threading
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any

__all__ = ["fa", "rq"]

HERE = Path(__file__).resolve().parent
for sibling in ("research_quick", "fact_answer"):
    path = str(HERE.parent / sibling)
    if path not in sys.path:
        sys.path.insert(0, path)

from pydantic import BaseModel  # noqa: E402

from thinkhow.facilitation import respond  # noqa: E402
from thinkhow.facilitation import types as ft  # noqa: E402
from thinkhow.facilitation.route import RouterAnswer  # noqa: E402
from thinkhow.facilitation.types import (  # noqa: E402
    DeepPlan,
    DeepReport,
    FacilitationContext,
    FacilitatorUpdate,
    MapItem,
    MapUpdate,
    ProblemMap,
    ReplyDelta,
    Turn,
)
from thinkhow.platform import llm as pl  # noqa: E402
from thinkhow.platform.storage import LocalStorage  # noqa: E402
from thinkhow.workspace import Delta, TopicRef, open_topic, reply, retry  # noqa: E402
from thinkhow.workspace.model import ReplyEvent  # noqa: E402

fa: Any = importlib.import_module("fa_fakes")  # the sealed fact-answer helpers
rq: Any = importlib.import_module("rq_fakes")  # the sealed research-quick helpers


def api(owner: Any, name: str) -> Any:
    """A name of the contract's Seam (of a module or a value), looked up when the test runs."""
    return getattr(owner, name)


def pending(question: str, intro: str, questions: Sequence[str]) -> Any:
    return api(ft, "PendingDeep")(question=question, intro=intro, questions=list(questions))


def flat(text: str) -> str:
    return " ".join(text.split())


# --- texts fixed elsewhere, word for word ---------------------------------------------------------------

FIRST_REPLY_LINE = (
    "[Стан] Перша відповідь у темі: перед питанням одним реченням скажи, що будь-коли можна спитати "
    "твою думку («що б ти обрав?») або попросити інший спосіб."
)
QUESTION_HEAD = "\n\n[Питання дослідження]\n"

# --- a deep scenario, by hand ---------------------------------------------------------------------------

DQ = "Як компанії Mittelstand купують консалтинг і де швидше перші гроші?"
INTRO_1 = "Дослідю, як Mittelstand купує консалтинг, — близько двох хвилин. Запускати чи щось змінити?"
INTRO_2 = "Дослідю конкурентів на ринку консалтингу Mittelstand — близько двох хвилин. Запускати?"
INTRO_4 = "Дослідю чотири боки ринку консалтингу — близько двох хвилин. Запускати чи змінити?"
QA = "Як Mittelstand обирає консультантів?"
QB = "Скільки коштує проєкт консалтингу для Mittelstand?"
QC = "Де консультанти знаходять перших клієнтів у Саксонії?"
QD = "Хто головні конкуренти в консалтингу для Mittelstand?"
QE = "Які консалтингові фірми працюють у Саксонії?"
QF = "Які програми IHK оплачують консалтинг?"
QG = "Як швидко Mittelstand платить консультантам?"
QH = "Чим нові консультанти виграють перших клієнтів?"
QI = "Скільки консультантів у Саксонії працюють самі?"

PLAN_1 = (QA, QB, QC)
PLAN_2 = (QD, QE)
PLAN_4 = (QF, QG, QH, QI)

# proposal_text = intro + "\n\n" + question + "\n" + the lines "- <sub-question>" — written out by hand
PROPOSAL_1 = (
    "Дослідю, як Mittelstand купує консалтинг, — близько двох хвилин. Запускати чи щось змінити?\n\n"
    "Як компанії Mittelstand купують консалтинг і де швидше перші гроші?\n"
    "- Як Mittelstand обирає консультантів?\n"
    "- Скільки коштує проєкт консалтингу для Mittelstand?\n"
    "- Де консультанти знаходять перших клієнтів у Саксонії?"
)
PROPOSAL_2 = (
    "Дослідю конкурентів на ринку консалтингу Mittelstand — близько двох хвилин. Запускати?\n\n"
    "Як компанії Mittelstand купують консалтинг і де швидше перші гроші?\n"
    "- Хто головні конкуренти в консалтингу для Mittelstand?\n"
    "- Які консалтингові фірми працюють у Саксонії?"
)
PROPOSAL_4 = (
    "Дослідю чотири боки ринку консалтингу — близько двох хвилин. Запускати чи змінити?\n\n"
    "Як компанії Mittelstand купують консалтинг і де швидше перші гроші?\n"
    "- Які програми IHK оплачують консалтинг?\n"
    "- Як швидко Mittelstand платить консультантам?\n"
    "- Чим нові консультанти виграють перших клієнтів?\n"
    "- Скільки консультантів у Саксонії працюють самі?"
)
STEPS_1 = "- Як Mittelstand обирає консультантів?\n- Скільки коштує проєкт консалтингу для Mittelstand?\n" + (
    "- Де консультанти знаходять перших клієнтів у Саксонії?"
)
STEPS_2 = (
    "- Хто головні конкуренти в консалтингу для Mittelstand?\n- Які консалтингові фірми працюють у Саксонії?"
)
STEPS_4 = (
    "- Які програми IHK оплачують консалтинг?\n- Як швидко Mittelstand платить консультантам?\n"
    "- Чим нові консультанти виграють перших клієнтів?\n- Скільки консультантів у Саксонії працюють самі?"
)

FILE_1 = {"question": DQ, "intro": INTRO_1, "questions": list(PLAN_1)}
FILE_2 = {"question": DQ, "intro": INTRO_2, "questions": list(PLAN_2)}
FILE_4 = {"question": DQ, "intro": INTRO_4, "questions": list(PLAN_4)}

CHANGE = "Не треба про ціни, додай, хто конкуренти."

REPORT = (
    "Mittelstand здебільшого бере консультантів за рекомендацією (62%), проєкт коштує 8–25 тис. євро, "
    "а перші клієнти приходять через IHK. Що з цього для вас важливо далі?"
)
FACT_1 = "62% фірм Mittelstand беруть консультанта за рекомендацією."
FACT_2 = "Проєкт консалтингу для Mittelstand коштує 8 000–25 000 євро."


def _found(query: str, title: str, url: str) -> pl.Found:
    return pl.Found((query,), (pl.Source(title, url),), None)


SEARCHES: dict[str, tuple[str, pl.Found | None]] = {
    QA: (
        "ЗНАХІДКА-А: 62% беруть за рекомендацією.",
        _found("Mittelstand Berater Auswahl", "Studie A", "https://a.example/a"),
    ),
    QB: ("ЗНАХІДКА-Б: 8 000–25 000 євро.", _found("Beratung Kosten", "Markt B", "https://b.example/b")),
    QC: ("ЗНАХІДКА-В: через IHK.", _found("Berater erste Kunden", "IHK C", "https://c.example/c")),
    QD: (
        "ЗНАХІДКА-Г: три великі фірми.",
        _found("Beratung Wettbewerb", "Wettbewerb D", "https://d.example/d"),
    ),
    QE: (
        "ЗНАХІДКА-Ґ: сорок фірм у Саксонії.",
        _found("Beratung Sachsen", "Sachsen E", "https://e.example/e"),
    ),
    QF: ("ЗНАХІДКА-Д: go-digital до 50%.", _found("go-digital", "Förder F", "https://f.example/f")),
    QG: ("ЗНАХІДКА-Е: 30 днів.", _found("Zahlungsziel Beratung", "Zahlung G", "https://g.example/g")),
    QH: ("ЗНАХІДКА-Є: рекомендації.", _found("erste Kunden Berater", "Kunden H", "https://h.example/h")),
    QI: ("ЗНАХІДКА-Ж: 60% самі.", _found("Solo Berater Sachsen", "Solo I", "https://i.example/i")),
}
SOURCES_LINE_1 = "\n\nДжерела: [Studie A](https://a.example/a), [Markt B](https://b.example/b), [IHK C](https://c.example/c)"
SOURCES_1 = [
    {"title": "Studie A", "url": "https://a.example/a"},
    {"title": "Markt B", "url": "https://b.example/b"},
    {"title": "IHK C", "url": "https://c.example/c"},
]
QUERIES_1 = {"Mittelstand Berater Auswahl", "Beratung Kosten", "Berater erste Kunden"}

CARD_REPLY = "Звучить як питання ринку — його можна дослідити глибше, якщо захочете."
CARD_PLAIN = "Добре, тоді далі без дослідження. Що для вас тут найважливіше?"
ASK_REPLY = "Про що саме ви хочете поговорити далі?"
ROUTER_REPLY = "РОУТЕР-КАЖЕ: це текст роутера, якого людина не бачить."


def is_report(text: str, steps: str, tail: str) -> bool:
    """The text after «yes»: first the lines of the sub-questions, then the report with its sources line at
    the end; only white space between them."""
    return text.startswith(steps) and text.endswith(tail) and text[len(steps) : -len(tail)].strip() == ""


def plan_raw(intro: str, questions: Sequence[str]) -> str:
    return json.dumps({"intro": intro, "questions": list(questions)}, ensure_ascii=False)


PLAN_RAW_1 = plan_raw(INTRO_1, PLAN_1)
PLAN_RAW_2 = plan_raw(INTRO_2, PLAN_2)
PLAN_RAW_4 = plan_raw(INTRO_4, PLAN_4)
INVALID_PLAN = json.dumps({"intro": INTRO_1}, ensure_ascii=False)
REPORT_RAW = json.dumps({"report": REPORT, "facts": [FACT_1, FACT_2]}, ensure_ascii=False)


def consent_raw(answer: str) -> str:
    return json.dumps({"answer": answer})


def router_deep(question: str = DQ) -> str:
    doc = json.loads(fa.router_raw("answer", reply=ROUTER_REPLY))
    doc["deep_question"] = question
    return json.dumps(doc, ensure_ascii=False)


def router_ask(text: str = ASK_REPLY) -> str:
    raw: str = fa.router_raw("ask", reply=text, why="людина говорить про інше")
    return raw


def card_raw(reply_text: str, phase: str = "a_one", deep_question: str | None = None) -> str:
    return json.dumps(
        {
            "reply": reply_text,
            "current_phase_id": phase,
            "phase_exit_met": False,
            "map_updates": [],
            "deep_question": deep_question,
        },
        ensure_ascii=False,
    )


# --- the model double ------------------------------------------------------------------------------------

USAGE = pl.Usage(prompt_tokens=10, output_tokens=5, thought_tokens=0)
REV = pl.KnowledgeRev(rev=3, n=7)
Planned = str | BaseException
SearchPlan = tuple[str, pl.Found | None] | BaseException


@dataclass
class Stream:
    deltas: list[str]
    raw: str
    found: pl.Found | None = None


@dataclass
class Call:
    kind: str  # stream, router, plan, report, consent, update, search
    system: str
    contents: list[pl.Turn]
    prompt: str | None = None

    @property
    def text(self) -> str:
        return "\n".join(t.text for t in self.contents)


def _kind(schema: Any) -> str:
    if isinstance(schema, type) and issubclass(schema, RouterAnswer):
        return "router"
    if isinstance(schema, type) and issubclass(schema, DeepPlan):
        return "plan"
    if isinstance(schema, type) and issubclass(schema, DeepReport):
        return "report"
    if isinstance(schema, type) and any(c.__name__ == "DeepConsent" for c in schema.__mro__):
        return "consent"
    return "update"


@dataclass
class DcLlm:
    router: list[Planned] = field(default_factory=list)
    plans: list[Planned] = field(default_factory=list)
    reports: list[Planned] = field(default_factory=list)
    consents: list[Planned] = field(default_factory=list)
    updates: list[Planned] = field(default_factory=list)
    streams: list[Stream | BaseException] = field(default_factory=list)
    searches: Mapping[str, SearchPlan] = field(default_factory=lambda: dict(SEARCHES))
    calls: list[Call] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def of(self, kind: str) -> list[Call]:
        with self.lock:
            return [c for c in self.calls if c.kind == kind]

    def prompts(self) -> list[str]:
        return [str(c.prompt) for c in self.of("search")]

    def _record(self, call: Call) -> None:
        with self.lock:
            self.calls.append(call)

    def stream_json(
        self, system: str, contents: Sequence[pl.Turn], schema: type[BaseModel], rev: pl.KnowledgeRev | None
    ) -> Iterator[pl.ReplyDelta | pl.Done]:
        self._record(Call("stream", system, list(contents)))
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
        kind = _kind(schema)
        self._record(Call(kind, system, list(contents)))
        queue = {
            "router": self.router,
            "plan": self.plans,
            "report": self.reports,
            "consent": self.consents,
            "update": self.updates,
        }[kind]
        if not queue:
            raise AssertionError(f"generate_json ({kind}) was called and the scenario planned no such call")
        planned = queue.pop(0)
        if isinstance(planned, BaseException):
            raise planned
        return schema.model_validate_json(planned)

    def search_text(
        self, system: str, prompt: str, rev: pl.KnowledgeRev | None
    ) -> tuple[str, pl.Found | None]:
        self._record(Call("search", system, [], prompt))
        if prompt not in self.searches:
            raise AssertionError(f"search_text with a prompt the scenario did not plan: {prompt!r}")
        plan = self.searches[prompt]
        if isinstance(plan, BaseException):
            raise plan
        return plan


# --- contexts for the unit tests ----------------------------------------------------------------------

HISTORY = [
    Turn(role="user", text="Хочу продавати консалтинг у Німеччині."),
    Turn(role="model", text="Кому саме ви хочете продавати?"),
]
GOAL = MapItem(id="i1", type="goal", text="продавати консалтинг", turn="t1")


def context(
    text: str = "Досліди, будь ласка, глибоко.",
    history: Sequence[Turn] = HISTORY,
    phase: str | None = "a_two",
    turn_no: int = 3,
    **extra: Any,
) -> FacilitationContext:
    cls: Any = FacilitationContext
    made: FacilitationContext = cls(
        card_id="alpha",
        history=list(history),
        problem_map=ProblemMap(items=[GOAL], phase_id=phase, last_turn=turn_no - 1),
        turn_no=turn_no,
        text=text,
        language=None,
        routing=(),
        **extra,
    )
    return made


# --- the workspace side ------------------------------------------------------------------------------------

T0: datetime = rq.T0
DAY = timedelta(hours=25)


def store_at(tmp_path: Path) -> LocalStorage:
    """A new storage object on the same folder: what one answer left, the next reads from disk."""
    return LocalStorage(tmp_path)


def new_topic(tmp_path: Path, card: str | None = None) -> TopicRef:
    store = store_at(tmp_path)
    ref: TopicRef = rq.topic(store)
    if card is not None:
        rq.put_routing(store, ref, [rq.d_choose(1, card)])
    return ref


def fac(llm: DcLlm) -> Any:
    return partial(respond, knowledge=rq.knowledge(), llm=llm)


def say(
    tmp_path: Path, facilitate: Any, ref: TopicRef, text: str, at: datetime = T0, question: Any = None
) -> tuple[list[ReplyEvent], str]:
    got = list(reply(store_at(tmp_path), facilitate, rq.ALICE, ref, text, at, question=question))
    return got, "".join(e.text for e in got if isinstance(e, Delta))


def again(tmp_path: Path, facilitate: Any, ref: TopicRef, at: datetime = T0) -> tuple[list[ReplyEvent], str]:
    got = list(retry(store_at(tmp_path), facilitate, rq.ALICE, ref, at))
    return got, "".join(e.text for e in got if isinstance(e, Delta))


def recorded(tmp_path: Path, ref: TopicRef, at: datetime = T0) -> str:
    return open_topic(store_at(tmp_path), rq.ALICE, ref, at).sessions[-1].turns[-1].text


def raw_file(tmp_path: Path, ref: TopicRef, name: str) -> bytes | None:
    return store_at(tmp_path).read("users", rq.topic_path(ref, name))


def pending_file(tmp_path: Path, ref: TopicRef) -> Any:
    data = raw_file(tmp_path, ref, "deep_pending.json")
    return None if data is None else json.loads(data)


def put_pending_raw(tmp_path: Path, ref: TopicRef, data: bytes) -> None:
    store_at(tmp_path).write("users", rq.topic_path(ref, "deep_pending.json"), data, "application/json")


def routing_raw(tmp_path: Path, ref: TopicRef) -> bytes | None:
    return raw_file(tmp_path, ref, "routing.json")


def propose_on_router(tmp_path: Path, ref: TopicRef, plan: str = PLAN_RAW_1, at: datetime = T0) -> DcLlm:
    """One answer: the router decides to research deep, the system shows the proposal."""
    llm = DcLlm(router=[router_deep()], plans=[plan])
    got, _ = say(tmp_path, fac(llm), ref, "Досліди глибоко, як Mittelstand купує консалтинг.", at)
    assert type(got[-1]).__name__ == "Answered", got[-1]
    return llm


def agree_llm(**kwargs: Any) -> DcLlm:
    """«так»: the consent call says yes, then the searches and the report; no plan is planned."""
    return DcLlm(consents=[consent_raw("yes")], reports=[REPORT_RAW], **kwargs)


STEP = "Поговорити з трьома клієнтами"


def Q(arg: str) -> str:
    """The injected `Question` of step-results."""
    return "Минулого разу ви обрали крок «" + arg + "». Як він вийшов?"


@dataclass
class Scripted:
    """A `Facilitate` double: every call takes the next script; an exception in it is raised."""

    scripts: list[list[Any]]
    contexts: list[FacilitationContext] = field(default_factory=list)

    def __call__(self, ctx: FacilitationContext) -> Iterator[Any]:
        self.contexts.append(ctx)
        if not self.scripts:
            raise AssertionError("facilitate was called more times than the scenario planned")
        return self._run(self.scripts.pop(0))

    def _run(self, script: list[Any]) -> Iterator[Any]:
        for step in script:
            if isinstance(step, BaseException):
                raise step
            yield step


class Down(Exception):
    """The model failed inside the answer: workspace answers it with Failed."""


def plain(text: str, updates: Sequence[MapUpdate] = ()) -> list[Any]:
    return [
        ReplyDelta(text=text),
        FacilitatorUpdate(reply=text, current_phase_id=None, phase_exit_met=False, map_updates=list(updates)),
    ]


def chosen_step(turn: int) -> MapUpdate:
    return MapUpdate(op="add", id="s1", type="chosen_step", text=STEP, turn=f"t{turn}")
