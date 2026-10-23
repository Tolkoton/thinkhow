"""Contract tests of voice-dictation: workspace.transcribe, its Flow and its errors (from the contract)."""

from pathlib import Path

import pytest
from vd_fakes import ALICE, AUDIO, BOB, OWNER, RecordingSpeech, new_topic, snapshot

from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import NoLanguage, TopicNotFound, TopicRef, set_language, transcribe


def test_transcribe_returns_the_speech_text_with_mime_unchanged_and_writes_nothing(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path / "data")
    set_language(store, ALICE, "uk-UA")
    ref = new_topic(store, ALICE)
    before = snapshot(tmp_path)
    speech = RecordingSpeech(text="нову роботу")
    assert transcribe(store, speech, ALICE, ref, AUDIO, "AUDIO/WebM; codecs=opus") == "нову роботу"
    assert speech.calls == [(AUDIO, "AUDIO/WebM; codecs=opus", "uk-UA")]
    assert snapshot(tmp_path) == before


def test_transcribe_into_a_foreign_topic_is_topic_not_found_even_for_the_owner(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path / "data")
    for user in (ALICE, BOB, OWNER):
        set_language(store, user, "uk-UA")
    bob_ref = new_topic(store, BOB, "Тема Боба")
    speech = RecordingSpeech()
    for user in (ALICE, OWNER):
        with pytest.raises(TopicNotFound):
            transcribe(store, speech, user, bob_ref, AUDIO, "audio/webm")
    assert speech.calls == []


def test_transcribe_into_an_absent_own_topic_is_topic_not_found_and_no_model_call(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path / "data")
    set_language(store, ALICE, "uk-UA")
    speech = RecordingSpeech()
    with pytest.raises(TopicNotFound):
        transcribe(store, speech, ALICE, TopicRef("alice-1", "t-000000000000"), AUDIO, "audio/webm")
    assert speech.calls == []


def test_transcribe_without_a_language_is_no_language_and_no_model_call(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path / "data")
    ref = new_topic(store, ALICE)
    speech = RecordingSpeech()
    with pytest.raises(NoLanguage):
        transcribe(store, speech, ALICE, ref, AUDIO, "audio/webm")
    assert speech.calls == []


def test_transcribe_empty_audio_or_a_non_audio_type_is_value_error_and_no_model_call(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path / "data")
    set_language(store, ALICE, "uk-UA")
    ref = new_topic(store, ALICE)
    speech = RecordingSpeech()
    cases = [
        (b"", "audio/webm;codecs=opus"),
        (AUDIO, "text/plain"),
        (AUDIO, ""),
        (AUDIO, "video/webm"),
        (AUDIO, "application/octet-stream"),
        (AUDIO, "audiox/webm"),
    ]
    for audio, mime in cases:
        with pytest.raises(ValueError):
            transcribe(store, speech, ALICE, ref, audio, mime)
    assert speech.calls == []


def test_transcribe_mime_check_ignores_case_parameters_and_spaces(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path / "data")
    set_language(store, ALICE, "uk-UA")
    ref = new_topic(store, ALICE)
    speech = RecordingSpeech()
    for mime in ("audio/mp4", "AUDIO/WebM; codecs=opus", " Audio/MP4 ;codecs=opus", "audio/webm"):
        transcribe(store, speech, ALICE, ref, AUDIO, mime)
    assert [m for _, m, _ in speech.calls] == [
        "audio/mp4",
        "AUDIO/WebM; codecs=opus",
        " Audio/MP4 ;codecs=opus",
        "audio/webm",
    ]


def test_transcribe_checks_the_topic_first_then_the_language_then_the_audio(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path / "data")
    bob_ref = new_topic(store, BOB, "Тема Боба")
    own = new_topic(store, ALICE)
    speech = RecordingSpeech()
    # no language, empty audio, foreign topic → the topic rule speaks first
    with pytest.raises(TopicNotFound):
        transcribe(store, speech, ALICE, bob_ref, b"", "text/plain")
    # own topic, no language, empty audio → the language speaks before the audio
    with pytest.raises(NoLanguage):
        transcribe(store, speech, ALICE, own, b"", "text/plain")
    assert speech.calls == []
