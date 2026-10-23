"""Catch-up contract tests of skel-workspace: the smoke script (slice tester).

Written from the contract (.engine/slices/skel-workspace.md, «Exit criterion»), not the code. The
script is executed in-process (runpy, as `__main__`) from the repository root. Its own checks are
judged by breaking one fact at a time underneath it and expecting the smoke to fail:
- at the storage level (`LocalStorage.write` / `create_if_absent` rewrite what lands in a file), so the
  break is seen by every reader of the file, whichever way the script reads it;
- at the public seam of `thinkhow.workspace` (the name is replaced in the package and in the module
  that defines it), for the access rule and for the reading functions.
`thinkhow.platform.llm.make_llm` refuses every call: the smoke goes through a scripted `facilitate`.
"""

from __future__ import annotations

import io
import json
import os
import runpy
import sys
from collections.abc import Callable, Iterator
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import pytest

import thinkhow.platform.llm as platform_llm
import thinkhow.workspace as workspace
from thinkhow.facilitation.types import ProblemMap
from thinkhow.platform.storage import LocalStorage

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "smoke_test_skel_workspace.py"
SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    ".claude",
}


class RefusingLlm:
    def __getattr__(self, name: str) -> Any:
        raise AssertionError("the model was reached although the smoke uses a scripted facilitate")


def replace_public(m: pytest.MonkeyPatch, name: str, new: Any) -> None:
    """Replace a public function of `thinkhow.workspace` in the package and in its defining module."""
    original = getattr(workspace, name)
    m.setattr(workspace, name, new)
    defining = sys.modules[original.__module__]
    if hasattr(defining, name):
        m.setattr(defining, name, new)


def rewrite_files(m: pytest.MonkeyPatch, suffix: str, change: Callable[[bytes], bytes]) -> None:
    """Every write of a file ending in `suffix` lands changed by `change`."""
    write = LocalStorage.write
    create = LocalStorage.create_if_absent

    def new_write(self: LocalStorage, bucket: Any, path: str, data: bytes, content_type: str) -> None:
        write(self, bucket, path, change(data) if path.endswith(suffix) else data, content_type)

    def new_create(self: LocalStorage, bucket: Any, path: str, data: bytes, content_type: str) -> bool:
        return create(self, bucket, path, change(data) if path.endswith(suffix) else data, content_type)

    m.setattr(LocalStorage, "write", new_write)
    m.setattr(LocalStorage, "create_if_absent", new_create)


def run_smoke(
    monkeypatch: pytest.MonkeyPatch, tmp: Path, sabotage: Callable[[pytest.MonkeyPatch], None] | None = None
) -> tuple[bool, str]:
    """Runs the smoke; returns (succeeded, stdout)."""
    out = io.StringIO()
    with monkeypatch.context() as m:
        m.setattr(platform_llm, "make_llm", lambda *a, **k: RefusingLlm())
        for name in ("TMPDIR", "TEMP", "TMP"):
            m.setenv(name, str(tmp))
        m.setattr("tempfile.tempdir", None)
        m.chdir(REPO)
        if sabotage is not None:
            sabotage(m)
        ok = True
        try:
            with redirect_stdout(out):
                runpy.run_path(str(SCRIPT), run_name="__main__")
        except SystemExit as stop:
            ok = stop.code in (0, None)
        except Exception:
            ok = False
    return ok, out.getvalue()


def repo_files() -> set[Path]:
    found: set[Path] = set()
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        found.update(Path(root) / f for f in files)
    return found


def printed_maps(out: str) -> list[ProblemMap]:
    decoder = json.JSONDecoder()
    maps: list[ProblemMap] = []
    for i, ch in enumerate(out):
        if ch != "{":
            continue
        try:
            value, _ = decoder.raw_decode(out, i)
        except ValueError:
            continue
        if isinstance(value, dict) and "items" in value:
            try:
                maps.append(ProblemMap.model_validate(value))
            except ValueError:
                continue
    return maps


