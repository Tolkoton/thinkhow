"""documents.json: the documents a person gave a topic — turn, name, extracted text (task 311; only here).

conversation.md keeps the turn `📎 <name>`; the model reads it as `document_turn(name, text)` of its entry.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from thinkhow.facilitation.types import document_turn
from thinkhow.platform.storage import Storage
from thinkhow.workspace._paths import JSON
from thinkhow.workspace.model import TopicRef

# Half of the conversation's reserve of the model window: knowledge/versions.py gives the knowledge all but
# 200 000 tokens (BUDGET_CHARS), 2 characters a token → 400 000 characters, half to the topic's documents.
# PROVISIONAL (AUTONOMOUS in .engine/overseer/escalations.md, 2026-11-03).
MAX_DOCUMENT_CHARS = 200_000
CLIP = "📎 "
SPACES = re.compile(r"\s+")


class DocumentEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    turn: int
    name: str
    text: str


class DocumentsFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entries: list[DocumentEntry]


@dataclass(frozen=True)
class NewDocument:
    """A file that passed the checks: its cleaned name, its text, and what the log line says of it."""

    name: str
    text: str
    format: str
    size: int


def clean_name(name: str) -> str:
    """The part after the last `/` or `\\`, every run of whitespace one space, trimmed; empty → `document`."""
    last = re.split(r"[/\\]", name)[-1]
    return SPACES.sub(" ", last).strip() or "document"


def turn_text(name: str) -> str:
    """The document's turn as conversation.md keeps it."""
    return CLIP + name


def read_documents(storage: Storage, ref: TopicRef) -> list[DocumentEntry]:
    """The topic's entries; none without documents.json (a parse error is not recovered, as research.json)."""
    data = storage.read("users", _path(ref))
    return [] if data is None else DocumentsFile.model_validate_json(data).entries


def append_document(storage: Storage, ref: TopicRef, entry: DocumentEntry) -> None:
    body = DocumentsFile(entries=[*read_documents(storage, ref), entry]).model_dump_json().encode("utf-8")
    storage.write("users", _path(ref), body, JSON)


def too_large(entries: Sequence[DocumentEntry], text: str) -> bool:
    """All entries count, matched by a turn or not (I4)."""
    return sum(len(e.text) for e in entries) + len(text) > MAX_DOCUMENT_CHARS


def model_text(entries: Sequence[DocumentEntry], no: int, role: str, text: str) -> str | None:
    """The frame of a user turn whose text is `📎 <X>` and whose number has an entry named X — the last such
    entry; None for every other turn, an orphan entry's number too (Q7b)."""
    if role != "user" or not text.startswith(CLIP):
        return None
    name = text[len(CLIP) :]
    found = [e for e in entries if e.turn == no and e.name == name]
    return document_turn(name, found[-1].text) if found else None


def _path(ref: TopicRef) -> str:
    return f"{ref.uid}/{ref.topic_id}/documents.json"
