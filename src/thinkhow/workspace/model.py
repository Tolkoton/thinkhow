"""The values of the person's space: topics, numbered turns, sessions, reply events (M1)."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from thinkhow.facilitation.types import Decision, ProblemMap

TopicId = str
CARD_ID = "pre-mortem"
SILENCE = timedelta(hours=24)


class TopicNotFound(Exception):
    """No such topic for this person: absent, malformed, or someone else's (one error, no existence leak)."""


class PendingAnswer(Exception):
    """The last turn of the open session is the person's and has no answer yet: retry first."""


class NothingToRetry(Exception):
    """There is no unanswered turn of the person in an open session."""


@dataclass(frozen=True)
class TopicRef:
    uid: str
    topic_id: TopicId


@dataclass(frozen=True)
class NumberedTurn:
    no: int
    role: Literal["user", "model"]
    text: str
    at: datetime


@dataclass(frozen=True)
class Session:
    no: int
    turns: list[NumberedTurn]
    closed_at: datetime | None


@dataclass(frozen=True)
class TopicSummary:
    ref: TopicRef
    title: str


@dataclass(frozen=True)
class ResearchView:
    """What the topic page shows of one research entry: the answer it belongs to, Google's suggestions."""

    turn: int
    suggestions_html: str | None


@dataclass(frozen=True)
class TopicView:
    ref: TopicRef
    title: str
    sessions: list[Session]
    problem_map: ProblemMap
    awaiting_answer: bool
    routing: tuple[Decision, ...] = ()
    research: tuple[ResearchView, ...] = ()


@dataclass(frozen=True)
class Saved:
    turn_no: int


@dataclass(frozen=True)
class Delta:
    text: str


@dataclass(frozen=True)
class Answered:
    turn_no: int


@dataclass(frozen=True)
class Failed:
    reason: str


ReplyEvent = Saved | Delta | Answered | Failed
