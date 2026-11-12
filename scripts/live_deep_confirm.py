"""Live check of tasks 747 and 754 (slices deep-research-confirm-first, deep-change-question): deep research
only after the person's consent; after a change the proposal shows the research question rewritten with it.

Three new topics through the product's `workspace.reply` on the real model (Vertex `eu`, the app's default
model, the search instance), each opened by the same request to research deep:
  (а) the proposal → «Так, запускай.» → the report searched by exactly the shown sub-questions;
  (б) the proposal → a change → a new proposal whose research question is rewritten without the removed rent;
  (в) the proposal → «Ні, не треба.» → the conversation goes on without research.
A recorder around the model writes the prompt of every `search_text` and the schema of every `generate_json`.
The facts of the contract's Exit criterion 2 are asserted by code (exit 1 on any breach); whether the first
answer came «за секунди» and says that the system's opinion can be asked is read by a person from the output.
Only the router path runs live; the card path is covered by the tests.

Run: `PYTHONPATH=src uv run python scripts/live_deep_confirm.py`; the output goes to
.engine/artifacts/754/live-deep-confirm.txt (and to the screen); the 747 output stays as that slice's
evidence.
"""

import json
import sys
import tempfile
import threading
import time
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from thinkhow.access import CurrentUser
from thinkhow.facilitation import respond
from thinkhow.knowledge import current, seed
from thinkhow.platform import llm as model
from thinkhow.platform.config import Settings
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import Answered, Delta, TopicRef, create_topic, reply

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".engine" / "artifacts" / "754" / "live-deep-confirm.txt"
USER = CurrentUser(id="live-person", email="live@example.com", is_owner=False)
OPENER = (
    "Я хочу відкрити невелику кав'ярню у Львові. Досліди, будь ласка, глибоко ринок: скільки там кав'ярень, "
    "які середні чеки і скільки коштує оренда в центрі."
)
YES = "Так, запускай."
CHANGE = "Не треба про оренду, додай, які кав'ярні там найпопулярніші."
NO = "Ні, не треба."


class Recorder:
    """The real model, with every `search_text` prompt and every `generate_json` schema written down."""

    def __init__(self, llm: model.Llm) -> None:
        self.llm = llm
        self.lock = threading.Lock()
        self.calls: list[tuple[str, str]] = []

    def mark(self) -> int:
        with self.lock:
            return len(self.calls)

    def since(self, at: int) -> list[tuple[str, str]]:
        with self.lock:
            return self.calls[at:]

    def _add(self, kind: str, what: str) -> None:
        with self.lock:
            self.calls.append((kind, what))

    def generate_json(
        self, system: str, contents: Sequence[model.Turn], schema: type[Any], rev: model.KnowledgeRev | None
    ) -> Any:
        self._add("json", schema.__name__)
        return self.llm.generate_json(system, contents, schema, rev)

    def stream_json(
        self,
        system: str,
        contents: Sequence[model.Turn],
        schema: type[BaseModel],
        rev: model.KnowledgeRev | None,
    ) -> Iterator[model.ReplyDelta | model.Done]:
        self._add("stream", schema.__name__)
        return self.llm.stream_json(system, contents, schema, rev)

    def search_text(
        self, system: str, prompt: str, rev: model.KnowledgeRev | None
    ) -> tuple[str, model.Found | None]:
        self._add("search", prompt)
        return self.llm.search_text(system, prompt, rev)


class Run:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.failed: list[str] = []

    def say(self, text: str) -> None:
        print(text, flush=True)
        self.lines.append(text)

    def check(self, ok: bool, what: str) -> None:
        self.say(f"  [{'OK' if ok else 'FAIL'}] {what}")
        if not ok:
            self.failed.append(what)


def turn(
    run: Run, storage: LocalStorage, rec: Recorder, knowledge: Any, ref: TopicRef, text: str, at: datetime
) -> tuple[str, list[tuple[str, str]], float]:
    """One turn of the person: the answer's text, the model calls it made, its seconds."""
    mark, started = rec.mark(), time.monotonic()
    facilitate = partial(respond, knowledge=knowledge, llm=rec)
    events = list(reply(storage, facilitate, USER, ref, text, at))
    seconds = time.monotonic() - started
    shown = "".join(e.text for e in events if isinstance(e, Delta))
    run.say(f"\n> людина: {text}\n< ThinkHow ({seconds:.1f} с):\n{shown}")
    run.check(isinstance(events[-1], Answered), f"відповідь записана ({type(events[-1]).__name__})")
    return shown, rec.since(mark), seconds


def pending(storage: LocalStorage, ref: TopicRef) -> dict[str, Any] | None:
    data = storage.read("users", f"{ref.uid}/{ref.topic_id}/deep_pending.json")
    return None if data is None else json.loads(data)


def research(storage: LocalStorage, ref: TopicRef) -> list[dict[str, Any]]:
    data = storage.read("users", f"{ref.uid}/{ref.topic_id}/research.json")
    return [] if data is None else list(json.loads(data)["entries"])


