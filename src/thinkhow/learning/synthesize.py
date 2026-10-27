"""The synthesizer: every day, the observations no change and no run has taken yet → one Gemini call →
changes of the notes to the methods, applied by the Knowledge's version check (learning-loop S3, F12).

The synthesizer makes the change itself (the owner's «1Б», G3); the owner sees it in /learning and rolls it
back. Writes only system/learning/synthesis/ (the run record, last); the Knowledge only through
`apply_memory`. Does NOT touch cards, read people's topics or roll anything back.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, create_model

from thinkhow import knowledge
from thinkhow.knowledge import ChangeView, CurrentKnowledge, MemoryChange, MemoryRecord
from thinkhow.learning.observations import Observation, read_all
from thinkhow.platform.llm import Llm, LlmUnavailable, Turn
from thinkhow.platform.log import log_event
from thinkhow.platform.storage import Storage

RUNS = "learning/synthesis/"
JSON = "application/json"
ID_PATTERN = r"^[A-Za-z0-9-]{1,64}$"
AUDIENCE: Any = Literal["router", "facilitator"]
Outcome = Literal["applied", "nothing_new", "no_change", "rejected", "failed"]
SYNTHESIZER = """Ти — синтезатор ThinkHow: ти вчиш систему з досвіду всіх людей, що думали з нею. ThinkHow
веде людину методом мислення, щоб вона сама дійшла до ясності, без готових відповідей.
Ти змінюєш лише нотатки до методів:
- router — у яких ситуаціях пропонувати метод, з яким сусіднім методом його плутають і як їх розрізнити;
- facilitator — коли метод допомагає, де застрягають, як застосувати в типовій ситуації, як вивести людину із
  застрягання питанням, не даючи їй готової відповіді.
Фази, мета й хід методу — стандарт із першоджерела: їх ти не змінюєш і не переписуєш у нотатках.
Правила:
- узагальнюй з кількох випадків; без подробиць людей (імен, міст, сум, дат, подій їхнього життя) і без цитат;
- кожна зміна цитує спостереження (o1, o2, …), з яких вона зроблена;
- краще оновити наявну нотатку (той самий id), ніж додати схожу; нова нотатка — новий id з латиниці, цифр
  і дефісів;
