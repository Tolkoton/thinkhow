"""Contract tests of voice-dictation: the `voice` route and the topic page (Seams 1-4, 6-8)."""

from pathlib import Path
from typing import Any

import pytest
from google.genai import types
from vd_fakes import (
    ALICE,
    AUDIO,
    BOB,
    FIRST_CHOOSE,
    H_ALICE,
    H_OWNER,
    NOT_ACCEPTED,
    NOT_RECOGNIZED,
    OWNER,
    TOPIC_NOT_FOUND,
    Clock,
    FakeGenai,
    FormPage,
    RecordingSpeech,
    Sleeps,
    error_fragment,
    make_app,
    new_topic,
    page_url,
    snapshot,
    text_part,
    voice_url,
)

from thinkhow.platform.speech import GeminiSpeech, SpeechUnavailable
from thinkhow.workspace import set_language


def post_voice(app: Any, url: str, body: bytes, mime: str | None, headers: dict[str, str]) -> Any:
    sent = dict(headers)
    if mime is not None:
        sent["Content-Type"] = mime
    return app.client.post(url, content=body, headers=sent)


# --- the happy path -----------------------------------------------------------------------------


def test_voice_returns_200_json_with_the_text(tmp_path: Path) -> None:
    speech = RecordingSpeech(text="нову роботу, зарплата і друзів")
    app = make_app(tmp_path, speech)
    set_language(app.storage, ALICE, "uk-UA")
    ref = new_topic(app.storage, ALICE)
    before = snapshot(tmp_path / "data")
    r = post_voice(app, voice_url(ref), AUDIO, "audio/webm;codecs=opus", H_ALICE)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    assert r.json() == {"text": "нову роботу, зарплата і друзів"}
    assert speech.calls == [(AUDIO, "audio/webm;codecs=opus", "uk-UA")]
    assert snapshot(tmp_path / "data") == before


# --- Seam 1 through the route -------------------------------------------------------------------


def test_seam1_blank_model_text_is_200_with_empty_text_not_502(tmp_path: Path) -> None:
    client = FakeGenai([[text_part("   ")]])
    speech = GeminiSpeech(client, "gemini-3.5-transcribe", 120.0, 3, sleep=Sleeps(), clock=Clock())
    app = make_app(tmp_path, speech)
    set_language(app.storage, ALICE, "uk-UA")
    ref = new_topic(app.storage, ALICE)
    r = post_voice(app, voice_url(ref), AUDIO, "audio/webm;codecs=opus", H_ALICE)
    assert r.status_code == 200
    assert r.json() == {"text": ""}


# --- Seam 2 -------------------------------------------------------------------------------------


def test_seam2_without_a_language_is_409_fragment_and_no_model_call(tmp_path: Path) -> None:
    speech = RecordingSpeech()
    app = make_app(tmp_path, speech)
    ref = new_topic(app.storage, ALICE)
    r = post_voice(app, voice_url(ref), AUDIO, "audio/webm", H_ALICE)
    assert r.status_code == 409
    assert error_fragment(r.text) == FIRST_CHOOSE
    assert speech.calls == []


# --- Seam 3 -------------------------------------------------------------------------------------


def test_seam3_foreign_topic_is_404_and_no_model_call_even_for_the_owner(tmp_path: Path) -> None:
    speech = RecordingSpeech()
    app = make_app(tmp_path, speech)
    for user in (ALICE, BOB, OWNER):
        set_language(app.storage, user, "uk-UA")
    bob_ref = new_topic(app.storage, BOB, "Тема Боба")
    for headers in (H_ALICE, H_OWNER):
        r = post_voice(app, voice_url(bob_ref), AUDIO, "audio/webm", headers)
        assert r.status_code == 404
        assert error_fragment(r.text) == TOPIC_NOT_FOUND
    absent = post_voice(app, "/topics/alice-1/t-000000000000/voice", AUDIO, "audio/webm", H_ALICE)
    assert absent.status_code == 404
    assert error_fragment(absent.text) == TOPIC_NOT_FOUND
    assert speech.calls == []


# --- Seam 4 through the route -------------------------------------------------------------------


