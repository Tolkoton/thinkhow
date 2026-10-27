"""Observations of the analyzer as files and their one reader (learning-loop S2, F10).

A file `learning/observations/<uid>/<topic>/t<a>-t<b>.json` holds a set of observations; the reader also reads
the old shapes (one observation per range file of continuous-analysis, `s<n>.json` of skel-learning). Does NOT
write anything and does NOT read people's topics.
"""

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from thinkhow.platform.log import log_event
from thinkhow.platform.storage import Storage

Kind = Literal["progress", "stuck", "method_fit", "step"]
Cause = Literal["router", "method", "facilitation", "circumstances"]


class Observation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    turn: int
    link: str
    kind: Kind
    worked: bool
    finding: str
    cause: Cause
    card_id: str | None
    analyzed_at: datetime


class ObservationSet(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    uid: str
    topic_id: str
    first_turn: int
    last_turn: int
    analyzed_at: datetime
    observations: list[Observation]


PREFIX = "learning/observations/"
SET_FILE = re.compile(r"^learning/observations/([^/]+)/([^/]+)/t(\d+)-t(\d+)\.json$")
OLD_SESSION = re.compile(r"^learning/observations/([^/]+)/([^/]+)/s(\d+)\.json$")


class _OldRange(BaseModel):
    """One observation per range file (continuous-analysis)."""

    uid: str
    topic_id: str
    first_turn: int
    last_turn: int
    turn: int
    link: str
    worked: bool
    finding: str
    cause: Cause
    analyzed_at: datetime


class _OldSession(BaseModel):
    """One observation per session file (skel-learning)."""

    uid: str
    topic_id: str
    session_no: int
    turn: int
    link: str
    worked: bool
    finding: str
    cause: Cause
    analyzed_at: datetime


def read_all(storage: Storage) -> list[Observation]:
    """Flow: every observation file in order (uid, topic, old sessions by n, then sets by first turn) → its
    observations; a file of none of the three shapes is skipped with a log line."""
    found: list[Observation] = []
    for path in sorted(storage.list("system", PREFIX), key=_order):
        found += _read(storage, path)
    return found


def _order(path: str) -> tuple[str, str, int, int]:
    if m := SET_FILE.match(path):
        return m.group(1), m.group(2), 1, int(m.group(3))
    if m := OLD_SESSION.match(path):
        return m.group(1), m.group(2), 0, int(m.group(3))
    return "", "", -1, 0


def _read(storage: Storage, path: str) -> list[Observation]:
    data = storage.read("system", path) or b""
    for parse in (_as_set, _as_old_range, _as_old_session):
        try:
            return parse(path, data)
        except (ValidationError, ValueError):
            continue
    log_event("observation_unreadable", severity="WARNING", path=path)
    return []


def _as_set(path: str, data: bytes) -> list[Observation]:
    if not SET_FILE.match(path):
        raise ValueError("not a set file")
    return list(ObservationSet.model_validate_json(data).observations)


def _as_old_range(path: str, data: bytes) -> list[Observation]:
    if not (m := SET_FILE.match(path)):
        raise ValueError("not a range file")
    old = _OldRange.model_validate_json(data)
    return [_one(old, f"{m.group(1)}/{m.group(2)}/t{m.group(3)}-t{m.group(4)}/1")]


def _as_old_session(path: str, data: bytes) -> list[Observation]:
    if not (m := OLD_SESSION.match(path)):
        raise ValueError("not a session file")
    old = _OldSession.model_validate_json(data)
    return [_one(old, f"{m.group(1)}/{m.group(2)}/s{m.group(3)}/1")]


def _one(old: _OldRange | _OldSession, oid: str) -> Observation:
    return Observation(
        id=oid,
        turn=old.turn,
        link=old.link,
        kind="progress" if old.worked else "stuck",
        worked=old.worked,
        finding=old.finding,
        cause=old.cause,
        card_id=None,
        analyzed_at=old.analyzed_at,
    )
