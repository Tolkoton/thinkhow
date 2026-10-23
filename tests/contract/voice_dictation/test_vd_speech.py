"""Contract tests of voice-dictation: platform.speech (Seams 1, 4, 8, 10), written from the contract."""

from pathlib import Path
from typing import Any

import httpx
import httpx2
import pytest
from google.genai import types
from vd_fakes import (
    AUDIO,
    Clock,
    FakeGenai,
    LogCapture,
    Sleeps,
    api_error,
    cfg_get,
    install_log_capture,
    response,
    text_part,
)

from thinkhow.platform.config import load_settings
from thinkhow.platform.speech import GeminiSpeech, ScriptedSpeech, SpeechUnavailable, make_speech

REPO = Path(__file__).resolve().parents[3]
CARDS = REPO / "cards"
WEBM = "audio/webm;codecs=opus"
CLOUD = {
    "THINKHOW_LOCAL": "false",
    "THINKHOW_USERS_BUCKET": "users-b",
    "THINKHOW_SYSTEM_BUCKET": "system-b",
    "THINKHOW_OWNER_EMAIL": "owner@example.com",
}


def gemini(
    plan: list[Any], attempts: int = 3, timeout_s: float = 120.0
) -> tuple[GeminiSpeech, FakeGenai, Sleeps]:
    client = FakeGenai(plan)
    sleeps = Sleeps()
    speech = GeminiSpeech(client, "gemini-3.5-transcribe", timeout_s, attempts, sleep=sleeps, clock=Clock())
    return speech, client, sleeps


