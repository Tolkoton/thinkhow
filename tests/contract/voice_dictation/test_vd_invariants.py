"""Contract tests of voice-dictation: the invariants I1-I4 (I5 waits on Q1, in its own disputed file)."""

import base64
from pathlib import Path

import httpx
import pytest
from vd_fakes import (
    ALICE,
    AUDIO,
    BOB,
    H_ALICE,
    H_BOB,
    HERE,
    Clock,
    FakeGenai,
    LogCapture,
    RecordingSpeech,
    Sleeps,
    api_error,
    cfg_get,
    install_log_capture,
    make_app,
    new_topic,
    run_node_test,
    voice_url,
)

from thinkhow.platform.speech import GeminiSpeech, SpeechUnavailable
from thinkhow.workspace import LANGUAGES, set_language

TYPES = (
    "audio/webm;codecs=opus",
    "AUDIO/WebM; codecs=opus",
    "audio/mp4",
    "Audio/MP4;codecs=opus",
    "audio/ogg",
    "audio/webm",
)
BODIES = (b"\x00", AUDIO, bytes(range(256)) * 4)


def test_I1_the_model_is_called_in_the_language_of_the_profile_only(tmp_path: Path) -> None:
    codes = [lang.code for lang in LANGUAGES]
    assert len(codes) == 85
    speech = RecordingSpeech()
    app = make_app(tmp_path, speech)
    ref = new_topic(app.storage, ALICE)

    # a refused request first (no language yet), then lawful ones
    refused = app.client.post(
        voice_url(ref), content=AUDIO, headers={**H_ALICE, "Content-Type": "audio/webm"}
    )
    assert refused.status_code == 409
    assert speech.calls == []

    for i, code in enumerate(codes):
        set_language(app.storage, ALICE, code)
        other = "de-DE" if code != "de-DE" else "pl-PL"
        mime = TYPES[i % len(TYPES)]
        body = BODIES[i % len(BODIES)]
        r = app.client.post(
            voice_url(ref),
            content=body,
            params={"language": other, "lang": other, "code": other},
            headers={**H_ALICE, "Content-Type": mime, "Accept-Language": other, "X-Language": other},
        )
        assert r.status_code == 200, (code, r.text)
        assert speech.calls[-1] == (body, mime, code), code
    assert len(speech.calls) == 85

    # two persons with two languages, interleaved, and a change of mind
    bob_ref = new_topic(app.storage, BOB, "Тема Боба")
    set_language(app.storage, BOB, "ja-JP")
    set_language(app.storage, ALICE, "uk-UA")
    for headers, url, expected in (
        (H_BOB, voice_url(bob_ref), "ja-JP"),
        (H_ALICE, voice_url(ref), "uk-UA"),
        (H_BOB, voice_url(bob_ref), "ja-JP"),
    ):
        r = app.client.post(url, content=AUDIO, headers={**headers, "Content-Type": "audio/mp4"})
        assert r.status_code == 200
        assert speech.calls[-1][2] == expected
    set_language(app.storage, ALICE, "cmn-Hans-CN")
    r = app.client.post(voice_url(ref), content=AUDIO, headers={**H_ALICE, "Content-Type": "audio/webm"})
    assert r.status_code == 200
    assert speech.calls[-1][2] == "cmn-Hans-CN"


def test_I2_gemini_passes_exactly_the_bytes_and_the_mime_it_got() -> None:
    cases = [
        (b"\x00", "audio/webm;codecs=opus"),
        (AUDIO, "audio/mp4"),
        (bytes(range(256)), "audio/mp4;codecs=opus"),
        (b"\xff" * 3000, "AUDIO/WebM; codecs=opus"),
        (b"RIFF....WAVEfmt ", "audio/ogg"),
        (b"a", "audio/webm"),
    ]
    for audio, mime in cases:
        client = FakeGenai([[]])
        speech = GeminiSpeech(client, "gemini-3.5-transcribe", 120.0, 3, sleep=Sleeps(), clock=Clock())
        speech.transcribe(audio, mime, "uk-UA")
        contents = client.calls[0]["contents"]
        assert len(contents) == 1, mime
        assert contents[0].inline_data.data == audio, mime
        assert contents[0].inline_data.mime_type == mime
    # the same bytes reach the model again on a retry
    client = FakeGenai([api_error(503), "текст"])
    speech = GeminiSpeech(client, "gemini-3.5-transcribe", 120.0, 3, sleep=Sleeps(), clock=Clock())
    speech.transcribe(AUDIO, "audio/webm;codecs=opus", "uk-UA")
    for call in client.calls:
        assert call["contents"][0].inline_data.data == AUDIO
        assert call["contents"][0].inline_data.mime_type == "audio/webm;codecs=opus"
        assert cfg_get(cfg_get(call["config"], "audio_transcription_config"), "language_codes") == ["uk-UA"]


TEXT_MARKER = "MARKER-TEXT-7f3a"
AUDIO_MARKER = "AUDIO-MARK-91c2"
MARKED_AUDIO = b"\x1aE\xdf\xa3" + AUDIO_MARKER.encode() + b"\x00\x01" + AUDIO_MARKER.encode()


@pytest.fixture
def logs(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> LogCapture:
    return install_log_capture(monkeypatch, capsys)


def test_I3_the_journal_holds_neither_the_audio_nor_the_text(tmp_path: Path, logs: LogCapture) -> None:
    plans: list[tuple[list[object], int, int]] = [
        ([f"  {TEXT_MARKER} нову роботу  "], 200, 1),  # ok, first attempt
        ([api_error(429), TEXT_MARKER], 200, 1),  # ok after a retry
        ([api_error(400)], 502, 1),  # unavailable at once
        ([httpx.ReadTimeout("slow")] * 3, 502, 1),  # unavailable after every attempt
    ]
    seen = 0
    for plan, status, lines in plans:
        client = FakeGenai(list(plan))
        speech = GeminiSpeech(client, "gemini-3.5-transcribe", 120.0, 3, sleep=Sleeps(), clock=Clock())
        app = make_app(tmp_path / f"case{seen}", speech)
        set_language(app.storage, ALICE, "uk-UA")
        ref = new_topic(app.storage, ALICE)
        r = app.client.post(
            voice_url(ref), content=MARKED_AUDIO, headers={**H_ALICE, "Content-Type": "audio/webm"}
        )
        assert r.status_code == status
        if status == 200:
            assert TEXT_MARKER in r.json()["text"]  # the text went to the page, not the journal
        calls = logs.events("speech_call")
        assert len(calls) == seen + lines
        assert calls[-1]["outcome"] == ("ok" if status == 200 else "unavailable")
        seen += lines
    journal = logs.text()
    assert logs.events("http_request"), "no http_request line was captured: the check would see nothing"
    assert TEXT_MARKER not in journal
    assert AUDIO_MARKER not in journal
    assert MARKED_AUDIO.hex() not in journal
    assert base64.b64encode(MARKED_AUDIO).decode() not in journal
    # and directly, without the web layer: a SpeechUnavailable carries no audio either
    client = FakeGenai([api_error(400)])
    speech = GeminiSpeech(client, "gemini-3.5-transcribe", 120.0, 3, sleep=Sleeps(), clock=Clock())
    with pytest.raises(SpeechUnavailable):
        speech.transcribe(MARKED_AUDIO, "audio/webm", "uk-UA")
    assert AUDIO_MARKER not in logs.text()


def test_I4_the_recording_stays_until_text_came_whatever_the_refusals() -> None:
    run_node_test(
        HERE / "vd_recorder.test.mjs",
        "I4: the same recording is sent after any refusal, in any order and any number of times",
    )