def test_smoke_passes_and_prints_conversation_md_and_map_json(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ok, out = run_smoke(monkeypatch, tmp_path)
    assert ok, out
    assert "<!-- thinkhow:format 1 -->" in out
    assert "<!-- thinkhow:session 1 -->" in out
    for no, role in ((1, "user"), (2, "model"), (3, "user"), (4, "model")):
        assert f"<!-- thinkhow:turn {no} {role} " in out, (no, role)
    assert "<!-- thinkhow:turn 5 " not in out
    assert "<!-- thinkhow:closed" not in out
    maps = printed_maps(out)
    assert maps, "no map.json printed"
    assert any(mp.items for mp in maps), "the printed map.json has no items from the updates"


def test_smoke_works_in_a_temporary_folder_not_in_the_repository(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    before = repo_files()
    ok, _ = run_smoke(monkeypatch, tmp_path)
    assert ok
    assert repo_files() - before == set()


def test_smoke_goes_through_failed_then_retry_answered(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen: list[tuple[str, list[str]]] = []

    def recording(name: str) -> Callable[..., Iterator[Any]]:
        original = getattr(workspace, name)

        def call(*args: Any, **kwargs: Any) -> Iterator[Any]:
            events = original(*args, **kwargs)
            kinds: list[str] = []
            seen.append((name, kinds))

            def gen() -> Iterator[Any]:
                for event in events:
                    kinds.append(type(event).__name__)
                    yield event

            return gen()

        return call

    def sabotage(m: pytest.MonkeyPatch) -> None:
        replace_public(m, "reply", recording("reply"))
        replace_public(m, "retry", recording("retry"))

    ok, out = run_smoke(monkeypatch, tmp_path, sabotage)
    assert ok, out
    replies = [kinds for name, kinds in seen if name == "reply"]
    retries = [kinds for name, kinds in seen if name == "retry"]
    assert len(replies) == 2, seen
    assert replies[0][0] == "Saved" and replies[0][-1] == "Answered", seen
    assert replies[1][0] == "Saved" and replies[1][-1] == "Failed", seen
    assert any("Delta" in kinds for kinds in replies), seen
    assert len(retries) == 1 and retries[0][-1] == "Answered" and "Saved" not in retries[0], seen


def test_smoke_fails_when_the_turn_numbers_are_not_1_to_4(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def sabotage(m: pytest.MonkeyPatch) -> None:
        rewrite_files(
            m, "conversation.md", lambda b: b.replace(b"<!-- thinkhow:turn 4 ", b"<!-- thinkhow:turn 5 ")
        )

    ok, _ = run_smoke(monkeypatch, tmp_path, sabotage)
    assert not ok, "turn numbers 1, 2, 3, 5 were not caught"


def test_smoke_fails_when_session_1_is_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    marker = b"<!-- thinkhow:closed 1 2026-10-22T16:03:00Z -->"

    def add_closed(data: bytes) -> bytes:
        if b"<!-- thinkhow:turn 4 " not in data or marker in data:
            return data
        return data.rstrip(b"\n") + b"\n\n" + marker + b"\n"

    def sabotage(m: pytest.MonkeyPatch) -> None:
        rewrite_files(m, "conversation.md", add_closed)

    ok, _ = run_smoke(monkeypatch, tmp_path, sabotage)
    assert not ok, "a closed session 1 was not caught"


def test_smoke_fails_when_the_map_has_no_items_from_the_updates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    empty = ProblemMap().model_dump_json().encode("utf-8")

    def sabotage(m: pytest.MonkeyPatch) -> None:
        rewrite_files(m, "map.json", lambda b: empty)

    ok, _ = run_smoke(monkeypatch, tmp_path, sabotage)
    assert not ok, "a map without the updates' items was not caught"


def test_smoke_fails_when_person_2_opens_the_topic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    original = workspace.open_topic

    def leaky(storage: Any, user: Any, ref: Any, now: Any) -> Any:
        try:
            return original(storage, user, ref, now)
        except workspace.TopicNotFound:
            stand_in = type(user)(id=ref.uid, email="stand-in@example.com", is_owner=False)
            return original(storage, stand_in, ref, now)

    ok, _ = run_smoke(monkeypatch, tmp_path, lambda m: replace_public(m, "open_topic", leaky))
    assert not ok, "person 2 opening person 1's topic was not caught"


def test_smoke_fails_when_the_owner_cannot_open_the_topic(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    original = workspace.open_topic

    def blind_owner(storage: Any, user: Any, ref: Any, now: Any) -> Any:
        if user.is_owner and user.id != ref.uid:
            raise workspace.TopicNotFound(ref.topic_id)
        return original(storage, user, ref, now)

    ok, _ = run_smoke(monkeypatch, tmp_path, lambda m: replace_public(m, "open_topic", blind_owner))
    assert not ok, "the owner failing to open the topic was not caught"


def test_smoke_fails_when_learning_does_not_get_the_topic(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def nothing(*args: Any, **kwargs: Any) -> Iterator[Any]:
        return iter(())

    ok, _ = run_smoke(monkeypatch, tmp_path, lambda m: replace_public(m, "all_topics_for_learning", nothing))
    assert not ok, "all_topics_for_learning without the topic was not caught"


def test_smoke_fails_when_topic_sessions_is_not_one_session_of_4_turns(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    original = workspace.topic_sessions

    def short(*args: Any, **kwargs: Any) -> list[Any]:
        found = original(*args, **kwargs)
        return [type(s)(no=s.no, turns=list(s.turns)[:-1], closed_at=s.closed_at) for s in found]

    ok, _ = run_smoke(monkeypatch, tmp_path, lambda m: replace_public(m, "topic_sessions", short))
    assert not ok, "a session of 3 turns for learning was not caught"