@pytest.fixture
def logs(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> LogCapture:
    return install_log_capture(monkeypatch, capsys)


# --- Seam 1 -------------------------------------------------------------------------------------


def test_seam1_gemini_sends_model_bytes_mime_language_and_timeout_as_given(logs: LogCapture) -> None:
    speech, client, _ = gemini(["Привіт"], timeout_s=12.5)
    assert speech.transcribe(AUDIO, WEBM, "uk-UA") == "Привіт"
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["model"] == "gemini-3.5-transcribe"
    contents = call["contents"]
    assert isinstance(contents, list) and len(contents) == 1
    part = contents[0]
    assert part.inline_data.data == AUDIO
    assert part.inline_data.mime_type == "audio/webm;codecs=opus"
    config = call["config"]
    atc = cfg_get(config, "audio_transcription_config")
    assert cfg_get(atc, "language_codes") == ["uk-UA"]
    assert not cfg_get(atc, "language_auto")
    assert cfg_get(cfg_get(config, "http_options"), "timeout") == 12500


def test_seam1_text_is_the_joined_parts_without_thought_trimmed(logs: LogCapture) -> None:
    reply = response(
        text_part("  Привіт, "), text_part("секретна думка", thought=True), text_part("світе.  ")
    )
    speech, _, _ = gemini([reply])
    assert speech.transcribe(AUDIO, WEBM, "uk-UA") == "Привіт, світе."


def test_seam1_empty_or_blank_model_text_is_an_empty_string(logs: LogCapture) -> None:
    for blank in ("", "   ", " \n\t "):
        speech, _, _ = gemini([[text_part(blank)]])
        assert speech.transcribe(AUDIO, WEBM, "uk-UA") == ""


# --- Seam 4 -------------------------------------------------------------------------------------


def test_seam4_429_then_text_returns_text_after_two_attempts_one_log_line(logs: LogCapture) -> None:
    speech, client, sleeps = gemini([api_error(429), "нову роботу"])
    assert speech.transcribe(AUDIO, WEBM, "pl-PL") == "нову роботу"
    assert len(client.calls) == 2
    assert len(sleeps.delays) == 1
    lines = logs.events("speech_call")
    assert len(lines) == 1
    line = lines[0]
    assert line["model"] == "gemini-3.5-transcribe"
    assert line["language"] == "pl-PL"
    assert line["mime"] == WEBM
    assert line["bytes"] == len(AUDIO)
    assert line["attempts"] == 2
    assert line["outcome"] == "ok"
    assert isinstance(line["latency_ms"], (int, float)) and line["latency_ms"] >= 0


def test_seam4_a_5xx_is_retried_too(logs: LogCapture) -> None:
    speech, client, sleeps = gemini([api_error(503), api_error(500), "текст"])
    assert speech.transcribe(AUDIO, WEBM, "uk-UA") == "текст"
    assert len(client.calls) == 3
    assert len(sleeps.delays) == 2


def test_seam4_400_is_not_retried_and_is_unavailable_at_once(logs: LogCapture) -> None:
    speech, client, sleeps = gemini([api_error(400)])
    with pytest.raises(SpeechUnavailable):
        speech.transcribe(AUDIO, WEBM, "uk-UA")
    assert len(client.calls) == 1
    assert sleeps.delays == []
    lines = logs.events("speech_call")
    assert len(lines) == 1
    assert lines[0]["outcome"] == "unavailable"
    assert lines[0]["attempts"] == 1


def test_seam4_timeouts_take_exactly_attempts_calls_and_attempts_minus_one_sleeps(logs: LogCapture) -> None:
    for attempts in (1, 3, 4):
        for timeout in (httpx.ReadTimeout("slow"), httpx2.ReadTimeout("slow")):
            speech, client, sleeps = gemini([timeout] * attempts, attempts=attempts)
            with pytest.raises(SpeechUnavailable):
                speech.transcribe(AUDIO, WEBM, "uk-UA")
            assert len(client.calls) == attempts
            assert len(sleeps.delays) == attempts - 1
    last = logs.events("speech_call")[-1]
    assert last["outcome"] == "unavailable"
    assert last["attempts"] == 4


# --- Seam 8 -------------------------------------------------------------------------------------


class SdkBuildError(ValueError):
    """What a pydantic validation inside the SDK looks like: a ValueError."""


def test_seam8_sdk_error_while_building_the_part_is_speech_unavailable(
    logs: LogCapture, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args: Any, **kwargs: Any) -> Any:
        raise SdkBuildError("bad part")

    monkeypatch.setattr(types.Part, "from_bytes", boom)
    speech, _, _ = gemini(["не має дійти"])
    with pytest.raises(SpeechUnavailable):
        speech.transcribe(AUDIO, WEBM, "uk-UA")


def test_seam8_sdk_error_while_building_the_config_is_speech_unavailable(
    logs: LogCapture, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args: Any, **kwargs: Any) -> None:
        raise SdkBuildError("bad config")

    monkeypatch.setattr(types.GenerateContentConfig, "__init__", boom)
    speech, _, _ = gemini(["не має дійти"])
    with pytest.raises(SpeechUnavailable):
        speech.transcribe(AUDIO, WEBM, "uk-UA")


# --- ScriptedSpeech -----------------------------------------------------------------------------


def test_scripted_speech_returns_its_text_and_remembers_len_mime_language() -> None:
    double = ScriptedSpeech("заданий текст")
    assert double.transcribe(b"12345", "audio/mp4", "uk-UA") == "заданий текст"
    assert double.transcribe(b"", "AUDIO/WebM; codecs=opus", "ja-JP") == "заданий текст"
    assert double.calls == [(5, "audio/mp4", "uk-UA"), (0, "AUDIO/WebM; codecs=opus", "ja-JP")]


# --- Seam 10 ------------------------------------------------------------------------------------


def test_seam10_make_speech_local_is_scripted_with_local_text(tmp_path: Path) -> None:
    settings = load_settings({"THINKHOW_LOCAL": "true", "THINKHOW_LOCAL_DIR": str(tmp_path)})
    speech = make_speech(settings)
    assert isinstance(speech, ScriptedSpeech)
    assert speech.transcribe(AUDIO, WEBM, "uk-UA") == "(локальний режим) розпізнаний текст"


class ClientFactory:
    def __init__(self, plan: list[Any]) -> None:
        self.plan = plan
        self.made: list[FakeGenai] = []

    def __call__(self, *args: Any, **kwargs: Any) -> FakeGenai:
        assert not args, f"genai.Client got positional arguments: {args!r}"
        client = FakeGenai(list(self.plan), **kwargs)
        self.made.append(client)
        return client


def test_seam10_make_speech_outside_local_is_gemini_with_speech_model_timeout_and_eu(
    monkeypatch: pytest.MonkeyPatch, logs: LogCapture
) -> None:
    factory = ClientFactory(["текст"])
    monkeypatch.setattr("google.genai.Client", factory)
    settings = load_settings(CLOUD)
    speech = make_speech(settings)
    assert isinstance(speech, GeminiSpeech)
    assert len(factory.made) == 1
    kwargs = factory.made[0].kwargs
    assert kwargs.get("vertexai") is True
    assert kwargs.get("project") == settings.project
    assert kwargs.get("location") == "eu"
    assert speech.transcribe(AUDIO, WEBM, "uk-UA") == "текст"
    call = factory.made[0].calls[0]
    assert call["model"] == "gemini-3.5-transcribe"
    assert cfg_get(cfg_get(call["config"], "http_options"), "timeout") == 120000


def test_seam10_speech_model_and_timeout_come_from_their_own_variables(
    monkeypatch: pytest.MonkeyPatch, logs: LogCapture
) -> None:
    factory = ClientFactory(["текст"])
    monkeypatch.setattr("google.genai.Client", factory)
    settings = load_settings(
        {
            **CLOUD,
            "THINKHOW_SPEECH_MODEL": "gemini-test-stt",
            "THINKHOW_SPEECH_TIMEOUT_S": "7.5",
            "THINKHOW_MODEL": "gemini-facilitator",
            "THINKHOW_LLM_TIMEOUT_S": "300",
            "THINKHOW_LOCATION": "europe-west4",
        }
    )
    speech = make_speech(settings)
    assert factory.made[0].kwargs.get("location") == "europe-west4"
    assert speech.transcribe(AUDIO, WEBM, "uk-UA") == "текст"
    call = factory.made[0].calls[0]
    assert call["model"] == "gemini-test-stt"
    assert cfg_get(cfg_get(call["config"], "http_options"), "timeout") == 7500


def test_seam10_build_deps_outside_local_puts_gemini_speech_into_deps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, logs: LogCapture
) -> None:
    from thinkhow import knowledge
    from thinkhow.platform.storage import LocalStorage
    from thinkhow.web import app as web_app

    store = LocalStorage(tmp_path / "data")
    knowledge.seed(store, CARDS)
    monkeypatch.setattr(web_app, "make_storage", lambda settings: store)
    monkeypatch.setattr("google.genai.Client", ClientFactory([]))
    deps = web_app.build_deps(CLOUD, CARDS)
    assert isinstance(deps.speech, GeminiSpeech)


def test_seam10_build_deps_in_local_mode_puts_the_scripted_speech(tmp_path: Path) -> None:
    from thinkhow.web.app import build_deps

    environ = {
        "THINKHOW_LOCAL": "true",
        "THINKHOW_LOCAL_DIR": str(tmp_path),
        "THINKHOW_OWNER_EMAIL": "owner@example.com",
    }
    deps = build_deps(environ, CARDS)
    assert isinstance(deps.speech, ScriptedSpeech)
    assert deps.speech.transcribe(AUDIO, WEBM, "uk-UA") == "(локальний режим) розпізнаний текст"
