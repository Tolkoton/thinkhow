"""The analyzer: one Gemini call per topic about the turns it has not analyzed → a set of observations by
the rules of analysis (learning-loop S2, F10).

Task 202: no closing, no silence threshold; what was analyzed is read from the observation file names (G6).
The card that led each anchor comes from routing.json, not from the model. Reads people's topics through
workspace only; writes only system/learning/observations/ (I2).
"""

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, create_model

from thinkhow import knowledge, workspace
from thinkhow.facilitation import Decision
from thinkhow.learning.observations import Observation, ObservationSet
from thinkhow.platform.llm import Llm, LlmUnavailable, Turn
from thinkhow.platform.log import log_event
from thinkhow.platform.storage import Storage

ANALYZER = """Ти — аналізатор ThinkHow. Ти читаєш нові репліки однієї теми (з часу минулого аналізу), у яких
фасилітатор вів людину за моделлю мислення, щоб вона сама дійшла до ясності (без готових відповідей).
Репліки під рядком «Контекст» уже проаналізовано — вони лише для розуміння; висновки і якорі — лише про нові.
Рядки в квадратних дужках кажуть, який метод вів розмову з цієї репліки і що пропонував роутер.

Правила аналізу:
- просувається (progress) — у новій репліці людини з'явилось нове розуміння, рішення чи крок;
- застрягла (stuck) — людина каже, що не знає чи не може знати відповіді, і питання лишається відкритим
  (особливо кілька разів у розмові, не обов'язково в сусідніх репліках); фасилітатор питає те саме вдруге;
  людина відповідає не на питання; людина просить того, у чому система їй відмовила;
- чи підійшов метод (method_fit) — чи метод, що вів, допоміг людині з тим, із чим вона прийшла;
- step — рядок «[Результат кроку …]» стоїть перед реплікою людини, і правило таке:
  результат кроку — що він каже про спосіб думати, яким людина дійшла до кроку;
- причина (cause): router — запропоновано чи обрано не той спосіб думати; method — сам метод не підійшов до
  ситуації; facilitation — як ставились питання і як вели; circumstances — обставини людини.

Напиши кілька спостережень українською, кожне — про одне місце. Якщо те саме (наприклад, застрягання)
повторюється в різних репліках, кожне таке місце — окреме спостереження зі своїм якорем, а не одне спільне про
останнє; не пропускай жодного місця, де людина застрягла чи просунулась.
- kind — progress, stuck, method_fit чи step;
- finding — що там сталося у веденні людини до ясності, коротко, своїми словами; не цитуй людину і не
  переказуй подробиць її життя понад потрібне для висновку;
- worked — чи спрацювало ведення в цьому місці;
- cause — чия це «заслуга» чи «вина» за правилами вище;
- anchor — одна з нових реплік, де це видно найкраще («t<номер>»); для «застрягла» — репліка людини, що це
  показує."""
CONTEXT = "[Контекст — уже проаналізовано, не якір:]"
NEW = "[Нові репліки:]"
RANGE_FILE = re.compile(r"^t(\d+)-t(\d+)\.json$")
LEGACY_FILE = re.compile(r"^s(\d+)\.json$")
KIND = Literal["progress", "stuck", "method_fit", "step"]
OUTCOME_WORDS = {"worked": "вийшло", "not_worked": "не вийшло", "unexpected": "несподіванка"}
CAUSE = Literal["router", "method", "facilitation", "circumstances"]
END_WORDS = {"done": "пройдено", "not_fit": "не підходить"}


@dataclass(frozen=True)
class AnalyzeReport:
    written: int
    skipped: int
    failed: int


