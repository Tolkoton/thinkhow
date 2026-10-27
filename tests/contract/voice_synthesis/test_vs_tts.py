"""Contract tests of voice-synthesis: platform.tts and platform._retry (Seams 1, 2, 3, 5a)."""

from pathlib import Path
from typing import Any

import httpx
import pytest
from vs_fakes import (
    MP3,
    URL,
    FakePost,
    Sleeps,
    Tokens,
    auth_error,
    cloud,
    header,
    install_log_capture,
    ok,
)

from thinkhow.platform._retry import retryable
from thinkhow.platform.config import load_settings
from thinkhow.platform.tts import (
    SILENCE_MP3,
    CloudTts,
    NoVoice,
    ScriptedTts,
    TtsUnavailable,
    Voice,
    make_tts,
    voice_for,
)

# --- voice_for ----------------------------------------------------------------------------------


def test_voice_for_chirp3_language_gives_the_chirp3_voice() -> None:
    assert voice_for("uk-UA") == Voice("uk-UA-Chirp3-HD-Kore", "uk-UA", None)


def test_voice_for_gemini_language_gives_kore_on_gemini_tts() -> None:
    assert voice_for("ka-GE") == Voice("Kore", "ka-GE", "gemini-2.5-flash-tts")


def test_voice_for_applies_the_alias_before_the_lookup() -> None:
    assert voice_for("cmn-Hans-CN") == Voice("cmn-CN-Chirp3-HD-Kore", "cmn-CN", None)


def test_voice_for_language_without_a_voice_is_none() -> None:
    assert voice_for("kk-KZ") is None
    assert voice_for("xx-XX") is None


def test_voice_for_uses_the_given_voice_name() -> None:
    assert voice_for("uk-UA", "Puck") == Voice("uk-UA-Chirp3-HD-Puck", "uk-UA", None)
    assert voice_for("ka-GE", "Puck") == Voice("Puck", "ka-GE", "gemini-2.5-flash-tts")


# --- Seam 1: the request body and the voice ------------------------------------------------------


def test_seam1_chirp3_request_body_without_model_name() -> None:
    post = FakePost([ok()])
    assert cloud(post).synthesize("Добрий день.", "uk-UA") == MP3
    assert len(post.calls) == 1
    assert post.calls[0]["url"] == URL
    assert post.calls[0]["json"] == {
        "input": {"text": "Добрий день."},
        "voice": {"languageCode": "uk-UA", "name": "uk-UA-Chirp3-HD-Kore"},
        "audioConfig": {"audioEncoding": "MP3"},
    }


def test_seam1_gemini_request_body_carries_model_name() -> None:
    post = FakePost([ok()])
    assert cloud(post).synthesize("გამარჯობა", "ka-GE") == MP3
    assert post.calls[0]["json"] == {
        "input": {"text": "გამარჯობა"},
        "voice": {"languageCode": "ka-GE", "name": "Kore", "modelName": "gemini-2.5-flash-tts"},
        "audioConfig": {"audioEncoding": "MP3"},
    }


def test_seam1_alias_code_goes_out_as_the_google_code() -> None:
    post = FakePost([ok()])
    cloud(post).synthesize("你好", "cmn-Hans-CN")
    voice = post.calls[0]["json"]["voice"]
    assert voice == {"languageCode": "cmn-CN", "name": "cmn-CN-Chirp3-HD-Kore"}


def test_seam1_no_voice_raises_novoice_without_any_request() -> None:
    post = FakePost([])
    with pytest.raises(NoVoice):
        cloud(post).synthesize("Сәлем", "kk-KZ")
    assert post.calls == []


def test_cloudtts_uses_its_voice_name_in_the_request() -> None:
    post = FakePost([ok()])
    cloud(post, voice_name="Puck").synthesize("Добрий день.", "uk-UA")
    assert post.calls[0]["json"]["voice"]["name"] == "uk-UA-Chirp3-HD-Puck"


def test_cloudtts_sends_the_adc_token_as_bearer() -> None:
    post = FakePost([ok()])
    cloud(post, token=Tokens("tok-xyz")).synthesize("Добрий день.", "uk-UA")
    assert header(post.calls[0]["headers"], "Authorization") == "Bearer tok-xyz"


def test_cloudtts_passes_its_timeout_to_post() -> None:
    post = FakePost([ok()])
    cloud(post).synthesize("Добрий день.", "uk-UA")
    assert post.calls[0]["timeout"] == 30.0


# --- Seam 2: retries on HTTP statuses ------------------------------------------------------------


def test_seam2_429_then_200_gives_mp3_and_attempts_2_in_the_log(monkeypatch: Any, capsys: Any) -> None:
    cap = install_log_capture(monkeypatch, capsys)
    post, sleeps = FakePost([429, ok()]), Sleeps()
    assert cloud(post, sleeps=sleeps).synthesize("Добрий день.", "uk-UA") == MP3
    assert len(post.calls) == 2
    assert len(sleeps.delays) == 1
    events = cap.events("tts_call")
    assert len(events) == 1
    assert events[0]["attempts"] == 2
    assert events[0]["outcome"] == "ok"


def test_seam2_400_is_unavailable_at_once_without_sleep() -> None:
    post, sleeps = FakePost([400, ok()]), Sleeps()
    with pytest.raises(TtsUnavailable):
        cloud(post, sleeps=sleeps).synthesize("Добрий день.", "uk-UA")
    assert len(post.calls) == 1
    assert sleeps.delays == []


