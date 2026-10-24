"""Voice → text in the person's language: gemini-3.5-transcribe on Vertex `eu`, a double locally (F13; M3 A2).

Retries the way platform.llm does (platform._retry); one `speech_call` log line per call, with neither the
audio, the text nor the vocabulary's words. The vocabulary (words the conversation already has, task 304) goes
as `custom_vocabulary`, which biases the model towards them. Does NOT store audio, choose the language or the
vocabulary, or know any person.
"""

import time
from collections.abc import Callable, Sequence
from typing import Any, Protocol

from google.genai import types

from thinkhow.platform._retry import backoff_s, retryable
from thinkhow.platform.config import Settings
from thinkhow.platform.log import log_event

LOCAL_TEXT = "(локальний режим) розпізнаний текст"


class SpeechUnavailable(Exception):
    """The model gave no text after the retries."""


class Speech(Protocol):
    def transcribe(self, audio: bytes, mime: str, language: str, vocabulary: Sequence[str] = ()) -> str: ...


class GeminiSpeech:
    def __init__(
        self,
        client: Any,
        model: str,
        timeout_s: float,
        attempts: int,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.client = client
        self.model = model
        self.timeout_s = timeout_s
        self.attempts = attempts
        self.sleep = sleep
        self.clock = clock

    def transcribe(self, audio: bytes, mime: str, language: str, vocabulary: Sequence[str] = ()) -> str:
        """Flow: try up to `attempts` times → the text of the answer; one log line either way."""
        started, attempts = self.clock(), 0
        try:
            for attempt in range(self.attempts):
                attempts = attempt + 1
                try:
                    response = self._call(audio, mime, language, vocabulary)
                except Exception as exc:
                    self._fail_or_wait(exc, attempt)
                    continue
                self._log(language, mime, len(audio), len(vocabulary), started, attempts, "ok")
                return _text(response)
            raise SpeechUnavailable("no attempt was allowed")
        except SpeechUnavailable:
            self._log(language, mime, len(audio), len(vocabulary), started, attempts, "unavailable")
            raise

    def _call(self, audio: bytes, mime: str, language: str, vocabulary: Sequence[str]) -> Any:
        """One request; the Part and the config are built here, so an SDK error counts as a failed attempt."""
        config = types.GenerateContentConfig(
            audio_transcription_config=types.AudioTranscriptionConfig(
                language_codes=[language], custom_vocabulary=list(vocabulary) or None
            ),
            http_options=types.HttpOptions(timeout=int(self.timeout_s * 1000)),
        )
        part = types.Part.from_bytes(data=audio, mime_type=mime)
        return self.client.models.generate_content(model=self.model, contents=[part], config=config)

    def _fail_or_wait(self, exc: Exception, attempt: int) -> None:
        if not retryable(exc) or attempt + 1 >= self.attempts:
            raise SpeechUnavailable(f"the speech model gave no text: {type(exc).__name__}") from exc
        self.sleep(backoff_s(attempt))

    def _log(
        self, language: str, mime: str, size: int, words: int, started: float, attempts: int, outcome: str
    ) -> None:
        log_event(
            "speech_call",
            severity="INFO" if outcome == "ok" else "WARNING",
            model=self.model,
            language=language,
            mime=mime,
            bytes=size,
            vocabulary=words,
            latency_ms=int((self.clock() - started) * 1000),
            attempts=attempts,
            outcome=outcome,
        )


def _text(response: Any) -> str:
    """The answer's text parts joined, thought parts left out, trimmed."""
    parts = []
    for candidate in response.candidates or []:
        for part in (candidate.content.parts if candidate.content else None) or []:
            if part.text and not part.thought:
                parts.append(part.text)
    return "".join(parts).strip()


class ScriptedSpeech:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[tuple[int, str, str]] = []

    def transcribe(self, audio: bytes, mime: str, language: str, vocabulary: Sequence[str] = ()) -> str:
        self.calls.append((len(audio), mime, language))
        return self.text


def make_speech(settings: Settings) -> Speech:
    if settings.local:
        return ScriptedSpeech(LOCAL_TEXT)
    from google import genai

    client = genai.Client(vertexai=True, project=settings.project, location=settings.location)
    return GeminiSpeech(client, settings.speech_model, settings.speech_timeout_s, settings.llm_attempts)
