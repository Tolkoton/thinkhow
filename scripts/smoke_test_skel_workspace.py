"""Manual smoke of thinkhow.workspace: two people and the owner in a temporary folder, a scripted facilitator.

Run: `uv run python scripts/smoke_test_skel_workspace.py`. The real bucket is the owner's deployment (PR-07).
"""

import importlib
import sys
import tempfile
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
access = importlib.import_module("thinkhow.access")
types = importlib.import_module("thinkhow.facilitation.types")
storage_module = importlib.import_module("thinkhow.platform.storage")
ws = importlib.import_module("thinkhow.workspace")

T0 = datetime(2026, 10, 22, 16, 0, tzinfo=UTC)
PERSON = access.CurrentUser("person-1", "person@example.com", False)
OTHER = access.CurrentUser("person-2", "other@example.com", False)
OWNER = access.CurrentUser("owner-1", "owner@example.com", True)


class ScriptedFacilitate:
    """Answers with two deltas and one map change; fails once when asked to."""

    def __init__(self) -> None:
        self.fail_next = False

    def __call__(self, ctx: Any) -> Iterator[Any]:
        if self.fail_next:
            self.fail_next = False
            yield types.ReplyDelta("Уявіть ")
            raise ConnectionError("the scripted model is down")
        reply = f"Уявіть провал. Що сталося першим (репліка {ctx.turn_no})?"
        yield types.ReplyDelta(reply[:10])
        yield types.ReplyDelta(reply[10:])
        change = types.MapUpdate(
            op="add", id=f"i{ctx.turn_no}", type="plan", text=ctx.text, turn=f"t{ctx.turn_no}"
        )
        yield types.FacilitatorUpdate(
            reply=reply, current_phase_id="phase_1_time_travel", phase_exit_met=False, map_updates=[change]
        )


def events(iterator: Iterator[Any]) -> list[Any]:
    got = list(iterator)
    print("  events:", [type(e).__name__ for e in got])
    return got


def main() -> None:
    with tempfile.TemporaryDirectory() as root:
        storage = storage_module.LocalStorage(Path(root))
        facilitate = ScriptedFacilitate()
        ws.ensure_profile(storage, PERSON)
        ref = ws.TopicRef(PERSON.id, ws.create_topic(storage, PERSON, "Відкрити кав'ярню", T0))
        events(ws.reply(storage, facilitate, PERSON, ref, "Хочу відкрити кав'ярню за три місяці.", T0))
        facilitate.fail_next = True
        failed = events(
            ws.reply(storage, facilitate, PERSON, ref, "Оренда — за три тижні.", T0 + timedelta(minutes=2))
        )
        assert isinstance(failed[-1], ws.Failed)
        assert isinstance(
            events(ws.retry(storage, facilitate, PERSON, ref, T0 + timedelta(minutes=3)))[-1], ws.Answered
        )
        later = T0 + timedelta(minutes=6)
        print("--- conversation.md ---")
        print(storage.read("users", f"{ref.uid}/{ref.topic_id}/conversation.md").decode())
        print("--- map.json ---")
        print(storage.read("users", f"{ref.uid}/{ref.topic_id}/map.json").decode())
        view = ws.open_topic(storage, PERSON, ref, later)
        numbers = [t.no for s in view.sessions for t in s.turns]
        assert numbers == [1, 2, 3, 4], numbers
        assert view.sessions[0].closed_at is None
        assert [i.id for i in view.problem_map.items] == ["i1", "i3"]
        try:
            ws.open_topic(storage, OTHER, ref, later)
        except ws.TopicNotFound:
            print("person 2 cannot open person 1's topic: TopicNotFound")
        else:
            raise AssertionError("person 2 opened a foreign topic")
        assert ws.open_topic(storage, OWNER, ref, later).title == "Відкрити кав'ярню"
        print("the owner opens it")
        assert list(ws.all_topics_for_learning(storage)) == [ref]
        sessions = ws.topic_sessions(storage, ref, later)
        assert [(s.no, len(s.turns)) for s in sessions] == [(1, 4)]
        print("OK: turns 1-4, session 1 open, map from the updates, G4 holds, one session for learning")


if __name__ == "__main__":
    main()