def test_seam2_503_every_attempt_is_unavailable_after_attempts(monkeypatch: Any, capsys: Any) -> None:
    cap = install_log_capture(monkeypatch, capsys)
    post = FakePost([503, 503, 503])
    with pytest.raises(TtsUnavailable):
        cloud(post, attempts=3).synthesize("Добрий день.", "uk-UA")
    assert len(post.calls) == 3
    events = cap.events("tts_call")
    assert len(events) == 1
    assert events[0]["outcome"] == "unavailable"
    assert events[0]["attempts"] == 3


def test_seam2_timeout_is_retried() -> None:
    post = FakePost([httpx.ReadTimeout("slow"), ok()])
    assert cloud(post).synthesize("Добрий день.", "uk-UA") == MP3
    assert len(post.calls) == 2


def test_retryable_true_for_http_status_429_and_5xx() -> None:
    def status_error(code: int) -> httpx.HTTPStatusError:
        request = httpx.Request("POST", URL)
        return httpx.HTTPStatusError("x", request=request, response=httpx.Response(code, request=request))

    assert retryable(status_error(429)) is True
    assert retryable(status_error(500)) is True
    assert retryable(status_error(503)) is True


def test_retryable_keeps_its_old_answers() -> None:
    request = httpx.Request("POST", URL)
    assert retryable(httpx.ReadTimeout("slow")) is True
    assert retryable(ValueError("x")) is False
    assert retryable(httpx.ConnectError("refused")) is False
    assert not retryable(
        httpx.HTTPStatusError("x", request=request, response=httpx.Response(400, request=request))
    )


# --- Seam 3: the log line -------------------------------------------------------------------------


def test_seam3_one_tts_call_line_with_its_fields_on_success(monkeypatch: Any, capsys: Any) -> None:
    cap = install_log_capture(monkeypatch, capsys)
    text = "Добрий день, світе."
    cloud(FakePost([ok()])).synthesize(text, "uk-UA")
    events = cap.events("tts_call")
    assert len(events) == 1
    e = events[0]
    for key in ("voice", "model", "language", "chars", "bytes", "latency_ms", "attempts", "outcome"):
        assert key in e, key
    assert e["model"] == "chirp3-hd"
    assert e["language"] == "uk-UA"
    assert e["chars"] == 19
    assert e["bytes"] == 13
    assert e["attempts"] == 1
    assert e["outcome"] == "ok"


def test_seam3_gemini_voice_logs_the_model_name(monkeypatch: Any, capsys: Any) -> None:
    cap = install_log_capture(monkeypatch, capsys)
    cloud(FakePost([ok()])).synthesize("გამარჯობა", "ka-GE")
    events = cap.events("tts_call")
    assert len(events) == 1
    assert events[0]["model"] == "gemini-2.5-flash-tts"


# --- Seam 5a: everything after voice_for is TtsUnavailable ---------------------------------------


def test_seam5a_200_without_audio_content_is_unavailable() -> None:
    with pytest.raises(TtsUnavailable):
        cloud(FakePost([(200, {"something": "else"})])).synthesize("Добрий день.", "uk-UA")


def test_seam5a_audio_content_not_base64_is_unavailable() -> None:
    with pytest.raises(TtsUnavailable):
        cloud(FakePost([(200, {"audioContent": "a"})])).synthesize("Добрий день.", "uk-UA")


def test_seam5a_connect_error_is_unavailable() -> None:
    with pytest.raises(TtsUnavailable):
        cloud(FakePost([httpx.ConnectError("refused")] * 3)).synthesize("Добрий день.", "uk-UA")


def test_seam5a_token_error_is_unavailable() -> None:
    post = FakePost([ok(), ok(), ok()])
    with pytest.raises(TtsUnavailable):
        cloud(post, token=Tokens(fail=auth_error())).synthesize("Добрий день.", "uk-UA")


# --- the double and the factory ------------------------------------------------------------------


def test_scripted_tts_returns_its_audio_and_remembers_calls() -> None:
    tts = ScriptedTts(b"abc")
    assert tts.synthesize("Привіт", "uk-UA") == b"abc"
    assert tts.calls == [("Привіт", "uk-UA")]
    assert ScriptedTts().synthesize("Привіт", "uk-UA") == SILENCE_MP3


def test_scripted_tts_raises_novoice_by_the_same_table() -> None:
    with pytest.raises(NoVoice):
        ScriptedTts().synthesize("Сәлем", "kk-KZ")


def test_make_tts_local_gives_the_double(tmp_path: Path) -> None:
    settings = load_settings(
        {
            "THINKHOW_LOCAL": "true",
            "THINKHOW_LOCAL_DIR": str(tmp_path),
            "THINKHOW_OWNER_EMAIL": "o@example.com",
        }
    )
    assert isinstance(make_tts(settings), ScriptedTts)


def test_make_tts_outside_local_gives_cloud_tts() -> None:
    settings = load_settings(
        {
            "THINKHOW_USERS_BUCKET": "users-b",
            "THINKHOW_SYSTEM_BUCKET": "system-b",
            "THINKHOW_OWNER_EMAIL": "o@example.com",
        }
    )
    assert isinstance(make_tts(settings), CloudTts)
