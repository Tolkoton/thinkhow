"""Task 207: every button is an icon without visible words; its name is in aria-label for screen readers."""

from __future__ import annotations

from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from thinkhow.access import CurrentUser
from thinkhow.platform.config import load_settings
from thinkhow.platform.identity import IapIdentity
from thinkhow.platform.speech import ScriptedSpeech
from thinkhow.platform.storage import LocalStorage
from thinkhow.web.server import Deps, create_app
from thinkhow.workspace import TopicRef, create_topic, set_language

T0 = datetime(2026, 10, 25, 12, 0, 0, tzinfo=UTC)
ALICE = CurrentUser(id="alice-1", email="alice@example.com", is_owner=False)
H_ALICE = {"x-goog-iap-jwt-assertion": "tok-alice"}
TOKENS = {"tok-alice": {"sub": "accounts.google.com:alice-1", "email": "alice@example.com"}}
CONTROLS = ("button", "summary")


class Controls(HTMLParser):
    """The page's buttons and <summary>s: attributes, the words inside, and whether an <svg> is inside."""

    def __init__(self, html: str) -> None:
        super().__init__()
        self.found: list[dict[str, Any]] = []
        self._open: list[dict[str, Any]] = []
        self.header_links: list[dict[str, str | None]] = []
        self._in_header = False
        self.feed(html)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == "header":
            self._in_header = True
        if tag == "a" and self._in_header:
            self.header_links.append(a)
        if tag == "svg":
            for c in self._open:
                c["svg"] = True
                c["svg_hidden"] = c.get("svg_hidden", True) and a.get("aria-hidden") == "true"
        if tag in CONTROLS:
            c = {"tag": tag, "attrs": a, "text": "", "svg": False}
            self.found.append(c)
            self._open.append(c)

    def handle_endtag(self, tag: str) -> None:
        if tag == "header":
            self._in_header = False
        if tag in CONTROLS and self._open:
            self._open.pop()

    def handle_data(self, data: str) -> None:
        for c in self._open:
            c["text"] += data


def _client(tmp_path: Path) -> tuple[TestClient, TopicRef]:
    store = LocalStorage(tmp_path)
    settings = load_settings(
        {
            "THINKHOW_LOCAL": "true",
            "THINKHOW_LOCAL_DIR": str(tmp_path),
            "THINKHOW_OWNER_EMAIL": "o@example.com",
        }
    )
    identity = IapIdentity("aud", lambda token, audience: TOKENS[token])
    deps = Deps(store, identity, settings, lambda ctx: iter(()), lambda: T0, ScriptedSpeech(""))
    set_language(store, ALICE, "uk-UA")
    ref = TopicRef(ALICE.id, create_topic(store, ALICE, "Тема", T0))
    return TestClient(create_app(deps)), ref


def _pages(tmp_path: Path) -> dict[str, Controls]:
    client, ref = _client(tmp_path)
    paths = {"home": "/", "language": "/language", "topic": f"/topics/{ref.uid}/{ref.topic_id}"}
    return {name: Controls(client.get(path, headers=H_ALICE).text) for name, path in paths.items()}


def test_every_button_is_an_icon_with_no_words_and_a_name_for_screen_readers(tmp_path: Path) -> None:
    for name, page in _pages(tmp_path).items():
        assert page.found, f"no buttons on {name}"
        for c in page.found:
            label = c["attrs"].get("aria-label")
            assert label, f"{name}: <{c['tag']} id={c['attrs'].get('id')!r}> has no aria-label"
            assert c["text"].strip() == "", f"{name}: «{label}» shows words {c['text'].strip()!r}"
            assert c["svg"] and c["svg_hidden"], f"{name}: «{label}» has no icon hidden from screen readers"


def test_the_pages_name_every_button_the_task_lists(tmp_path: Path) -> None:
    pages = _pages(tmp_path)
    labels = {name: {c["attrs"].get("aria-label") for c in page.found} for name, page in pages.items()}
    assert labels["home"] == {"Створити", "Видалити", "Так, видалити"}
    assert labels["language"] == {"Зберегти"}
    assert labels["topic"] == {
        "Говорити",
        "Розпізнати ще раз",
        "Надіслати",
        "Спробуйте ще раз",
        "Видалити",
        "Так, видалити",
    }


def test_the_language_link_in_the_header_is_a_globe_named_for_screen_readers(tmp_path: Path) -> None:
    home = _pages(tmp_path)["home"]
    language = [a for a in home.header_links if a.get("href") == "/language"]
    assert [a.get("aria-label") for a in language] == ["Мова"]


def test_mic_state_words_are_for_screen_readers_only(tmp_path: Path) -> None:
    client, ref = _client(tmp_path)
    topic = client.get(f"/topics/{ref.uid}/{ref.topic_id}", headers=H_ALICE).text
    assert '<span id="mic-state" class="sr-only" aria-live="polite"></span>' in topic
    assert 'aria-pressed="false"' in topic
