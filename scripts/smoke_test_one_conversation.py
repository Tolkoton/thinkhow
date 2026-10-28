"""Smoke of slice one-conversation (task 711): after a day of silence the facilitator and the analyzer see the
whole topic, not the session.

Run: `uv run python scripts/smoke_test_one_conversation.py`. A temporary local folder, a scripted facilitator
that records what it is given, the analyzer on the scripted model of local mode. Exits 1 on a failed check.
"""

import importlib
import sys
import tempfile
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
access = importlib.import_module("thinkhow.access")
types = importlib.import_module("thinkhow.facilitation.types")
storage_module = importlib.import_module("thinkhow.platform.storage")
llm_module = importlib.import_module("thinkhow.platform.llm")
analyze_module = importlib.import_module("thinkhow.learning.analyze")
local = importlib.import_module("thinkhow.learning.local")
ws = importlib.import_module("thinkhow.workspace")

T0 = datetime(2026, 10, 22, 16, 0, tzinfo=UTC)
PERSON = access.CurrentUser("person-1", "person@example.com", False)


class RecordingFacilitate:
    """Answers every turn with one question and keeps the history it was given."""

    def __init__(self) -> None:
        self.histories: list[list[tuple[str, str]]] = []

    def __call__(self, ctx: Any) -> Iterator[Any]:
        self.histories.append([(t.role, t.text) for t in ctx.history])
        reply = f"Питання до репліки {ctx.turn_no}?"
        yield types.ReplyDelta(reply)
        yield types.FacilitatorUpdate(
            reply=reply, current_phase_id="phase_1_time_travel", phase_exit_met=False, map_updates=[]
        )


def check(ok: bool, what: str) -> None:
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        sys.exit(1)


def lines(contents: Sequence[Any]) -> list[str]:
    return [line for turn in contents for line in turn.text.split("\n")]


def main() -> None:
    with tempfile.TemporaryDirectory() as root:
        storage = storage_module.LocalStorage(Path(root))
        facilitate = RecordingFacilitate()
        ws.ensure_profile(storage, PERSON)
        ref = ws.TopicRef(PERSON.id, ws.create_topic(storage, PERSON, "Відкрити кав'ярню", T0))
        list(ws.reply(storage, facilitate, PERSON, ref, "Хочу відкрити кав'ярню.", T0))
        llm = llm_module.ScriptedLlm(local.local_script)
        analyze_module.analyze(storage, llm, T0 + timedelta(hours=1))
        later = T0 + timedelta(hours=25)
        list(ws.reply(storage, facilitate, PERSON, ref, "Повернувся: оренду знайшов.", later))
        sessions = ws.topic_sessions(storage, ref, later)
        print("sessions:", [(s.no, [t.no for t in s.turns]) for s in sessions])
        check(len(sessions) == 2, "the turn after 25 h opened session 2")
        first = [("user", "Хочу відкрити кав'ярню."), ("model", "Питання до репліки 1?")]
        print("history of turn 3:", facilitate.histories[1])
        check(facilitate.histories[1] == first, "the facilitator got every turn of session 1 for turn 3")
        llm.calls.clear()
        analyze_module.analyze(storage, llm, later + timedelta(hours=1))
        got = lines(llm.calls[0][1]) if llm.calls else []
        print("analyzer input:", got)
        check(
            got
            == [
                analyze_module.CONTEXT,
                "#1 людина: Хочу відкрити кав'ярню.",
                "#2 фасилітатор: Питання до репліки 1?",
                analyze_module.NEW,
                "#3 людина: Повернувся: оренду знайшов.",
                "#4 фасилітатор: Питання до репліки 3?",
            ],
            "the analyzer got session 1 as context and only turns 3-4 as new",
        )
        enum = llm.calls[0][2].model_json_schema()["$defs"]["ObservationAnswerItem"]["properties"]["anchor"][
            "enum"
        ]
        check(enum == ["t3", "t4"], "the anchor may be only a new turn")
        print("OK: the facilitator and the analyzer see the whole topic across a day of silence")


if __name__ == "__main__":
    main()
