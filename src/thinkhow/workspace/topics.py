"""Topics of a person in the users bucket: the only writer of users/ (M3 A3.3).

Paths are built here only, from the server's ids. Read rule: own or the owner; write rule: own (Q2).
"""

import json
import re
import secrets
from collections.abc import Iterator
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from thinkhow.access import CurrentUser
from thinkhow.facilitation.types import (
    Decision,
    Facilitate,
    FacilitationContext,
    FacilitatorUpdate,
    MapItem,
    MapUpdate,
    ProblemMap,
    ResearchEvent,
    RoutingEvent,
    current_card,
)
from thinkhow.facilitation.types import Turn as FacilitationTurn
from thinkhow.platform.storage import Storage
from thinkhow.workspace import conversation as conv_file
from thinkhow.workspace._paths import JSON, UID, _uid
from thinkhow.workspace.model import (
    CARD_ID,
    SILENCE,
    Answered,
    Delta,
    Failed,
    NothingToRetry,
    NumberedTurn,
    PendingAnswer,
    ReplyEvent,
    ResearchView,
    Saved,
    Session,
    TopicId,
    TopicNotFound,
    TopicRef,
    TopicSummary,
    TopicView,
)
from thinkhow.workspace.profile import NoLanguage, language


class RoutingFile(BaseModel):
    """routing.json: the router's decisions of a topic, in order (written only here — M2 «вибір методу»)."""

    model_config = ConfigDict(extra="forbid")
    decisions: list[Decision]


class ResearchSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    url: str


class ResearchEntry(BaseModel):
    """One answer's research in research.json; `turn` is the number of the model's answer."""

    model_config = ConfigDict(extra="forbid")
    turn: int
    depth: Literal["quick", "deep"]
    queries: list[str]
    sources: list[ResearchSource]
    suggestions_html: str | None
    question: str | None
    report: str | None


class ResearchFile(BaseModel):
    """research.json: the searches behind a topic's answers, in order (written only here — A7)."""

    model_config = ConfigDict(extra="forbid")
    entries: list[ResearchEntry]


TOPIC_ID = re.compile(r"^t-[0-9a-f]{12}$")
CONVERSATION = re.compile(r"^([A-Za-z0-9_-]{1,128})/(t-[0-9a-f]{12})/conversation\.md$")
MARKDOWN = "text/markdown; charset=utf-8"


def ensure_profile(storage: Storage, user: CurrentUser) -> None:
    data = json.dumps({"email": user.email}, ensure_ascii=False).encode()
    storage.create_if_absent("users", f"{_uid(user.id)}/profile.json", data, JSON)


def create_topic(storage: Storage, user: CurrentUser, title: str, now: datetime) -> TopicId:
    _check_now(now)
    clean = conv_file.normalize_title(title)
    if not clean:
        raise ValueError("a topic needs a title")
    ref = TopicRef(_uid(user.id), "t-" + secrets.token_hex(6))
    _write_conversation(storage, ref, conv_file.Conversation(clean, [conv_file.SessionDoc(no=1)]))
    _write_map(storage, ref, ProblemMap())
    return ref.topic_id


def list_topics(storage: Storage, user: CurrentUser) -> list[TopicSummary]:
    refs = [ref for ref in _refs(storage, f"{_uid(user.id)}/") if ref.uid == user.id]
    return [TopicSummary(ref, _read_conversation(storage, ref).title) for ref in refs]


def all_topics_for_learning(storage: Storage) -> Iterator[TopicRef]:
    """The one reader of all people's topics (M3 A3.3): web gives it to the owner only; learning reads it."""
    yield from _refs(storage, "")


def open_topic(storage: Storage, user: CurrentUser, ref: TopicRef, now: datetime) -> TopicView:
    _check_now(now)
    _can_read(user, ref)
    conv = _read_conversation(storage, ref)
    sessions = [_session(s, now) for s in conv.sessions]
    problem_map, routing = _read_map(storage, ref), _read_routing(storage, ref)
    research = tuple(ResearchView(e.turn, e.suggestions_html) for e in _read_research(storage, ref))
    return TopicView(ref, conv.title, sessions, problem_map, _awaiting(conv, now), routing, research)


def reply(
    storage: Storage,
    facilitate: Facilitate,
    user: CurrentUser,
    ref: TopicRef,
    text: str,
    now: datetime,
    spoken: bool = False,
) -> Iterator[ReplyEvent]:
    """Checks now (Q4, eager); the returned iterator saves the turn, then streams and writes the answer."""
    _check_now(now)
    _can_write(user, ref)
    clean = conv_file.normalize(text)
    if not clean:
        raise ValueError("an empty turn is not saved")
    conv = _read_conversation(storage, ref)
    if _awaiting(conv, now):
        raise PendingAnswer("the last turn has no answer yet: retry it first")
    return _reply_flow(storage, facilitate, ref, conv, clean, now, _language_of(storage, user), spoken)


