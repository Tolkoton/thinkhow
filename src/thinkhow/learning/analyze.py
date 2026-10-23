"""The analyzer: one Gemini call per topic about the turns it has not analyzed → one observation, one anchor.

Task 202: no closing, no silence threshold; what was analyzed is read from the observation file names (G6).
Reads people's topics through workspace only; writes only system/learning/observations/ (I2).
"""

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, create_model

from thinkhow import workspace
from thinkhow.platform.llm import Llm, LlmUnavailable, Turn
from thinkhow.platform.log import log_event
from thinkhow.platform.storage import Storage

ANALYZER = """Ти — аналізатор ThinkHow. Ти читаєш нові репліки однієї теми (з часу минулого аналізу), у яких
фасилітатор вів людину за моделлю мислення, щоб вона сама дійшла до ясності (без готових відповідей).
Репліки під рядком «Контекст» уже проаналізовано — вони лише для розуміння; висновок і якір — лише про нові.
Напиши одне спостереження українською:
- finding — що у нових репліках спрацювало чи не спрацювало у веденні людини до ясності, коротко, своїми
  словами;
  не цитуй людину і не переказуй подробиць її життя понад потрібне для висновку;
- worked — чи спрацювало;
- cause — чия це «заслуга» чи «вина»: method (вибір моделі мислення), facilitation (ведення розмови) чи
  circumstances (обставини людини);
- anchor — одна з нових реплік, де це видно найкраще, її номер з переліку («t<номер>»)."""
CONTEXT = "[Контекст — уже проаналізовано, не якір:]"
NEW = "[Нові репліки:]"
RANGE_FILE = re.compile(r"^t(\d+)-t(\d+)\.json$")
LEGACY_FILE = re.compile(r"^s(\d+)\.json$")
CAUSE = Literal["method", "facilitation", "circumstances"]


class Observation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    uid: str
    topic_id: str
    first_turn: int
    last_turn: int
    turn: int
    link: str
    worked: bool
    finding: str
    cause: CAUSE
    analyzed_at: datetime


@dataclass(frozen=True)
class AnalyzeReport:
    written: int
    skipped: int
    failed: int


def answer_schema(turn_nos: Sequence[int]) -> type[BaseModel]:
    """finding, worked, cause, anchor — anchor narrowed to this session's turns, always an `enum` (Q2)."""
    anchors = [f"t{n}" for n in turn_nos]
    anchor: Any = Literal[tuple(anchors)]
    return create_model(
        "ObservationAnswer",
        finding=(str, Field(min_length=1)),
        worked=(bool, ...),
        cause=(CAUSE, ...),
        anchor=(anchor, Field(json_schema_extra=_enum_of(anchors))),
    )


def _enum_of(anchors: list[str]) -> Callable[[dict[str, Any]], None]:
    """pydantic writes `const` for a one-value Literal; Vertex gets the `enum` it was verified with."""

    def fix(schema: dict[str, Any]) -> None:
        schema.pop("const", None)
        schema.update({"type": "string", "enum": list(anchors)})

    return fix


def analyze(storage: Storage, llm: Llm, now: datetime) -> AnalyzeReport:
    """Flow: every topic → its turns after the last analyzed one → one call, one file (Q1, Q2 of task 202)."""
    if now.tzinfo is None:
        raise ValueError("now must carry a time zone")
    outcomes = [_topic(storage, llm, ref, now) for ref in workspace.all_topics_for_learning(storage)]
    report = AnalyzeReport(outcomes.count("written"), outcomes.count("skipped"), outcomes.count("failed"))
    log_event("analyze_done", written=report.written, skipped=report.skipped, failed=report.failed)
    return report


def _topic(storage: Storage, llm: Llm, ref: workspace.TopicRef, now: datetime) -> str:
    """Flow: sessions + observation names → seen → the new turns and their context → one observation."""
    folder = f"learning/observations/{ref.uid}/{ref.topic_id}/"
    try:
        sessions = workspace.topic_sessions(storage, ref, now)
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
    try:
        answer = llm.generate_json(ANALYZER, [Turn("user", _text(context, new))], schema, None)
    except (ValidationError, LlmUnavailable) as exc:
        _failed(ref, exc, new)
        return "failed"
    _write(storage, ref, new, answer.model_dump(), now)
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


def _write(
    storage: Storage,
    ref: workspace.TopicRef,
    new: Sequence[workspace.NumberedTurn],
    answer: dict[str, Any],
    now: datetime,
) -> None:
    turn = int(answer["anchor"][1:])
    observation = Observation(
        uid=ref.uid,
        topic_id=ref.topic_id,
        first_turn=new[0].no,
        last_turn=new[-1].no,
        turn=turn,
        link=f"/topics/{ref.uid}/{ref.topic_id}#t{turn}",
        analyzed_at=now,
        **{k: v for k, v in answer.items() if k in ("worked", "finding", "cause")},
    )
    name = f"t{new[0].no}-t{new[-1].no}.json"
    storage.write(
        "system",
        f"learning/observations/{ref.uid}/{ref.topic_id}/{name}",
        observation.model_dump_json().encode("utf-8"),
        "application/json",
    )


def _failed(ref: workspace.TopicRef, exc: Exception, new: Sequence[workspace.NumberedTurn] = ()) -> None:
    """The topic and the range that failed (no text); the topic-read failure has no range."""
    error = type(exc).__name__
    if not new:
        log_event("analyze_failed", severity="WARNING", uid=ref.uid, topic_id=ref.topic_id, error=error)
        return
    first, last = new[0].no, new[-1].no
    log_event(
        "analyze_failed",
        severity="WARNING",
        uid=ref.uid,
        topic_id=ref.topic_id,
        error=error,
        first_turn=first,
        last_turn=last,
    )


def _text(context: Sequence[workspace.NumberedTurn], new: Sequence[workspace.NumberedTurn]) -> str:
    """The new turns, after the analyzed turns of their session as context under its own header (Q8)."""
    lines = [CONTEXT, *map(_line, context), NEW] if context else []
    return "\n".join(lines + [_line(t) for t in new])


def _line(turn: workspace.NumberedTurn) -> str:
    return f"#{turn.no} {'людина' if turn.role == 'user' else 'фасилітатор'}: {turn.text}"
