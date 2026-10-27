"""voice-synthesis, live: the synthesis as the product builds it (`make_tts`), Cloud TTS on `eu` (`-m live`).

`uk-UA` goes to a Chirp 3 HD voice, `ka-GE` to Gemini-TTS; each must come back as MP3 bytes.
"""

import os
import time

import pytest

from thinkhow.platform.config import load_settings
from thinkhow.platform.tts import CloudTts, Tts, make_tts

TEXTS = {
    "uk-UA": "Добре, тоді почнімо з того, що для вас зараз найважливіше.",
    "ka-GE": "კარგი, დავიწყოთ იმით, რაც ახლა თქვენთვის ყველაზე მნიშვნელოვანია.",
}


def product_tts() -> Tts:
    settings = load_settings(
        {
            **os.environ,
            "THINKHOW_LOCAL": "false",
            "THINKHOW_USERS_BUCKET": "-",
            "THINKHOW_SYSTEM_BUCKET": "-",
            "THINKHOW_OWNER_EMAIL": "-",
        }
    )
    assert settings.tts_endpoint == "https://eu-texttospeech.googleapis.com"
    tts = make_tts(settings)
    assert isinstance(tts, CloudTts)
    return tts


def is_mp3(audio: bytes) -> bool:
    return audio[:3] == b"ID3" or (len(audio) > 1 and audio[0] == 0xFF and audio[1] & 0xE0 == 0xE0)


@pytest.mark.live
@pytest.mark.parametrize("language", sorted(TEXTS))
def test_make_tts_speaks_the_language_as_mp3_on_eu(language: str) -> None:
    tts = product_tts()
    started = time.monotonic()
    audio = tts.synthesize(TEXTS[language], language)
    print(f"{language}: {len(audio)} bytes in {time.monotonic() - started:.2f} s")
    assert is_mp3(audio)
    assert len(audio) > 5000
