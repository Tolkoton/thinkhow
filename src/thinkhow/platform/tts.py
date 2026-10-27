"""Text → speech in the person's language: Cloud Text-to-Speech on the `eu` endpoint, a double locally (308).

Chirp 3 HD voices where Google has one for the language, Gemini-TTS for 21 more, none for the rest (the spike
`.engine/artifacts/spikes/voice-conversation-2026-10-27/`). One `tts_call` log line per call, no text.
Does NOT store audio, cut text into sentences, cache, or know any person or topic.
"""

import base64
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import httpx

from thinkhow.platform._retry import backoff_s, retryable
from thinkhow.platform.config import Settings
from thinkhow.platform.log import log_event

SILENCE_MP3 = (Path(__file__).with_name("silence.mp3")).read_bytes()
GEMINI_MODEL = "gemini-2.5-flash-tts"
SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
# The spike's tables (voices.out, gemini_langs.out): the profile's codes as Google names them for a voice.
ALIASES = {"cmn-Hans-CN": "cmn-CN", "yue-Hant-HK": "yue-HK", "pa-Guru-IN": "pa-IN"}
CHIRP3 = frozenset(
    "cs-CZ da-DK de-DE et-EE en-AU en-IN en-GB en-US es-ES es-US fr-CA fr-FR hr-HR id-ID it-IT sw-KE lv-LV "
    "lt-LT hu-HU nl-NL nb-NO pl-PL pt-BR ro-RO sk-SK sl-SI fi-FI sv-SE vi-VN tr-TR el-GR bg-BG sr-RS uk-UA "
    "he-IL mr-IN hi-IN bn-IN pa-IN gu-IN te-IN kn-IN ml-IN th-TH ko-KR ja-JP cmn-CN yue-HK".split()
)
GEMINI = frozenset(
    "af-ZA az-AZ ca-ES es-419 fil-PH gl-ES is-IS ms-MY pt-PT be-BY mk-MK mn-MN hy-AM ar-EG fa-IR ne-NP bn-BD "
    "or-IN my-MM ka-GE am-ET".split()
)


class TtsUnavailable(Exception):
    """The synthesis gave no audio after the retries."""


class NoVoice(Exception):
    """Google has no voice for this language."""


@dataclass(frozen=True)
class Voice:
    name: str
    language: str
    model: str | None


def voice_for(code: str, name: str = "Kore") -> Voice | None:
    """Flow: the alias of the code → a Chirp 3 HD voice, else Gemini-TTS, else none."""
    code = ALIASES.get(code, code)
    if code in CHIRP3:
        return Voice(f"{code}-Chirp3-HD-{name}", code, None)
    if code in GEMINI:
        return Voice(name, code, GEMINI_MODEL)
    return None


class Tts(Protocol):
    def synthesize(self, text: str, language: str) -> bytes: ...


class CloudTts:
    def __init__(
        self,
        post: Callable[..., Any],
        token: Callable[[], str],
        endpoint: str,
        voice_name: str,
        timeout_s: float,
        attempts: int,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.post = post
        self.token = token
        self.endpoint = endpoint
        self.voice_name = voice_name
        self.timeout_s = timeout_s
        self.attempts = attempts
        self.sleep = sleep
        self.clock = clock

    def synthesize(self, text: str, language: str) -> bytes:
        """Flow: the voice (none → NoVoice, no request) → up to `attempts` requests → MP3; one log line."""
        voice = voice_for(language, self.voice_name)
        if voice is None:
            raise NoVoice(language)
        started, attempts = self.clock(), 0
        try:
            for attempt in range(self.attempts):
                attempts = attempt + 1
                try:
                    audio = self._call(text, voice)
                except Exception as exc:
                    self._fail_or_wait(exc, attempt)
                    continue
                self._log(voice, len(text), len(audio), started, attempts, "ok")
                return audio
            raise TtsUnavailable("no attempt was allowed")
        except TtsUnavailable:
            self._log(voice, len(text), 0, started, attempts, "unavailable")
            raise

    def _call(self, text: str, voice: Voice) -> bytes:
        """One request; the token, the JSON and its base64 are read here, so any failure is an attempt's."""
        body_voice: dict[str, str] = {"languageCode": voice.language, "name": voice.name}
        if voice.model:
            body_voice["modelName"] = voice.model
        body = {"input": {"text": text}, "voice": body_voice, "audioConfig": {"audioEncoding": "MP3"}}
        headers = {"Authorization": f"Bearer {self.token()}"}
        url = f"{self.endpoint}/v1/text:synthesize"
        response = self.post(url, headers=headers, json=body, timeout=self.timeout_s)
        response.raise_for_status()
        return base64.b64decode(response.json()["audioContent"], validate=True)

    def _fail_or_wait(self, exc: Exception, attempt: int) -> None:
        if not retryable(exc) or attempt + 1 >= self.attempts:
            raise TtsUnavailable(f"the synthesis gave no audio: {type(exc).__name__}") from exc
        self.sleep(backoff_s(attempt))

    def _log(self, voice: Voice, chars: int, size: int, started: float, attempts: int, outcome: str) -> None:
        log_event(
            "tts_call",
            severity="INFO" if outcome == "ok" else "WARNING",
            voice=voice.name,
            model=voice.model or "chirp3-hd",
            language=voice.language,
            chars=chars,
            bytes=size,
            latency_ms=int((self.clock() - started) * 1000),
            attempts=attempts,
            outcome=outcome,
        )


class ScriptedTts:
    def __init__(self, audio: bytes = SILENCE_MP3) -> None:
        self.audio = audio
        self.calls: list[tuple[str, str]] = []

    def synthesize(self, text: str, language: str) -> bytes:
        if voice_for(language) is None:
            raise NoVoice(language)
        self.calls.append((text, language))
        return self.audio


def make_tts(settings: Settings) -> Tts:
    if settings.local:
        return ScriptedTts()
    return CloudTts(
        httpx.post,
        adc_token(),
        settings.tts_endpoint,
        settings.tts_voice,
        settings.tts_timeout_s,
        settings.llm_attempts,
    )


def adc_token() -> Callable[[], str]:
    """The ADC access token, refreshed when expired (Cloud Run: the metadata server; locally: gcloud ADC)."""
    import google.auth
    from google.auth.transport.requests import Request

    credentials: Any = None

    def token() -> str:
        nonlocal credentials
        if credentials is None:
            credentials, _ = google.auth.default(scopes=SCOPES)
        if not credentials.valid:
            credentials.refresh(Request())
        return str(credentials.token)

    return token
