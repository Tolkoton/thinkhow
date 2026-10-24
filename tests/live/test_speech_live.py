"""F13 voice-dictation, live: the speech model as the product builds it (Seam 10), on Vertex `eu` (`-m live`).

Recordings from the spike: `uk-short.webm` (real Chromium, 64 kbit/s), `uk-short.m4a` (AAC, Safari's type);
`uk-names.webm` (task 304, below).
"""

import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import pytest

from thinkhow.platform.config import load_settings
from thinkhow.platform.speech import GeminiSpeech, Speech, SpeechUnavailable, make_speech
from thinkhow.workspace import LANGUAGES
from thinkhow.workspace import conversation as conv_file
from thinkhow.workspace.voice import vocabulary

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


# Task 304: `uk-names.webm` — Gemini TTS saying «Я шукаю клієнтів серед фірм Меттлі-Штанд у Шварцвальд, а не
# на Апворк.» (names spelt as an accented speaker says them; spike `voice-context-2026-10-24`).
NAMES = ("Mittelstand", "Schwarzwald", "Upwork")
TURNS: list[tuple[Literal["user", "model"], str]] = [
    ("user", "Я думаю, що мені треба йти не на біржі фрилансу, а прямо до компаній."),
    (
        "model",
        "Ви згадали, що Upwork дає лише дрібні замовлення. Кого саме ви хочете досягти — "
        "Mittelstand, тобто сімейних середніх фірм, чи великих концернів?",
    ),
    ("user", "Скоріше середніх, у регіонах, де я вже бував, Баден-Вюртемберг, Schwarzwald."),
    ("model", "Що для таких фірм у Schwarzwald могло б бути цінним: SEO, сайт чи щось інше?"),
]
CONTEXT = conv_file.Conversation(
    "Як знайти перших клієнтів у Німеччині",
    [
        conv_file.SessionDoc(
            no=1,
            turns=[
                conv_file.Turn(no=n + 1, role=role, at=datetime(2026, 10, 24, 12, n, tzinfo=UTC), text=text)
                for n, (role, text) in enumerate(TURNS)
            ],
        )
    ],
)


@pytest.mark.live
def test_with_the_conversation_vocabulary_the_names_come_out_as_written() -> None:
    speech = product_speech()
    audio = (FIXTURES / "uk-names.webm").read_bytes()
    words = vocabulary(CONTEXT)
    results = {}
    for label, vocab in (("without context", ()), ("with context", tuple(words))):
        started = time.monotonic()
        text = speech.transcribe(audio, "audio/webm;codecs=opus", "uk-UA", vocab)
        results[label] = text
        print(f"{label}: {time.monotonic() - started:.2f} s → {text}")
    print(f"vocabulary: {words}")
    for name in NAMES:
        assert name in results["with context"], (name, results["with context"])