def kinds(calls: list[tuple[str, str]], kind: str, what: str | None = None) -> list[str]:
    return [w for k, w in calls if k == kind and (what is None or w == what)]


def propose(
    run: Run, storage: LocalStorage, rec: Recorder, knowledge: Any, name: str
) -> tuple[TopicRef, dict[str, Any]]:
    """A new topic, the opener: the first answer is a proposal and searches nothing."""
    run.say(f"\n=== Тема ({name}) ===")
    ref = TopicRef(USER.id, create_topic(storage, USER, f"Кав'ярня у Львові ({name})", datetime.now(UTC)))
    shown, calls, seconds = turn(run, storage, rec, knowledge, ref, OPENER, datetime.now(UTC))
    waiting = pending(storage, ref)
    run.say(f"  час першої відповіді: {seconds:.1f} с (судить людина: «за секунди»)")
    run.check(waiting is not None, "deep_pending.json є після першої відповіді")
    run.check(kinds(calls, "search") == [], "у першій відповіді нуль search_text")
    run.check(research(storage, ref) == [], "research.json порожній")
    lines = waiting["pending"]["questions"] if waiting else []
    run.check(
        bool(lines) and all(f"- {q}" in shown for q in lines), "у відповіді — рядки підпитань пропозиції"
    )
    return ref, waiting or {}


def case_yes(run: Run, storage: LocalStorage, rec: Recorder, knowledge: Any) -> None:
    ref, waiting = propose(run, storage, rec, knowledge, "а: так")
    shown, calls, _ = turn(run, storage, rec, knowledge, ref, YES, datetime.now(UTC) + timedelta(seconds=30))
    asked = sorted(kinds(calls, "search"))
    run.check(
        asked == sorted(waiting["pending"]["questions"]),
        f"запити search_text — рівно рядки пропозиції: {asked}",
    )
    run.check(kinds(calls, "json", "DeepPlan") == [], "у другій відповіді нуль DeepPlan")
    run.check("Джерела: " in shown, "у відповіді звіт із рядком джерел")
    deep = [e for e in research(storage, ref) if e["depth"] == "deep"]
    run.check(
        len(deep) == 1 and deep[0]["question"] == waiting["pending"]["question"], "запис deep у research.json"
    )
    run.check(pending(storage, ref) is None, "deep_pending.json після згоди немає")


def case_change(run: Run, storage: LocalStorage, rec: Recorder, knowledge: Any) -> None:
    ref, waiting = propose(run, storage, rec, knowledge, "б: правка")
    later = datetime.now(UTC) + timedelta(seconds=30)
    shown, calls, _ = turn(run, storage, rec, knowledge, ref, CHANGE, later)
    after = pending(storage, ref)
    run.check(kinds(calls, "search") == [], "у відповіді на правку нуль search_text")
    run.check(
        after is not None and after["turn"] == waiting["turn"] + 2,
        "deep_pending.json оновлено (нова відповідь)",
    )
    old, new = (
        set(waiting["pending"]["questions"]),
        set((after or {}).get("pending", {}).get("questions", [])),
    )
    run.check(bool(new) and new != old, "множина підпитань інша, ніж до правки")
    question = (after or {}).get("pending", {}).get("question", "")
    run.check(question != waiting["pending"]["question"], f"питання інше, ніж до правки: {question}")
    run.check(question in shown.split("\n"), "рядок питання у відповіді — питання з deep_pending.json")
    run.check("оренд" not in question.lower(), "у питанні після правки немає «оренд»")


def case_no(run: Run, storage: LocalStorage, rec: Recorder, knowledge: Any) -> None:
    ref, _ = propose(run, storage, rec, knowledge, "в: ні")
    _, calls, _ = turn(run, storage, rec, knowledge, ref, NO, datetime.now(UTC) + timedelta(seconds=30))
    run.check(kinds(calls, "search") == [], "у відповіді на «ні» нуль search_text")
    run.check(kinds(calls, "json", "DeepPlan") == [], "у відповіді на «ні» нуль DeepPlan")
    run.check(pending(storage, ref) is None, "deep_pending.json після «ні» немає")


def main() -> None:
    settings = Settings(local=False, users_bucket="-", system_bucket="-", owner_email="-")
    rec = Recorder(model.make_llm(settings, lambda *_: "", search=True))
    storage = LocalStorage(Path(tempfile.mkdtemp(prefix="thinkhow-754-")))
    seed(storage, ROOT / "cards")
    knowledge = current(storage)
    run = Run()
    started = datetime.now(UTC).isoformat(timespec="seconds")
    run.say(f"Жива перевірка 747/754, {started}, модель {settings.model}")
    for case in (case_yes, case_change, case_no):
        case(run, storage, rec, knowledge)
    run.say(f"\nПідсумок: {'усе OK' if not run.failed else 'FAIL: ' + '; '.join(run.failed)}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(run.lines) + "\n", encoding="utf-8")
    sys.exit(1 if run.failed else 0)


if __name__ == "__main__":
    main()
