"""Helpers for the research-deep contract tests (slice tester; built from the contract, not the code).

The sealed helpers of research-quick (`rq_fakes`: cards alpha/beta, contexts, the genai response builder,
the journal capture, the research.json helpers) and of fact-answer (`fa_fakes`: router answers, the texts of
router.md and research.md, `flat`) are reused as they are: their folders are put on `sys.path`.

- DeepLlm: a fake `platform.llm.Llm` with `search_text`. `generate_json` answers by the schema it was given:
  a `RouterAnswer` schema from `router`, `DeepPlan` from `plans`, `DeepReport` from `reports`, any other
  (a retry of an update) from `updates`; each planned raw JSON is validated by that schema, so an invalid
  plan is a `ValidationError` inside the call. `stream_json` yields the planned deltas, then
  `Done(raw, usage, found)`. `search_text` answers by the prompt from `searches`: a `(text, found)`, an
  exception to raise, or a callable of the prompt. Every call is recorded (thread-safe).
- The texts the contract fixes word for word: the three rules of `deep.md`, the sentence of `research.md`,
  the section of `deep_field.md`, the sentence added to `router.md`.
- A deep scenario written by hand: a question, a plan of three sub-questions, their findings and sources,
  a report with two facts, and the sources line of the cycle.
"""

from __future__ import annotations

import json
import sys
import threading
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = ["fa", "rq"]  # the sibling helpers, re-exported; every name defined here is exported as well

HERE = Path(__file__).resolve().parent
for sibling in ("research_quick", "fact_answer"):
    path = str(HERE.parent / sibling)
    if path not in sys.path:
        sys.path.insert(0, path)

import fa_fakes as fa  # noqa: E402, F401  (re-exported: the tests import the sibling helpers from here)
import rq_fakes as rq  # noqa: E402, F401
from pydantic import BaseModel  # noqa: E402

from thinkhow.facilitation.route import RouterAnswer  # noqa: E402
from thinkhow.facilitation.types import (  # noqa: E402
    DeepPlan,
    DeepReport,
    FacilitationContext,
    MapItem,
    ProblemMap,
    Source,
    Turn,
)
from thinkhow.platform import llm as pl  # noqa: E402

# --- the texts of the contract, word for word -------------------------------------------------------

PLAN_RULE = (
    "Розклади питання на 2–4 підпитання для пошуку в інтернеті, кожне — коротке речення мовою людини. "
    "intro — одне речення людині, що ти досліджуєш і що це займе близько двох хвилин."
)
SEARCH_RULE = "Знайди факти з джерелами на це підпитання. Коротко, з числами, назвами й датами."
REPORT_RULE = (
    "Склади стислий звіт людині на її питання з цих знахідок: що відомо, з числами; де джерела розходяться — "
    "скажи так. Без посилань у тексті (джерела система допише сама). Не радь, що їй робити, і не оцінюй її "
    "варіантів. Закінчи одним питанням до людини: що з цього для неї важливо далі. У facts — кожен факт, на "
    "який вона спиратиметься, одним реченням, з числом чи назвою, без посилань."
)
RESEARCH_SENTENCE = (
    "Коли питання багатогранне (ринок, кілька шляхів, порівняння) і швидкого пошуку замало, запропонуй "
    "людині глибоке дослідження: скажи, що це займе близько двох хвилин, і спитай, чи шукати."
)
DEEP_FIELD_HEAD = "# Глибоке дослідження"
DEEP_FIELD_BODY = (
    "Коли людина погодилась на глибоке дослідження або сама просить дослідити глибоко — постав питання "
    "дослідження в deep_question (одне речення: що саме з'ясувати), а в reply коротко скажи, що починаєш. "
    "Інакше deep_question — null."
)
ROUTER_DEEP_SENTENCE = (
    'Так само "answer" — коли людина погоджується на глибоке дослідження, яке щойно запропоновано, або сама '
    "просить дослідити глибоко, а картки не обрано: тоді deep_question — одне речення, що саме з'ясувати."
)
QUESTION_HEAD = "\n\n[Питання дослідження]\n"
RULE_PL = (
    "Відповідай мовою людини — Polski (pl-PL): цю мову вона обрала для розмов з ThinkHow, "
    "і це правило важливіше за «мовою останньої репліки» вище. "
    "Іншою мовою — лише якщо людина прямо попросить. "
    "Ніколи не відповідай російською — ні на репліку російською, ні на прохання."
)


def flat(text: str) -> str:
    """The text with every run of whitespace made one space (the line breaks of a wrapped paragraph)."""
    return " ".join(text.split())


# --- a deep scenario, by hand --------------------------------------------------------------------------