def answer_schema(turn_nos: Sequence[int]) -> type[BaseModel]:
    """observations: kind, finding, worked, cause, anchor — anchor narrowed to the new turns, an `enum`."""
    anchors = [f"t{n}" for n in turn_nos]
    anchor: Any = Literal[tuple(anchors)]
    one = create_model(
        "ObservationAnswerItem",
        kind=(KIND, ...),
        finding=(str, Field(min_length=1)),
        worked=(bool, ...),
        cause=(CAUSE, ...),
        anchor=(anchor, Field(json_schema_extra=_enum_of(anchors))),
    )
    many: Any = list.__class_getitem__(one)
    return create_model("ObservationAnswer", observations=(many, Field(min_length=1)))


def _enum_of(anchors: list[str]) -> Callable[[dict[str, Any]], None]:
    """pydantic writes `const` for a one-value Literal; Vertex gets the `enum` it was verified with."""

    def fix(schema: dict[str, Any]) -> None:
        schema.pop("const", None)
        schema.update({"type": "string", "enum": list(anchors)})

    return fix


def analyze(storage: Storage, llm: Llm, now: datetime) -> AnalyzeReport:
    """Flow: the card titles once → every topic → its new turns → one call, one file (Q1, Q2 of task 202)."""
    if now.tzinfo is None:
        raise ValueError("now must carry a time zone")
    titles = _titles(storage)
    refs = workspace.all_topics_for_learning(storage)
    outcomes = [_topic(storage, llm, ref, now, titles) for ref in refs]
    report = AnalyzeReport(outcomes.count("written"), outcomes.count("skipped"), outcomes.count("failed"))
    log_event("analyze_done", written=report.written, skipped=report.skipped, failed=report.failed)
    return report


def _titles(storage: Storage) -> dict[str, str]:
    try:
        return {cid: card.title for cid, card in knowledge.current(storage).cards.items()}
    except knowledge.KnowledgeMissing:
        return {}


def _topic(storage: Storage, llm: Llm, ref: workspace.TopicRef, now: datetime, titles: dict[str, str]) -> str:
    """Flow: sessions, routing, observation names → the new turns and their context → one set."""
    folder = f"learning/observations/{ref.uid}/{ref.topic_id}/"
    try:
        sessions = workspace.topic_sessions(storage, ref, now)
        routing = workspace.topic_routing(storage, ref)
        steps = workspace.step_results_for_learning(storage, ref)
        seen = _seen(storage.list("system", folder), folder, sessions)
    except Exception as exc:
        _failed(ref, exc)
        return "failed"
    new = [t for s in sessions for t in s.turns if t.no > seen]
    if not new:
        return "skipped"
    context = next(s for s in sessions if new[0] in s.turns).turns
    context = [t for t in context if t.no < new[0].no]
    schema = answer_schema([t.no for t in new])
    marks = _marks(routing, titles)
    for record in steps:  # the result of a step before the person's answer to its question (S6), no `clearer`
        if record.outcome is not None:
            line = f"[Результат кроку «{record.step}»: {OUTCOME_WORDS[record.outcome]} — {record.said}]"
            marks.setdefault(record.asked_turn + 1, []).append(line)
    try:
        answer = llm.generate_json(ANALYZER, [Turn("user", _text(context, new, marks))], schema, None)
    except (ValidationError, LlmUnavailable) as exc:
        _failed(ref, exc, new)
        return "failed"
    _write(storage, ref, new, answer.model_dump()["observations"], routing, now)
    return "written"


def _seen(paths: Sequence[str], folder: str, sessions: Sequence[workspace.Session]) -> int:
    """The last analyzed turn: `t<a>-t<b>.json` → b; an old `s<n>.json` → the last turn of session n (Q4)."""
    last_of = {s.no: s.turns[-1].no for s in sessions if s.turns}
    seen = 0
    for path in paths:
        name = path.removeprefix(folder)
        if m := RANGE_FILE.match(name):
            seen = max(seen, int(m.group(2)))
        elif (m := LEGACY_FILE.match(name)) and int(m.group(1)) in last_of:
            seen = max(seen, last_of[int(m.group(1))])
    return seen


