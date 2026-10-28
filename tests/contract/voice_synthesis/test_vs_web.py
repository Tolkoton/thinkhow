"""Contract tests of voice-synthesis: `POST /speak` and the topic page (Seams 4, 5, 5a), from the contract."""

from pathlib import Path

from vs_fakes import (
    ALICE,
    FIRST_CHOOSE,
    H_ALICE,
    NO_VOICE_TEXT,
    NOT_ACCEPTED_TEXT,
    UNAVAILABLE_TEXT,
    FakePost,
    Tags,
    cloud,
    make_app,
    new_topic,
    page_url,
)

from thinkhow.platform.tts import ScriptedTts, TtsUnavailable
from thinkhow.workspace import set_language


class FailingTts:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def synthesize(self, text: str, language: str) -> bytes:
        self.calls.append((text, language))
        raise TtsUnavailable("down")


def test_seam5_speak_returns_200_audio_mpeg_with_the_tts_bytes(tmp_path: Path) -> None:
    tts = ScriptedTts(b"ID3-mp3-bytes")
    app = make_app(tmp_path, tts)
    set_language(app.storage, ALICE, "uk-UA")
    r = app.client.post("/speak", data={"text": "Добрий день."}, headers=H_ALICE)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("audio/mpeg")
    assert r.content == b"ID3-mp3-bytes"
    assert tts.calls == [("Добрий день.", "uk-UA")]


def test_speak_response_is_not_cached(tmp_path: Path) -> None:
    app = make_app(tmp_path, ScriptedTts(b"mp3"))
    set_language(app.storage, ALICE, "uk-UA")
    r = app.client.post("/speak", data={"text": "Добрий день."}, headers=H_ALICE)
    assert r.status_code == 200
    assert "no-store" in r.headers.get("cache-control", "")


def test_seam5_language_without_voice_is_409_fragment(tmp_path: Path) -> None:
    app = make_app(tmp_path, ScriptedTts())
    set_language(app.storage, ALICE, "kk-KZ")
    r = app.client.post("/speak", data={"text": "Сәлем"}, headers=H_ALICE)
    assert r.status_code == 409
    assert NO_VOICE_TEXT in r.text
    # «англійською для будь-якої мови»: a second language without a voice, the same English text.
    set_language(app.storage, ALICE, "ky-KG")
    r = app.client.post("/speak", data={"text": "Салам"}, headers=H_ALICE)
    assert r.status_code == 409
    assert NO_VOICE_TEXT in r.text


def test_seam5_empty_text_is_400_fragment(tmp_path: Path) -> None:
    tts = ScriptedTts()
    app = make_app(tmp_path, tts)
    set_language(app.storage, ALICE, "uk-UA")
    r = app.client.post("/speak", data={"text": ""}, headers=H_ALICE)
    assert r.status_code == 400
    assert NOT_ACCEPTED_TEXT in r.text
    assert tts.calls == []


def test_seam4_over_4000_bytes_is_400_through_the_route(tmp_path: Path) -> None:
    tts = ScriptedTts()
    app = make_app(tmp_path, tts)
    set_language(app.storage, ALICE, "uk-UA")
    r = app.client.post("/speak", data={"text": "ж" * 2001}, headers=H_ALICE)
    assert r.status_code == 400
    assert NOT_ACCEPTED_TEXT in r.text
    assert tts.calls == []


def test_seam5_tts_unavailable_is_502_fragment(tmp_path: Path) -> None:
    app = make_app(tmp_path, FailingTts())
    set_language(app.storage, ALICE, "uk-UA")
    r = app.client.post("/speak", data={"text": "Добрий день."}, headers=H_ALICE)
    assert r.status_code == 502
    assert UNAVAILABLE_TEXT in r.text


def test_seam5a_200_without_audio_content_is_502_not_400(tmp_path: Path) -> None:
    app = make_app(tmp_path, cloud(FakePost([(200, {"nothing": "here"})] * 3)))
    set_language(app.storage, ALICE, "uk-UA")
    r = app.client.post("/speak", data={"text": "Добрий день."}, headers=H_ALICE)
    assert r.status_code == 502
    assert UNAVAILABLE_TEXT in r.text


def test_seam5_without_a_language_is_409_of_the_existing_handler(tmp_path: Path) -> None:
    tts = ScriptedTts()
    app = make_app(tmp_path, tts)
    r = app.client.post("/speak", data={"text": "Добрий день."}, headers=H_ALICE)
    assert r.status_code == 409
    assert FIRST_CHOOSE in r.text
    assert tts.calls == []


def test_seam5_topic_page_reply_form_says_whether_there_is_a_voice(tmp_path: Path) -> None:
    app = make_app(tmp_path / "a")
    set_language(app.storage, ALICE, "uk-UA")
    r = app.client.get(page_url(new_topic(app.storage, ALICE)), headers=H_ALICE)
    assert r.status_code == 200
    tag, attrs = Tags(r.text).by_id("reply-form")
    assert tag == "form"
    assert attrs.get("data-voice") == "yes"

    app = make_app(tmp_path / "b")
    set_language(app.storage, ALICE, "kk-KZ")
    r = app.client.get(page_url(new_topic(app.storage, ALICE)), headers=H_ALICE)
    assert r.status_code == 200
    tag, attrs = Tags(r.text).by_id("reply-form")
    assert attrs.get("data-voice") == "no"
