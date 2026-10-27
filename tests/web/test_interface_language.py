"""Task 208: the interface speaks the language the person chose; before a choice, the browser's."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from thinkhow import knowledge
from thinkhow.access import CurrentUser
from thinkhow.facilitation.types import Decision, FacilitatorUpdate, ReplyDelta, Rev, RoutingEvent
from thinkhow.platform.config import load_settings
from thinkhow.platform.identity import IapIdentity
from thinkhow.platform.speech import ScriptedSpeech
from thinkhow.platform.storage import LocalStorage
from thinkhow.web import ui_text
from thinkhow.web.server import Deps, create_app
from thinkhow.workspace import LANGUAGES, TopicRef, create_topic, reply, set_language

T0 = datetime(2026, 10, 27, 12, 0, 0, tzinfo=UTC)
ALICE = CurrentUser(id="alice-1", email="alice@example.com", is_owner=False)
H_ALICE = {"x-goog-iap-jwt-assertion": "tok-alice"}
TOKENS = {"tok-alice": {"sub": "accounts.google.com:alice-1", "email": "alice@example.com"}}
ROOT = Path(__file__).resolve().parents[2]
LOCALES = ROOT / "src" / "thinkhow" / "web" / "locales"


def _cards(tmp_path: Path) -> dict[str, knowledge.Card]:
    store = LocalStorage(tmp_path / "knowledge")
    knowledge.seed(store, ROOT / "cards")
    return dict(knowledge.current(store).cards)


CARDS = _cards(Path(__import__("tempfile").mkdtemp()))
CYRILLIC_UK = re.compile(r"[ІіЇїЄєҐґ]|Мої теми|Модель мислення|Сесія")


def _raw(name: str) -> dict[str, str]:
    data: dict[str, str] = json.loads((LOCALES / f"{name}.json").read_text(encoding="utf-8"))
    return data


def _placeholders(text: str) -> list[str]:
    return sorted(re.findall(r"\{\w+\}", text))


def _client(tmp_path: Path, code: str | None) -> tuple[TestClient, TopicRef]:
    store = LocalStorage(tmp_path)
    settings = load_settings(
        {
            "THINKHOW_LOCAL": "true",
            "THINKHOW_LOCAL_DIR": str(tmp_path),
            "THINKHOW_OWNER_EMAIL": "o@example.com",
        }
    )
    identity = IapIdentity("aud", lambda token, audience: TOKENS[token])
    deps = Deps(store, identity, settings, lambda ctx: iter(()), lambda: T0, ScriptedSpeech(""), cards=CARDS)
    if code:
        set_language(store, ALICE, code)
    ref = TopicRef(ALICE.id, create_topic(store, ALICE, "Тема", T0))
    if code:
        choose = Decision.model_validate(
            {
                "turn": 1,
                "rev": Rev(rev=1, n=25).model_dump(),
                "kind": "choose",
                "profile": None,
                "candidates": [],
                "card_id": "five-whys",
                "end": None,
                "why": "w",
            }
        )
        update = FacilitatorUpdate(reply="?", current_phase_id=None, phase_exit_met=False, map_updates=[])
        answer = [RoutingEvent(choose), ReplyDelta("?"), update]
        list(reply(store, lambda ctx: iter(answer), ALICE, ref, "Lorem.", T0))
    return TestClient(create_app(deps)), ref


def test_every_listed_language_has_every_word_with_the_same_placeholders() -> None:
    source = _raw("uk")
    for name in sorted({ui_text.catalog_name(lang.code) for lang in LANGUAGES} - {"uk"}):
        words = _raw(name)
        assert set(source) <= set(words), (name, sorted(set(source) - set(words)))
        for key, text in source.items():
            assert _placeholders(words[key]) == _placeholders(text), (name, key, words[key])
            assert words[key].strip(), (name, key)


def test_every_card_has_its_title_in_every_language_but_the_source() -> None:
    for name in sorted({ui_text.catalog_name(lang.code) for lang in LANGUAGES} - {"uk"}):
        words = _raw(name)
        missing = [card for card in CARDS if not words.get(f"card.{card}", "").strip()]
        assert not missing, (name, missing)


def test_the_pages_speak_the_chosen_language(tmp_path: Path) -> None:
    client, ref = _client(tmp_path, "pl-PL")
    pl = ui_text.texts("pl")
    home = client.get("/", headers=H_ALICE).text
    topic = client.get(f"/topics/{ref.uid}/{ref.topic_id}", headers=H_ALICE).text
    language = client.get("/language", headers=H_ALICE).text
    assert pl["my_topics"] in home and pl["new_topic"] in home and '<html lang="pl" dir="ltr">' in home
    assert pl["session"].format(n=1) in topic and f'aria-label="{pl["send"]}"' in topic
    assert pl["method_leads"].format(title=pl["card.five-whys"]) in topic
    assert pl["card.five-whys"] in topic
    assert pl["language_prompt"] in language
    for page in (home, topic, language):
        words = page.replace("Тема", "")  # the topic's own name; below, the list's endonyms
        for lang in LANGUAGES:
            words = words.replace(lang.name, "")
        assert not CYRILLIC_UK.search(words), CYRILLIC_UK.search(words)


def test_the_script_gets_its_words_in_the_chosen_language(tmp_path: Path) -> None:
    client, ref = _client(tmp_path, "ja-JP")
    topic = client.get(f"/topics/{ref.uid}/{ref.topic_id}", headers=H_ALICE).text
    found = re.search(r'<script id="ui-text" type="application/json">(.*?)</script>', topic, re.S)
    assert found, topic
    ja = ui_text.texts("ja")
    assert json.loads(found.group(1)) == {k[3:]: v for k, v in ja.items() if k.startswith("js_")}


def test_a_right_to_left_language_turns_the_page(tmp_path: Path) -> None:
    client, _ = _client(tmp_path, "ar-EG")
    assert '<html lang="ar" dir="rtl">' in client.get("/", headers=H_ALICE).text


def test_an_error_comes_in_the_chosen_language(tmp_path: Path) -> None:
    client, _ = _client(tmp_path, "de-DE")
    r = client.post("/topics", data={"title": ""}, headers=H_ALICE)
    assert r.status_code == 400 and ui_text.texts("de")["err_empty_title"] in r.text
    r = client.get("/topics/alice-1/t-000000000000", headers=H_ALICE)
    assert r.status_code == 404 and ui_text.texts("de")["err_topic_not_found"] in r.text


@pytest.mark.parametrize(
    ("header", "name"),
    [("en-US,en;q=0.9", "en"), ("ja", "ja"), ("ru;q=0.9, ka;q=0.8", "ka"), ("ru", "en"), (None, "uk")],
)
def test_before_a_choice_the_language_page_speaks_the_browsers_language(
    tmp_path: Path, header: str | None, name: str
) -> None:
    client, _ = _client(tmp_path, None)
    headers = H_ALICE | ({"accept-language": header} if header else {})
    page = client.get("/language", headers=headers).text
    words = ui_text.texts(name)
    assert words["language_prompt"] in page and words["choose_language"] in page
    assert f'<html lang="{name}"' in page


@pytest.mark.parametrize(
    ("header", "name"),
    [
        ("zh-CN", "cmn"),
        ("zh-TW", "cmn"),
        ("zh-HK", "yue"),
        ("nn-NO", "nb"),
        ("fr-CA;q=0.5, pt-BR", "pt"),
        ("*, xx", "en"),
        ("tl", "fil"),
        ("uk;q=0, de", "de"),
    ],
)
def test_browser_tags_find_the_listed_language(header: str, name: str) -> None:
    assert ui_text.from_header(header) == name


def test_a_card_title_unknown_to_the_catalog_stays_the_cards_own() -> None:
    card = CARDS["five-whys"]
    assert ui_text.card_title(card, ui_text.texts("uk")) == card.title
    assert ui_text.card_title(card, ui_text.texts("en")) == "Five whys with branching"
