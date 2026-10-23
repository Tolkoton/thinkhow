"""Contract tests of continuous-analysis: no close button, no route, the new reader (slice tester)."""

from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

import pytest
from ca_fakes import ALICE, DAY, H_ALICE, LS, LT, NOW, H, M, legacy_topic, make_client, new_topic, pair, say

import thinkhow.workspace as workspace
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import TopicNotFound, TopicRef, open_topic, topic_sessions


class Tags(HTMLParser):
    def __init__(self, html: str) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self.texts: list[str] = []
        self.feed(html)
        self.close()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag, dict(attrs)))

    def handle_data(self, data: str) -> None:
        self.texts.append(data)


def page_url(ref: TopicRef) -> str:
    return f"/topics/{ref.uid}/{ref.topic_id}"


# --- Seam 4: no button, no route -------------------------------------------------------------------


def test_seam4_the_own_topic_page_has_no_close_button_and_no_close_form(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "data")
    ref = new_topic(storage, ALICE, NOW - 2 * H)
    say(storage, ALICE, ref, "Хочу відкрити кав'ярню.", "Що може піти не так?", NOW - H)
    client = make_client(tmp_path, storage)
    r = client.get(page_url(ref), headers=H_ALICE)
    assert r.status_code == 200
    page = Tags(r.text)
    assert "Завершити сесію" not in "".join(page.texts)
    assert not any("Завершити сесію" in (v or "") for _, a in page.tags for v in a.values())
    for tag, attrs in page.tags:
        if tag == "form":
            assert not (attrs.get("action") or "").endswith("/close"), attrs


def test_seam4_post_close_is_404(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "data")
    ref = new_topic(storage, ALICE, NOW - 2 * H)
    say(storage, ALICE, ref, "Хочу відкрити кав'ярню.", "Що може піти не так?", NOW - H)
    client = make_client(tmp_path, storage)
    r = client.post(page_url(ref) + "/close", headers=H_ALICE)
    assert r.status_code == 404
    raw = storage.read("users", f"{ref.uid}/{ref.topic_id}/conversation.md") or b""
    assert b"thinkhow:closed" not in raw


def test_seam4_workspace_has_no_close_session_closed_sessions_closed_session() -> None:
    for name in ("close_session", "closed_sessions", "ClosedSession"):
        assert not hasattr(workspace, name), name
        assert name not in workspace.__all__, name


# --- topic_sessions --------------------------------------------------------------------------------


def test_topic_sessions_are_the_sessions_open_topic_shows(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    old = NOW - 10 * DAY
    legacy = legacy_topic(
        storage,
        ALICE,
        [
            LS(1, pair(1, "перша", old), closed=old + H),  # closed by the legacy marker
            LS(2, pair(3, "друга", old + 2 * DAY)),  # closed by silence
            LS(3, [LT(5, "user", "третя без відповіді", NOW - 2 * H)]),  # open
        ],
    )
    fresh = new_topic(storage, ALICE, NOW - 3 * H)  # one empty session
    lively = new_topic(storage, ALICE, NOW - 3 * DAY)
    say(storage, ALICE, lively, "Один.", "Два?", NOW - 3 * DAY + M)
    say(storage, ALICE, lively, "Три.", "Чотири?", NOW - H)
    for ref in (legacy, fresh, lively):
        for now in (NOW, NOW + 2 * DAY):
            got = topic_sessions(storage, ref, now)
            assert got == open_topic(storage, ALICE, ref, now).sessions, (ref, now)
    assert [[t.no for t in s.turns] for s in topic_sessions(storage, legacy, NOW)] == [[1, 2], [3, 4], [5]]


def test_topic_sessions_now_without_time_zone_is_value_error(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    ref = new_topic(storage, ALICE, NOW - H)
    with pytest.raises(ValueError):
        topic_sessions(storage, ref, datetime(2026, 10, 23, 3, 0, 0))


def test_topic_sessions_of_a_malformed_or_absent_ref_is_topic_not_found(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    new_topic(storage, ALICE, NOW - H)
    for ref in (
        TopicRef(ALICE.id, "not-a-topic"),
        TopicRef(ALICE.id, "t-000000000000"),
        TopicRef("../etc", "t-000000000000"),
    ):
        with pytest.raises(TopicNotFound):
            topic_sessions(storage, ref, NOW)
