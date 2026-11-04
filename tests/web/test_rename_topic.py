"""Task 209: a person renames a topic of their own — only the title line of conversation.md changes."""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from thinkhow.access import CurrentUser
from thinkhow.platform.config import load_settings
from thinkhow.platform.identity import IapIdentity
from thinkhow.platform.speech import ScriptedSpeech
from thinkhow.platform.storage import LocalStorage
from thinkhow.web.server import Deps, create_app
from thinkhow.workspace import (
    TopicNotFound,
    TopicRef,
    create_topic,
    list_topics,
    open_topic,
    rename_topic,
    reply,
    set_language,
    transcribe,
)
from thinkhow.workspace.conversation import FORMAT_LINE

T0 = datetime(2026, 11, 4, 12, 0, 0, tzinfo=UTC)
ALICE = CurrentUser(id="alice-1", email="alice@example.com", is_owner=False)
OWNER = CurrentUser(id="owner-0", email="owner@example.com", is_owner=True)
TOKENS = {
    "tok-alice": {"sub": "accounts.google.com:alice-1", "email": "alice@example.com"},
    "tok-owner": {"sub": "accounts.google.com:owner-0", "email": "owner@example.com"},
}
H_ALICE = {"x-goog-iap-jwt-assertion": "tok-alice"}
H_OWNER = {"x-goog-iap-jwt-assertion": "tok-owner"}


def _topic(store: LocalStorage, user: CurrentUser, title: str) -> TopicRef:
    return TopicRef(user.id, create_topic(store, user, title, T0))


def _conversation(store: LocalStorage, ref: TopicRef) -> str:
    data = store.read("users", f"{ref.uid}/{ref.topic_id}/conversation.md")
    assert data is not None
    return data.decode("utf-8")


def _folder(store: LocalStorage, ref: TopicRef) -> dict[str, bytes | None]:
    return {p: store.read("users", p) for p in store.list("users", f"{ref.uid}/{ref.topic_id}/")}


# --- workspace -----------------------------------------------------------------------------------


