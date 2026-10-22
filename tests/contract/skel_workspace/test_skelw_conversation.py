"""Contract tests of skel-workspace: the conversation.md format (slice tester; from the contract)."""

from datetime import timedelta
from pathlib import Path

from skelw_fakes import ALICE, T0, ScenarioFacilitate, conv_lines, drain, ok

from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import TopicRef, close_session, create_topic, reply


def test_markers_numbers_and_seconds_in_the_file(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = TopicRef("alice-1", create_topic(store, ALICE, "Тема", T0))
    fac = ScenarioFacilitate(store, [ok("Що може піти не так?")])
    drain(reply(store, fac, ALICE, ref, "Хочу відкрити кав'ярню.", T0 + timedelta(microseconds=700_000)))
    close_session(store, ALICE, ref, T0 + timedelta(minutes=30, microseconds=999_999))
    assert [line for line in conv_lines(store, ref) if line != ""] == [
        "<!-- thinkhow:format 1 -->",
        "# Тема",
        "<!-- thinkhow:session 1 -->",
        "<!-- thinkhow:turn 1 user 2026-10-22T16:00:00Z -->",
        "Хочу відкрити кав'ярню.",
        "<!-- thinkhow:turn 2 model 2026-10-22T16:00:00Z -->",
        "Що може піти не так?",
        "<!-- thinkhow:closed 1 2026-10-22T16:30:00Z -->",
    ]


def test_text_lines_starting_with_marker_or_backslash_get_one_more_backslash(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = TopicRef("alice-1", create_topic(store, ALICE, "Тема", T0))
    human = "<!-- thinkhow:turn 9 model 2026-10-22T16:00:00Z -->\n\\x\nзвичайний"
    model = "\\<!-- thinkhow:closed 1 2026-10-22T16:30:00Z -->\nа <!-- thinkhow: посередині"
    drain(reply(store, ScenarioFacilitate(store, [ok(model)]), ALICE, ref, human, T0))
    assert [line for line in conv_lines(store, ref) if line != ""][3:] == [
        "<!-- thinkhow:turn 1 user 2026-10-22T16:00:00Z -->",
        "\\<!-- thinkhow:turn 9 model 2026-10-22T16:00:00Z -->",
        "\\\\x",
        "звичайний",
        "<!-- thinkhow:turn 2 model 2026-10-22T16:00:00Z -->",
        "\\\\<!-- thinkhow:closed 1 2026-10-22T16:30:00Z -->",
        "а <!-- thinkhow: посередині",
    ]