DQ = "Як компанії Mittelstand купують консалтинг і де швидше перші гроші?"
INTRO = "Досліджую, як Mittelstand купує консалтинг, — це займе близько двох хвилин."
QA = "Як Mittelstand обирає консультантів?"
QB = "Скільки коштує проєкт консалтингу для Mittelstand?"
QC = "Де консультанти знаходять перших клієнтів у Саксонії?"
QD = "Які програми IHK оплачують консалтинг?"

PA = pl.Source("Mittelstand Studie", "https://a.example/mittelstand")
PB = pl.Source("Beratermarkt", "https://b.example/markt")
PC = pl.Source("IHK Leipzig", "https://c.example/ihk")
PD = pl.Source("Förderprogramm", "https://d.example/foerder")
SA = Source("Mittelstand Studie", "https://a.example/mittelstand")
SB = Source("Beratermarkt", "https://b.example/markt")
SC = Source("IHK Leipzig", "https://c.example/ihk")
SD = Source("Förderprogramm", "https://d.example/foerder")
LINK_A = "[Mittelstand Studie](https://a.example/mittelstand)"
LINK_B = "[Beratermarkt](https://b.example/markt)"
LINK_C = "[IHK Leipzig](https://c.example/ihk)"
LINK_D = "[Förderprogramm](https://d.example/foerder)"

TEXT_A = "ЗНАХІДКА-А: 62% фірм Mittelstand беруть консультанта за рекомендацією."
TEXT_B = "ЗНАХІДКА-Б: проєкт коштує від 8 000 до 25 000 євро."
TEXT_C = "ЗНАХІДКА-В: перші клієнти приходять через IHK і галузеві зустрічі."
TEXT_D = "ЗНАХІДКА-Г: програма go-digital оплачує до 50%."

FOUND_A = pl.Found(("Mittelstand Berater Auswahl",), (PA,), None)
FOUND_B = pl.Found(("Beratung Mittelstand Kosten",), (PB, PA), "<div>підказки Б</div>")
FOUND_C = pl.Found(("Berater erste Kunden Sachsen",), (PC,), "")
FOUND_D = pl.Found(("go-digital Förderung Beratung",), (PD,), None)

REPORT = (
    "Mittelstand здебільшого бере консультантів за рекомендацією (62%), проєкт коштує 8–25 тис. євро, "
    "а перші клієнти приходять через IHK. Що з цього для вас важливо далі?"
)
FACT_1 = "62% фірм Mittelstand беруть консультанта за рекомендацією."
FACT_2 = "Проєкт консалтингу для Mittelstand коштує 8 000–25 000 євро."
# the cycle's sources line for A, B, C (B repeats A): every url once, in the order of the sub-questions
LINE_ABC = "\n\nДжерела: " + ", ".join([LINK_A, LINK_B, LINK_C])

SEARCHES_ABC: dict[str, Any] = {QA: (TEXT_A, FOUND_A), QB: (TEXT_B, FOUND_B), QC: (TEXT_C, FOUND_C)}
QUERIES_ABC = ("Mittelstand Berater Auswahl", "Beratung Mittelstand Kosten", "Berater erste Kunden Sachsen")


def plan_raw(intro: str = INTRO, questions: Sequence[str] = (QA, QB, QC)) -> str:
    return json.dumps({"intro": intro, "questions": list(questions)}, ensure_ascii=False)


def report_raw(report: str = REPORT, facts: Sequence[str] = (FACT_1, FACT_2)) -> str:
    return json.dumps({"report": report, "facts": list(facts)}, ensure_ascii=False)


INVALID_PLAN = json.dumps({"intro": INTRO}, ensure_ascii=False)
INVALID_REPORT = json.dumps({"facts": [FACT_1]}, ensure_ascii=False)


def steps_lines(text: str) -> list[str]:
    """The lines of the steps text: `intro`, then `- <sub-question>` each."""
    return text.splitlines()


def want_steps(intro: str = INTRO, questions: Sequence[str] = (QA, QB, QC)) -> list[str]:
    return [intro, *[f"- {q}" for q in questions]]


def fact_update(fid: str, text: str, turn: str) -> dict[str, Any]:
    return {"op": "add", "id": fid, "type": "fact", "text": text, "turn": turn}


# --- facilitator answers under the router (raw JSON) -------------------------------------------------

_OMIT = object()


def card_answer(
    reply: str,
    phase: str | None = "a_one",
    exit_met: bool = False,
    updates: Sequence[dict[str, Any]] = (),
    deep_question: Any = _OMIT,
) -> str:
    doc: dict[str, Any] = {
        "reply": reply,
        "current_phase_id": phase,
        "phase_exit_met": exit_met,
        "map_updates": list(updates),
    }
    if deep_question is not _OMIT:
        doc["deep_question"] = deep_question
    return json.dumps(doc, ensure_ascii=False)