def retry(
    storage: Storage,
    facilitate: Facilitate,
    user: CurrentUser,
    ref: TopicRef,
    now: datetime,
    spoken: bool = False,
) -> Iterator[ReplyEvent]:
    _check_now(now)
    _can_write(user, ref)
    conv = _read_conversation(storage, ref)
    if not _awaiting(conv, now):
        raise NothingToRetry("no unanswered turn in an open session")
    last = conv.sessions[-1].turns[-1]
    lang = _language_of(storage, user)
    return _answer(storage, facilitate, ref, conv, last.no, last.text, now, lang, spoken)


def delete_topic(storage: Storage, user: CurrentUser, ref: TopicRef) -> None:
    """Own topics only, the owner's too (task 204); conversation.md goes last, so a broken delete leaves
    the topic listed and the person can delete it again."""
    _can_write(user, ref)
    conversation = f"{ref.uid}/{ref.topic_id}/conversation.md"
    if storage.read("users", conversation) is None:
        raise TopicNotFound(ref.topic_id)
    for path in storage.list("users", f"{ref.uid}/{ref.topic_id}/"):
        if path != conversation:
            storage.delete("users", path)
    storage.delete("users", conversation)


def _language_of(storage: Storage, user: CurrentUser) -> str | None:
    """The person's language as the model reads it, «name (code)», or None before the first choice (F13)."""
    try:
        chosen = language(storage, user)
    except NoLanguage:
        return None
    return f"{chosen.name} ({chosen.code})"


def topic_sessions(storage: Storage, ref: TopicRef, now: datetime) -> list[Session]:
    """Read only, no access rule: for learning, with refs from all_topics_for_learning."""
    _check_now(now)
    _check_ref(ref)
    return [_session(s, now) for s in _read_conversation(storage, ref).sessions]


def topic_routing(storage: Storage, ref: TopicRef) -> tuple[Decision, ...]:
    """Read only, no access rule: the router's decisions of the topic for learning (refs from
    all_topics_for_learning); none without routing.json."""
    _check_ref(ref)
    return _read_routing(storage, ref)


def _reply_flow(
    storage: Storage,
    facilitate: Facilitate,
    ref: TopicRef,
    conv: conv_file.Conversation,
    text: str,
    now: datetime,
    lang: str | None,
    spoken: bool = False,
) -> Iterator[ReplyEvent]:
    """Flow (M2): the person's turn into conversation.md → Saved → the answer (I4)."""
    if _closed_at(conv.sessions[-1], now) is not None:
        conv.sessions.append(conv_file.SessionDoc(no=conv.sessions[-1].no + 1))
    turn_no = conv.last_no() + 1
    conv.sessions[-1].turns.append(conv_file.Turn(turn_no, "user", conv_file.second(now), text))
    _write_conversation(storage, ref, conv)
    yield Saved(turn_no)
    yield from _answer(storage, facilitate, ref, conv, turn_no, text, now, lang, spoken)


def _answer(
    storage: Storage,
    facilitate: Facilitate,
    ref: TopicRef,
    conv: conv_file.Conversation,
    turn_no: int,
    text: str,
    now: datetime,
    lang: str | None,
    spoken: bool = False,
) -> Iterator[ReplyEvent]:
    """Flow: facilitate → deltas → answer into conversation.md → map, routing, research.json → Answered."""
    session = conv.sessions[-1]
    history = [FacilitationTurn(t.role, t.text) for t in session.turns if t.no < turn_no]
    problem_map, routing = _read_map(storage, ref), _read_routing(storage, ref)
    card_id = current_card(routing) or CARD_ID
    ctx = FacilitationContext(card_id, history, problem_map, turn_no, text, lang, routing, spoken)
    update: FacilitatorUpdate | None = None
    decisions: list[Decision] = []
    research: list[ResearchEvent] = []
    try:
        for item in facilitate(ctx):
            if isinstance(item, FacilitatorUpdate):
                update = item
                break
            if isinstance(item, RoutingEvent):
                decisions.append(item.decision)
                continue
            if isinstance(item, ResearchEvent):
                research.append(item)
                continue
            yield Delta(item.text)
    except Exception as exc:
        yield Failed(type(exc).__name__)
        return
    if update is None:
        yield Failed("NoUpdate")
        return
    answer = conv_file.normalize(update.reply)
    if not answer:
        yield Failed("EmptyReply")
        return
    session.turns.append(conv_file.Turn(turn_no + 1, "model", conv_file.second(now), answer))
    _write_conversation(storage, ref, conv)
    _write_map(storage, ref, apply_updates(problem_map, update, turn_no + 1))
    if decisions:
        _write_routing(storage, ref, (*routing, *decisions))
    if research:
        _append_research(storage, ref, [_entry(event, turn_no + 1) for event in research])
    yield Answered(turn_no + 1)


def apply_updates(problem_map: ProblemMap, update: FacilitatorUpdate, last_turn: int) -> ProblemMap:
    items = list(problem_map.items)
    for change in update.map_updates:
        items = _apply_one(items, change)
    return ProblemMap(items=items, phase_id=update.current_phase_id, last_turn=last_turn)


