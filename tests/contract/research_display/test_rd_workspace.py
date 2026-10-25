"""Contract tests of research-display, `workspace`: `open_topic` gives `TopicView.research` from research.json
(slice tester; from the contract)."""

from pathlib import Path

import pytest
from rd_fakes import entry, put_research, seed_answered, write_research
from rq_fakes import T0
from skelweb_fakes import ALICE, BOB, OWNER

from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import ResearchView, open_topic

EXCHANGES = [("Скільки коштує оренда?", "Від 15 євро."), ("А кава?", "3 євро."), ("Добре.", "Що далі?")]


def test_open_topic_gives_one_research_view_per_entry_in_file_order(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = seed_answered(store, ALICE, "Тема", EXCHANGES, T0)
    assert open_topic(store, ALICE, ref, T0).research == ()
    write_research(
        store,
        ref,
        [
            entry(4, "<div>кава</div>", [("Кава", "https://c.example/coffee")]),
            entry(2, None),
            entry(4, "<div>друга</div>"),
        ],
    )
    assert open_topic(store, ALICE, ref, T0).research == (
        ResearchView(4, "<div>кава</div>"),
        ResearchView(2, None),
        ResearchView(4, "<div>друга</div>"),
    )


def test_open_topic_research_for_the_owner_on_a_foreign_topic(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = seed_answered(store, BOB, "Тема Боба", EXCHANGES[:1], T0)
    write_research(store, ref, [entry(2, "<div>a</div>")])
    assert open_topic(store, OWNER, ref, T0).research == (ResearchView(2, "<div>a</div>"),)


def test_open_topic_with_an_unreadable_research_json_raises(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = seed_answered(store, ALICE, "Тема", EXCHANGES[:1], T0)
    put_research(store, ref, b'{"entries": [{"turn": ')
    with pytest.raises(Exception):  # noqa: B017 — the contract names no type: "виняток як і з routing.json"
        open_topic(store, ALICE, ref, T0)
