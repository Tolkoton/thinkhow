"""The analyzer: one Gemini call per closed session → one observation anchored to a turn (F10, G6).

Reads people's topics through workspace only; writes only system/learning/observations/ (I2).
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, create_model

from thinkhow import workspace
from thinkhow.platform.llm import Llm, LlmUnavailable, Turn
from thinkhow.platform.log import log_event
from thinkhow.platform.storage import Storage

ANALYZER = """Ти — аналізатор ThinkHow. Ти читаєш одну закриту сесію, у якій фасилітатор вів людину за
моделлю мислення, щоб вона сама дійшла до ясності (без готових відповідей).
Напиши одне спостереження українською:
- finding — що в цій сесії спрацювало чи не спрацювало у веденні людини до ясності, коротко, своїми словами;
  не цитуй людину і не переказуй подробиць її життя понад потрібне для висновку;
- worked — чи спрацювало;
- cause — чия це «заслуга» чи «вина»: method (вибір моделі мислення), facilitation (ведення розмови) чи
  circumstances (обставини людини);
- anchor — одна репліка, де це видно найкраще, її номер з переліку («t<номер>»)."""
CAUSE = Literal["method", "facilitation", "circumstances"]


class Observation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    uid: str
    topic_id: str
    session_no: int
    turn: int
    link: str
    worked: bool
    finding: str
    cause: CAUSE
    closed_at: datetime
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
    """Flow: every topic → its closed sessions → skip the observed → one call each, one file each (Q1, Q3)."""
    if now.tzinfo is None:
        raise ValueError("now must carry a time zone")
    written = skipped = failed = 0
    for ref in workspace.all_topics_for_learning(storage):
        try:
            sessions = workspace.closed_sessions(storage, ref, now)
        except Exception as exc:
            log_event(
                "analyze_failed",
                severity="WARNING",
                uid=ref.uid,
                topic_id=ref.topic_id,
                error=type(exc).__name__,
            )
            failed += 1
            continue
        for session in sessions:
            outcome = _one(storage, llm, ref, session, now)
            written += outcome == "written"
            skipped += outcome == "skipped"
            failed += outcome == "failed"
    report = AnalyzeReport(written, skipped, failed)
    log_event("analyze_done", written=report.written, skipped=report.skipped, failed=report.failed)
    return report


def _one(
    storage: Storage, llm: Llm, ref: workspace.TopicRef, session: workspace.ClosedSession, now: datetime
) -> str:
    path = f"learning/observations/{ref.uid}/{ref.topic_id}/s{session.session_no}.json"
    if storage.read("system", path) is not None:
        return "skipped"
    schema = answer_schema([t.no for t in session.turns])
    try:
        answer = llm.generate_json(ANALYZER, [Turn("user", _session_text(session))], schema, None)
    except (ValidationError, LlmUnavailable) as exc:
        log_event(
            "analyze_failed",
            severity="WARNING",
            uid=ref.uid,
            topic_id=ref.topic_id,
            session_no=session.session_no,
            error=type(exc).__name__,
        )
        return "failed"
    turn = int(answer.model_dump()["anchor"][1:])
    observation = Observation(
        uid=ref.uid,
        topic_id=ref.topic_id,
        session_no=session.session_no,
        turn=turn,
        link=f"/topics/{ref.uid}/{ref.topic_id}#t{turn}",
        closed_at=session.closed_at,
        analyzed_at=now,
        **{k: v for k, v in answer.model_dump().items() if k in ("worked", "finding", "cause")},
    )
    storage.write("system", path, observation.model_dump_json().encode("utf-8"), "application/json")
    return "written"


def _session_text(session: workspace.ClosedSession) -> str:
    lines = [f"#{t.no} {'людина' if t.role == 'user' else 'фасилітатор'}: {t.text}" for t in session.turns]
    lines.append(f"[Сесія {session.session_no} закрита {session.closed_at.isoformat()}]")
    return "\n".join(lines)