def _apply_one(items: list[MapItem], change: MapUpdate) -> list[MapItem]:
    at = next((i for i, item in enumerate(items) if item.id == change.id), None)
    if change.op == "remove":
        return items if at is None else items[:at] + items[at + 1 :]
    new = MapItem(id=change.id, type=change.type, text=change.text, turn=change.turn)
    if at is not None:
        return items[:at] + [new] + items[at + 1 :]
    return items + [new] if change.op == "add" else items


def _session(doc: conv_file.SessionDoc, now: datetime) -> Session:
    turns = [NumberedTurn(t.no, t.role, t.text, t.at) for t in doc.turns]
    return Session(doc.no, turns, _closed_at(doc, now))


def _closed_at(doc: conv_file.SessionDoc, now: datetime) -> datetime | None:
    """Closed by the marker of an old file (task 202: only read), or by 24 h of silence; never if empty."""
    if doc.closed_at is not None:
        return doc.closed_at
    if doc.turns and now >= doc.turns[-1].at + SILENCE:
        return doc.turns[-1].at + SILENCE
    return None


def _awaiting(conv: conv_file.Conversation, now: datetime) -> bool:
    """The person's turn is the last one and its session is still open on `now` (Q7)."""
    last = conv.sessions[-1]
    return bool(last.turns) and last.turns[-1].role == "user" and _closed_at(last, now) is None


def _refs(storage: Storage, prefix: str) -> Iterator[TopicRef]:
    for path in storage.list("users", prefix):
        if m := CONVERSATION.match(path):
            yield TopicRef(m.group(1), m.group(2))


def _can_read(user: CurrentUser, ref: TopicRef) -> None:
    _check_ref(ref)
    if ref.uid != user.id and not user.is_owner:
        raise TopicNotFound(ref.topic_id)


def _can_write(user: CurrentUser, ref: TopicRef) -> None:
    _check_ref(ref)
    if ref.uid != user.id:
        raise TopicNotFound(ref.topic_id)


def _check_ref(ref: TopicRef) -> None:
    if not UID.match(ref.uid) or not TOPIC_ID.match(ref.topic_id):
        raise TopicNotFound(ref.topic_id)


def _check_now(now: datetime) -> None:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must carry a time zone")


def _read_conversation(storage: Storage, ref: TopicRef) -> conv_file.Conversation:
    data = storage.read("users", f"{ref.uid}/{ref.topic_id}/conversation.md")
    if data is None:
        raise TopicNotFound(ref.topic_id)
    return conv_file.parse(data.decode("utf-8"))


def _write_conversation(storage: Storage, ref: TopicRef, conv: conv_file.Conversation) -> None:
    path = f"{ref.uid}/{ref.topic_id}/conversation.md"
    storage.write("users", path, conv_file.render(conv).encode("utf-8"), MARKDOWN)


def _read_map(storage: Storage, ref: TopicRef) -> ProblemMap:
    data = storage.read("users", f"{ref.uid}/{ref.topic_id}/map.json")
    return ProblemMap() if data is None else ProblemMap.model_validate_json(data)


def _read_routing(storage: Storage, ref: TopicRef) -> tuple[Decision, ...]:
    """The router's decisions of the topic; none without routing.json (a parse error is not recovered)."""
    data = storage.read("users", f"{ref.uid}/{ref.topic_id}/routing.json")
    return () if data is None else tuple(RoutingFile.model_validate_json(data).decisions)


def _write_routing(storage: Storage, ref: TopicRef, routing: tuple[Decision, ...]) -> None:
    path = f"{ref.uid}/{ref.topic_id}/routing.json"
    storage.write("users", path, RoutingFile(decisions=list(routing)).model_dump_json().encode("utf-8"), JSON)


def _entry(event: ResearchEvent, turn: int) -> ResearchEntry:
    sources = [ResearchSource(title=s.title, url=s.url) for s in event.sources]
    return ResearchEntry(
        turn=turn,
        depth=event.depth,
        queries=list(event.queries),
        sources=sources,
        suggestions_html=event.suggestions_html,
        question=event.question,
        report=event.report,
    )


def _read_research(storage: Storage, ref: TopicRef) -> list[ResearchEntry]:
    """The research entries of the topic; none without research.json (a parse error is not recovered)."""
    data = storage.read("users", f"{ref.uid}/{ref.topic_id}/research.json")
    return [] if data is None else ResearchFile.model_validate_json(data).entries


def _append_research(storage: Storage, ref: TopicRef, entries: list[ResearchEntry]) -> None:
    """research.json keeps every earlier entry; the new ones go after them (I5)."""
    path = f"{ref.uid}/{ref.topic_id}/research.json"
    old = _read_research(storage, ref)
    body = ResearchFile(entries=[*old, *entries]).model_dump_json().encode("utf-8")
    storage.write("users", path, body, JSON)


def _write_map(storage: Storage, ref: TopicRef, problem_map: ProblemMap) -> None:
    path = f"{ref.uid}/{ref.topic_id}/map.json"
    storage.write("users", path, problem_map.model_dump_json().encode("utf-8"), JSON)