def _marks(routing: Sequence[Decision], titles: dict[str, str]) -> dict[int, list[str]]:
    """The state lines by the turn they stand before: choose/offer from turn + 1, end from turn + 2."""
    marks: dict[int, list[str]] = {}
    for d in routing:
        if d.kind == "choose" and d.card_id:
            title = titles.get(d.card_id)
            name = f"{title} ({d.card_id})" if title else d.card_id
            marks.setdefault(d.turn + 1, []).append(f"[Метод: {name}]")
        elif d.kind == "offer":
            ids = ", ".join(c.card_id for c in d.candidates)
            marks.setdefault(d.turn + 1, []).append(f"[Роутер: запропоновано {ids}]")
        elif d.kind == "end" and d.card_id:
            how = END_WORDS.get(str(d.end), str(d.end))
            marks.setdefault(d.turn + 2, []).append(f"[Метод закінчено: {d.card_id} — {how}]")
    return marks


def card_at(routing: Sequence[Decision], turn: int) -> str | None:
    """The card that led the turn: the last decision acting on it, if a choose (end acts from turn + 2)."""
    acting = [d for d in routing if (d.turn + 1 < turn if d.kind == "end" else d.turn < turn)]
    if acting and acting[-1].kind == "choose":
        return acting[-1].card_id
    return None


def _write(
    storage: Storage,
    ref: workspace.TopicRef,
    new: Sequence[workspace.NumberedTurn],
    answers: Sequence[dict[str, Any]],
    routing: Sequence[Decision],
    now: datetime,
) -> None:
    name = f"t{new[0].no}-t{new[-1].no}"
    observations = [_observation(ref, name, k, a, routing, now) for k, a in enumerate(answers, start=1)]
    found = ObservationSet(
        uid=ref.uid,
        topic_id=ref.topic_id,
        first_turn=new[0].no,
        last_turn=new[-1].no,
        analyzed_at=now,
        observations=observations,
    )
    storage.write(
        "system",
        f"learning/observations/{ref.uid}/{ref.topic_id}/{name}.json",
        found.model_dump_json().encode("utf-8"),
        "application/json",
    )


def _observation(
    ref: workspace.TopicRef,
    name: str,
    k: int,
    answer: dict[str, Any],
    routing: Sequence[Decision],
    now: datetime,
) -> Observation:
    turn = int(answer["anchor"][1:])
    return Observation(
        id=f"{ref.uid}/{ref.topic_id}/{name}/{k}",
        turn=turn,
        link=f"/topics/{ref.uid}/{ref.topic_id}#t{turn}",
        kind=answer["kind"],
        worked=answer["worked"],
        finding=answer["finding"],
        cause=answer["cause"],
        card_id=card_at(routing, turn),
        analyzed_at=now,
    )


def _failed(ref: workspace.TopicRef, exc: Exception, new: Sequence[workspace.NumberedTurn] = ()) -> None:
    """The topic and the range that failed (no text); the topic-read failure has no range."""
    error = type(exc).__name__
    if not new:
        log_event("analyze_failed", severity="WARNING", uid=ref.uid, topic_id=ref.topic_id, error=error)
        return
    log_event(
        "analyze_failed",
        severity="WARNING",
        uid=ref.uid,
        topic_id=ref.topic_id,
        error=error,
        first_turn=new[0].no,
        last_turn=new[-1].no,
    )


def _text(
    context: Sequence[workspace.NumberedTurn],
    new: Sequence[workspace.NumberedTurn],
    marks: dict[int, list[str]],
) -> str:
    """The new turns, after the analyzed turns of their session as context, with the method's state lines."""
    lines = [CONTEXT, *_lines(context, marks), NEW] if context else []
    return "\n".join(lines + _lines(new, marks))


def _lines(turns: Sequence[workspace.NumberedTurn], marks: dict[int, list[str]]) -> list[str]:
    out: list[str] = []
    for turn in turns:
        out += marks.get(turn.no, [])
        out.append(f"#{turn.no} {'людина' if turn.role == 'user' else 'фасилітатор'}: {turn.text}")
    return out