def test_rename_changes_only_the_title_line_and_keeps_the_conversation(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    set_language(store, ALICE, "uk-UA")
    ref = _topic(store, ALICE, "Стара назва")
    list(reply(store, lambda ctx: iter(()), ALICE, ref, "Перший крок.\n<!-- thinkhow:turn 9 -->", T0))
    before, files = _conversation(store, ref).split("\n"), _folder(store, ref)
    rename_topic(store, ALICE, ref, "Нова назва")
    after = _conversation(store, ref).split("\n")
    assert after[:2] == [FORMAT_LINE, "# Нова назва"] and after[2:] == before[2:]
    others = {p: d for p, d in _folder(store, ref).items() if not p.endswith("conversation.md")}
    assert others == {p: d for p, d in files.items() if not p.endswith("conversation.md")}
    assert [t.title for t in list_topics(store, ALICE)] == ["Нова назва"]
    assert open_topic(store, ALICE, ref, T0).title == "Нова назва"


def test_the_new_title_is_normalized_as_a_new_topics(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = _topic(store, ALICE, "Тема")
    rename_topic(store, ALICE, ref, "  Два\r\nрядки  ")
    assert open_topic(store, ALICE, ref, T0).title == "Два рядки"


@pytest.mark.parametrize("title", ["", "   ", "\r\n\t"])
def test_an_empty_title_is_refused_and_nothing_is_written(tmp_path: Path, title: str) -> None:
    store = LocalStorage(tmp_path)
    ref = _topic(store, ALICE, "Тема")
    before = _conversation(store, ref)
    with pytest.raises(ValueError):
        rename_topic(store, ALICE, ref, title)
    assert _conversation(store, ref) == before


def test_nobody_renames_a_topic_of_another_person_not_even_the_owner(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = _topic(store, ALICE, "Тема Аліси")
    with pytest.raises(TopicNotFound):
        rename_topic(store, OWNER, ref, "Чужа назва")
    assert open_topic(store, ALICE, ref, T0).title == "Тема Аліси"


def test_an_unknown_or_malformed_topic_is_not_found_and_nothing_is_created(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    for ref in (TopicRef(ALICE.id, "t-000000000000"), TopicRef(ALICE.id, "../t-000000000000")):
        with pytest.raises(TopicNotFound):
            rename_topic(store, ALICE, ref, "Назва")
    assert store.list("users", "") == []


class _Speech(ScriptedSpeech):
    def __init__(self) -> None:
        super().__init__("текст")
        self.vocabularies: list[list[str]] = []

    def transcribe(self, audio: bytes, mime: str, language: str, vocabulary: Sequence[str] = ()) -> str:
        self.vocabularies.append(list(vocabulary))
        return super().transcribe(audio, mime, language, vocabulary)


def test_voice_hints_take_the_new_title(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    set_language(store, ALICE, "uk-UA")
    ref = _topic(store, ALICE, "Розмова про Kyiv")
    speech = _Speech()
    rename_topic(store, ALICE, ref, "Розмова про Lviv")
    transcribe(store, speech, ALICE, ref, b"\x1a\x45\xdf\xa3" + b"x" * 2000, "audio/webm")
    assert "Lviv" in speech.vocabularies[0] and "Kyiv" not in speech.vocabularies[0]


# --- web -----------------------------------------------------------------------------------------


def _client(tmp_path: Path, store: LocalStorage) -> TestClient:
    settings = load_settings(
        {"THINKHOW_LOCAL": "true", "THINKHOW_LOCAL_DIR": str(tmp_path), "THINKHOW_OWNER_EMAIL": OWNER.email}
    )
    identity = IapIdentity("aud", lambda token, audience: TOKENS[token])
    deps = Deps(store, identity, settings, lambda ctx: iter(()), lambda: T0, ScriptedSpeech(""))
    for user in (ALICE, OWNER):
        set_language(store, user, "uk-UA")
    return TestClient(create_app(deps), raise_server_exceptions=False)


def _url(ref: TopicRef) -> str:
    return f"/topics/{ref.uid}/{ref.topic_id}"


def _rename_forms(html: str) -> list[str]:
    return re.findall(r'<form[^>]*action="(/topics/[^"]+/rename)"', html)


@pytest.mark.parametrize(("back", "location"), [("home", "/"), ("topic", "page"), ("", "/"), ("//evil", "/")])
def test_post_rename_saves_the_title_and_goes_back_where_it_came_from(
    tmp_path: Path, back: str, location: str
) -> None:
    store = LocalStorage(tmp_path)
    client = _client(tmp_path, store)
    ref = _topic(store, ALICE, "Стара назва")
    data = {"new_title": "Нова назва", "back": back}
    r = client.post(_url(ref) + "/rename", data=data, headers=H_ALICE, follow_redirects=False)
    assert (r.status_code, r.headers["location"]) == (303, _url(ref) if location == "page" else location)
    home, page = client.get("/", headers=H_ALICE).text, client.get(_url(ref), headers=H_ALICE).text
    assert "Нова назва" in home and "Стара назва" not in home
    assert "<h1>Нова назва</h1>" in page and "Стара назва" not in page


def test_post_rename_with_an_empty_title_is_400_and_keeps_the_old_one(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    client = _client(tmp_path, store)
    ref = _topic(store, ALICE, "Стара назва")
    r = client.post(_url(ref) + "/rename", data={"new_title": "  "}, headers=H_ALICE, follow_redirects=False)
    assert r.status_code == 400 and "Назва теми порожня." in r.text
    assert open_topic(store, ALICE, ref, T0).title == "Стара назва"


def test_post_rename_of_a_foreign_topic_is_404_and_changes_nothing(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    client = _client(tmp_path, store)
    ref = _topic(store, ALICE, "Тема Аліси")
    r = client.post(
        _url(ref) + "/rename", data={"new_title": "Чужа"}, headers=H_OWNER, follow_redirects=False
    )
    assert r.status_code == 404 and "Тему не знайдено." in r.text
    assert open_topic(store, ALICE, ref, T0).title == "Тема Аліси"


def test_home_has_a_rename_form_with_the_current_title_for_each_own_topic_only(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    client = _client(tmp_path, store)
    mine = _topic(store, OWNER, "Моя тема")
    _topic(store, ALICE, "Тема Аліси")
    page = client.get("/", headers=H_OWNER).text
    assert _rename_forms(page) == [_url(mine) + "/rename"]
    form = page[page.index('<details class="rename">') :]
    form = form[: form.index("</details>")]
    assert 'aria-label="Перейменувати"' in form and 'value="Моя тема"' in form and "required" in form
    assert 'name="back" value="home"' in form


def test_the_own_topic_page_has_the_rename_form_beside_the_title_and_a_foreign_one_has_none(
    tmp_path: Path,
) -> None:
    store = LocalStorage(tmp_path)
    client = _client(tmp_path, store)
    ref = _topic(store, ALICE, "Тема Аліси")
    own = client.get(_url(ref), headers=H_ALICE).text
    foreign = client.get(_url(ref), headers=H_OWNER).text
    assert _rename_forms(own) == [_url(ref) + "/rename"] and 'name="back" value="topic"' in own
    row = own[own.index('<div class="title-row">') :]
    assert row.index("<h1>") < row.index('<details class="rename">') < row.index("</div>")
    assert _rename_forms(foreign) == [] and "Перейменувати" not in foreign


def test_a_title_with_markup_is_escaped_in_the_field(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    client = _client(tmp_path, store)
    _topic(store, ALICE, 'Лапки " і <b>')
    page = client.get("/", headers=H_ALICE).text
    assert 'value="Лапки &#34; і &lt;b&gt;"' in page