def test_seam4_speech_unavailable_is_502_fragment(tmp_path: Path) -> None:
    speech = RecordingSpeech(fail=SpeechUnavailable("no text"))
    app = make_app(tmp_path, speech)
    set_language(app.storage, ALICE, "uk-UA")
    ref = new_topic(app.storage, ALICE)
    r = post_voice(app, voice_url(ref), AUDIO, "audio/mp4", H_ALICE)
    assert r.status_code == 502
    assert error_fragment(r.text) == NOT_RECOGNIZED


# --- Seam 6 -------------------------------------------------------------------------------------


def test_seam6_the_model_call_runs_outside_the_event_loop_thread(tmp_path: Path) -> None:
    speech = RecordingSpeech(text="текст")
    app = make_app(tmp_path, speech)
    set_language(app.storage, ALICE, "uk-UA")
    ref = new_topic(app.storage, ALICE)
    r = post_voice(app, voice_url(ref), AUDIO, "audio/webm", H_ALICE)
    assert r.status_code == 200
    assert speech.loop_running == [False]


# --- Seam 7 -------------------------------------------------------------------------------------


def test_seam7_empty_body_or_non_audio_type_is_400_with_the_voice_fragment(tmp_path: Path) -> None:
    speech = RecordingSpeech()
    app = make_app(tmp_path, speech)
    set_language(app.storage, ALICE, "uk-UA")
    ref = new_topic(app.storage, ALICE)
    cases: list[tuple[bytes, str | None]] = [
        (b"", "audio/webm;codecs=opus"),
        (AUDIO, "text/plain"),
        (AUDIO, None),
        (AUDIO, "video/webm"),
    ]
    for body, mime in cases:
        r = post_voice(app, voice_url(ref), body, mime, H_ALICE)
        assert r.status_code == 400, (body[:4], mime)
        assert error_fragment(r.text) == NOT_ACCEPTED
    assert speech.calls == []


# --- Seam 8 through the route -------------------------------------------------------------------


def test_seam8_sdk_error_while_building_the_request_is_502_not_400(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args: Any, **kwargs: Any) -> Any:
        raise ValueError("pydantic-like validation error inside the SDK")

    monkeypatch.setattr(types.Part, "from_bytes", boom)
    speech = GeminiSpeech(
        FakeGenai(["не має дійти"]), "gemini-3.5-transcribe", 120.0, 3, sleep=Sleeps(), clock=Clock()
    )
    app = make_app(tmp_path, speech)
    set_language(app.storage, ALICE, "uk-UA")
    ref = new_topic(app.storage, ALICE)
    r = post_voice(app, voice_url(ref), AUDIO, "audio/webm;codecs=opus", H_ALICE)
    assert r.status_code == 502
    assert error_fragment(r.text) == NOT_RECOGNIZED


# --- the topic page -----------------------------------------------------------------------------


def test_mic_recognize_and_state_are_in_the_form_of_the_own_topic_page_only(tmp_path: Path) -> None:
    app = make_app(tmp_path, RecordingSpeech())
    for user in (ALICE, BOB, OWNER):
        set_language(app.storage, user, "uk-UA")
    ref = new_topic(app.storage, ALICE)
    r = app.client.get(page_url(ref), headers=H_ALICE)
    assert r.status_code == 200
    page = FormPage(r.text)
    mic = page.by_id("mic")
    assert mic is not None, "no #mic on the own topic page"
    assert mic["tag"] == "button" and mic["attrs"].get("type") == "button"
    assert mic["in_form"]
    assert FormPage.text_of(mic) == "🎤 Говорити"
    recognize = page.by_id("recognize")
    assert recognize is not None, "no #recognize on the own topic page"
    assert recognize["tag"] == "button" and recognize["attrs"].get("type") == "button"
    assert "hidden" in recognize["attrs"]
    assert FormPage.text_of(recognize) == "Розпізнати ще раз"
    state = page.by_id("mic-state")
    assert state is not None and state["tag"] == "span"
    # the owner reads Bob's topic without a form: no microphone there
    bob_ref = new_topic(app.storage, BOB, "Тема Боба")
    foreign = app.client.get(page_url(bob_ref), headers=H_OWNER)
    assert foreign.status_code == 200
    other = FormPage(foreign.text)
    assert other.by_id("mic") is None
    assert other.by_id("recognize") is None