- прибирай нотатку (remove), лише якщо спостереження показують, що вона шкодить;
- відкочене власником не пропонуй знову;
- якщо нові спостереження нічого нового не кажуть — порожні upsert і remove.
what — одним реченням, що змінено; why — чому, з посиланням на спостереження."""


class SynthesisRun(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    at: datetime
    considered: list[str]
    outcome: Outcome
    rev: int | None
    rejected: str | None


@dataclass(frozen=True)
class SynthesisReport:
    rev: int | None
    considered: int
    outcome: Outcome


def synthesize(
    storage: Storage, llm: Llm, now: datetime, vet: knowledge.Vet, measure: knowledge.Measure
) -> SynthesisReport:
    """Flow: what is new → one call → the change through the version check → the run record last."""
    if now.tzinfo is None:
        raise ValueError("now must carry a time zone")
    current, feed = knowledge.current(storage), knowledge.changes(storage)
    new = _new(read_all(storage), feed, runs(storage))
    if not new:
        return _done(SynthesisReport(None, 0, "nothing_new"))
    aliases = {f"o{k}": o for k, o in enumerate(new, start=1)}
    try:
        answer = llm.generate_json(
            SYNTHESIZER,
            [Turn("user", _text(current, feed, aliases))],
            answer_schema(current, aliases),
            current.rev_pair(),
        ).model_dump()
        change = _change(answer, current, aliases)
        outcome, rev, rejected = _apply(storage, change, vet, measure)
    except (ValidationError, LlmUnavailable) as exc:
        log_event("synthesize_failed", severity="WARNING", error=type(exc).__name__, considered=len(new))
        return SynthesisReport(None, len(new), "failed")
    _write_run(
        storage,
        SynthesisRun(at=now, considered=[o.id for o in new], outcome=outcome, rev=rev, rejected=rejected),
    )
    return _done(SynthesisReport(rev, len(new), outcome))


def runs(storage: Storage) -> list[SynthesisRun]:
    """Every run record, by name."""
    paths = sorted(p for p in storage.list("system", RUNS) if p.endswith(".json"))
    return [SynthesisRun.model_validate_json(storage.read("system", p) or b"") for p in paths]


def _new(
    observations: Sequence[Observation], feed: Sequence[ChangeView], done: Sequence[SynthesisRun]
) -> list[Observation]:
    consumed = {oid for view in feed for oid in view.observations} | {
        oid for run in done for oid in run.considered
    }
    return [o for o in observations if o.id not in consumed]


def answer_schema(current: CurrentKnowledge, aliases: dict[str, Observation]) -> type[BaseModel]:
    """upsert and remove; the cards and the cited observations as an `enum`, the removed id a plain string."""
    cards: Any = list.__class_getitem__(Literal[tuple(sorted(current.cards))])
    cited: Any = list.__class_getitem__(Literal[tuple(aliases)])
    upsert: Any = create_model(
        "SynthesisUpsert",
        id=(str, Field(pattern=ID_PATTERN)),
        audience=(AUDIENCE, ...),
        cards=(cards, Field(min_length=1)),
        title=(str, Field(min_length=1)),
        noticed=(str, Field(min_length=1)),
        do=(str, Field(min_length=1)),
        observations=(cited, Field(min_length=1)),
    )
    remove: Any = create_model(
        "SynthesisRemove",
        id=(str, Field(pattern=ID_PATTERN)),
        observations=(cited, Field(min_length=1)),
    )
    upserts: Any = list.__class_getitem__(upsert)
    removes: Any = list.__class_getitem__(remove)
    return create_model(
        "SynthesisAnswer",
        what=(str, Field(min_length=1)),
        why=(str, Field(min_length=1)),
        upsert=(upserts, ...),
        remove=(removes, ...),
    )


def _text(current: CurrentKnowledge, feed: Sequence[ChangeView], aliases: dict[str, Observation]) -> str:
    cards = [f"- {cid}: {card.method} — {card.title}" for cid, card in sorted(current.cards.items())]
    notes = [_note(r) for r in current.memory] or ["(поки немає)"]
    rolled = [_rolled(v) for v in feed if v.rolled_back is not None and v.rollback_changed]
    seen = [
        f"- {alias}: картка {o.card_id or '—'}; {o.kind}; причина {o.cause}; "
        f"{'спрацювало' if o.worked else 'не спрацювало'} — {o.finding}"
        for alias, o in aliases.items()
    ]
    parts = [
        "# Методи (картки)",
        *cards,
        "# Чинні нотатки",
        *notes,
        *(["# Відкочено власником — не пропонуй знову", *rolled] if rolled else []),
        "# Нові спостереження",
        *seen,
    ]
    return "\n".join(parts)


def _note(r: MemoryRecord) -> str:
    return f"- {r.id} [{r.audience}; {', '.join(r.cards)}] {r.title}: {r.noticed} → {r.do}"


def _rolled(view: ChangeView) -> str:
    upserted = "; ".join(_note(r)[2:] for r in view.upserted)
    removed = ", ".join(view.removed)
    return (
        f"- ревізія {view.rev}: {view.what}"
        + (f"; нотатки: {upserted}" if upserted else "")
        + (f"; прибрано: {removed}" if removed else "")
    )


def _change(
    answer: dict[str, Any], current: CurrentKnowledge, aliases: dict[str, Observation]
) -> MemoryChange:
    now = {r.id: r for r in current.memory}
    cited: list[str] = []
    upsert = []
    for item in answer["upsert"]:
        ids = [aliases[a].id for a in item["observations"]]
        cited += ids
        old = now.get(item["id"])
        basis = (f"{old.basis}; " if old else "") + "спостереження: " + ", ".join(ids)
        upsert.append(
            MemoryRecord(
                id=item["id"],
                title=item["title"],
                cards=item["cards"],
                noticed=item["noticed"],
                do=item["do"],
                basis=basis,
                audience=item["audience"],
            )
        )
    for item in answer["remove"]:
        cited += [aliases[a].id for a in item["observations"]]
    return MemoryChange(
        what=answer["what"],
        why=answer["why"],
        by="synthesizer",
        upsert=upsert,
        remove=[item["id"] for item in answer["remove"]],
        observations=list(dict.fromkeys(cited)),
    )


def _apply(
    storage: Storage, change: MemoryChange, vet: knowledge.Vet, measure: knowledge.Measure
) -> tuple[Outcome, int | None, str | None]:
    if not change.upsert and not change.remove:
        return "no_change", None, None
    try:
        rev = knowledge.apply_memory(storage, change, vet, measure)
    except knowledge.VersionRejected as refused:
        return "rejected", None, refused.reason
    return ("applied", rev, None) if rev is not None else ("no_change", None, None)


def _write_run(storage: Storage, run: SynthesisRun) -> None:
    stem = f"{RUNS}{run.at.strftime('%Y%m%dT%H%M%SZ')}"
    data = run.model_dump_json().encode()
    for k in range(1, 100):
        if storage.create_if_absent("system", f"{stem}{'' if k == 1 else f'-{k}'}.json", data, JSON):
            return


def _done(report: SynthesisReport) -> SynthesisReport:
    log_event("synthesize_done", outcome=report.outcome, rev=report.rev, considered=report.considered)
    return report
