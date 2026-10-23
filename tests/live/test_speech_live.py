"""F13 voice-dictation, live: the speech model as the product builds it (Seam 10), on Vertex `eu` (`-m live`).

Recordings from the spike: `uk-short.webm` (real Chromium, 64 kbit/s), `uk-short.m4a` (AAC, Safari's type).
"""

import os
import time
from pathlib import Path

import pytest

from thinkhow.platform.config import load_settings
from thinkhow.platform.speech import GeminiSpeech, Speech, SpeechUnavailable, make_speech
from thinkhow.workspace import LANGUAGES

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "voice"
WORDS = ("нову роботу", "зарплата", "друзів")


def product_speech() -> Speech:
    settings = load_settings(
        {
            **os.environ,
            "THINKHOW_LOCAL": "false",
            "THINKHOW_USERS_BUCKET": "-",
            "THINKHOW_SYSTEM_BUCKET": "-",
            "THINKHOW_OWNER_EMAIL": "-",
        }
    )
    assert (settings.speech_model, settings.location) == ("gemini-3.5-transcribe", "eu")
    speech = make_speech(settings)
    assert isinstance(speech, GeminiSpeech)
    return speech


@pytest.mark.live
@pytest.mark.parametrize(
    ("name", "mime"), [("uk-short.webm", "audio/webm;codecs=opus"), ("uk-short.m4a", "audio/mp4")]
)
def test_the_eu_model_writes_down_ukrainian_in_the_pinned_language(name: str, mime: str) -> None:
    speech = product_speech()
    started = time.monotonic()
    text = speech.transcribe((FIXTURES / name).read_bytes(), mime, "uk-UA")
    print(f"{name}: {time.monotonic() - started:.2f} s → {text}")
    for word in WORDS:
        assert word in text, (word, text)


@pytest.mark.live_codes
def test_an_invalid_code_is_refused_and_every_listed_code_is_reported() -> None:
    """Control first: an invalid code must fail, else accepting codes proves nothing. The 85 are a report."""
    speech = product_speech()
    audio = (FIXTURES / "uk-short.webm").read_bytes()
    with pytest.raises(SpeechUnavailable):
        speech.transcribe(audio, "audio/webm;codecs=opus", "xx-XX")
    refused = []
    for lang in LANGUAGES:
        try:
            speech.transcribe(audio, "audio/webm;codecs=opus", lang.code)
        except SpeechUnavailable:
            refused.append(lang.code)
    print(f"refused by the model: {refused or 'none'} of {len(LANGUAGES)}")