def card_update(phase: str | None = "a_one", deep_question: Any = _OMIT) -> str:
    doc: dict[str, Any] = {"current_phase_id": phase, "phase_exit_met": False, "map_updates": []}
    if deep_question is not _OMIT:
        doc["deep_question"] = deep_question
    return json.dumps(doc, ensure_ascii=False)


def with_deep_question(raw: str, deep_question: Any) -> str:
    doc = json.loads(raw)
    doc["deep_question"] = deep_question
    return json.dumps(doc, ensure_ascii=False)


# --- contexts --------------------------------------------------------------------------------------------

HISTORY = [
    Turn(role="user", text="Хочу продавати консалтинг у Німеччині."),
    Turn(role="model", text="Кому саме ви хочете продавати?"),
]


def ctx(
    items: Sequence[MapItem] = (MapItem(id="i1", type="goal", text="продавати консалтинг", turn="t1"),),
    turn_no: int = 3,
    language: str | None = None,
    text: str = "Так, досліди.",
    card_id: str = "alpha",
    routing: Any = None,
) -> FacilitationContext:
    return FacilitationContext(
        card_id=card_id,
        history=list(HISTORY),
        problem_map=ProblemMap(items=list(items), phase_id="a_one", last_turn=turn_no - 1),
        turn_no=turn_no,
        text=text,
        language=language,
        routing=routing,
    )


# --- the model double -------------------------------------------------------------------------------------

USAGE = pl.Usage(prompt_tokens=10, output_tokens=5, thought_tokens=0)
SearchPlan = tuple[str, pl.Found | None] | BaseException | Callable[[str], tuple[str, pl.Found | None]]


@dataclass
class Stream:
    deltas: list[str]
    raw: str
    found: pl.Found | None = None


@dataclass
class Call:
    kind: str  # "stream", "router", "plan", "report", "update", "search"
    system: str
    contents: list[pl.Turn]
    schema: Any
    rev: pl.KnowledgeRev | None
    prompt: str | None = None


@dataclass
class DeepLlm:
    streams: list[Stream | BaseException] = field(default_factory=list)
    router: list[str] = field(default_factory=list)
    plans: list[str] = field(default_factory=list)
    reports: list[str] = field(default_factory=list)
    updates: list[str] = field(default_factory=list)
    searches: Mapping[str, SearchPlan] = field(default_factory=dict)
    calls: list[Call] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def of(self, kind: str) -> list[Call]:
        with self.lock:
            return [c for c in self.calls if c.kind == kind]

    @property
    def deep_calls(self) -> list[Call]:
        return [c for c in self.calls if c.kind in ("plan", "report", "search")]

    def _record(self, call: Call) -> None:
        with self.lock:
            self.calls.append(call)

    def stream_json(
        self, system: str, contents: Sequence[pl.Turn], schema: type[BaseModel], rev: pl.KnowledgeRev | None
    ) -> Iterator[pl.ReplyDelta | pl.Done]:
        self._record(Call("stream", system, list(contents), schema, rev))
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
        if isinstance(schema, type) and issubclass(schema, RouterAnswer):
            kind, queue = "router", self.router
        elif isinstance(schema, type) and issubclass(schema, DeepPlan):
            kind, queue = "plan", self.plans
        elif isinstance(schema, type) and issubclass(schema, DeepReport):
            kind, queue = "report", self.reports
        else:
            kind, queue = "update", self.updates
        self._record(Call(kind, system, list(contents), schema, rev))
        if not queue:
            raise AssertionError(f"generate_json ({kind}) was called more times than the scenario planned")
        return schema.model_validate_json(queue.pop(0))

    def search_text(
        self, system: str, prompt: str, rev: pl.KnowledgeRev | None
    ) -> tuple[str, pl.Found | None]:
        self._record(Call("search", system, [], None, rev, prompt))
        if prompt not in self.searches:
            raise AssertionError(
                f"search_text was called with a prompt the scenario did not plan: {prompt!r}"
            )
        plan = self.searches[prompt]
        if isinstance(plan, BaseException):
            raise plan
        if callable(plan):
            return plan(prompt)
        return plan


def deep_llm(
    plans: Sequence[str] = (),
    reports: Sequence[str] = (),
    searches: Mapping[str, SearchPlan] | None = None,
    streams: Sequence[Stream | BaseException] = (),
    router: Sequence[str] = (),
    updates: Sequence[str] = (),
) -> DeepLlm:
    return DeepLlm(
        streams=list(streams),
        router=list(router),
        plans=list(plans),
        reports=list(reports),
        updates=list(updates),
        searches=dict(SEARCHES_ABC if searches is None else searches),
    )


def full_deep(**kwargs: Any) -> DeepLlm:
    """The planned plan, the three searches and the report of the hand-written scenario."""
    return deep_llm(plans=[plan_raw()], reports=[report_raw()], **kwargs)
