"""A reply sentence as speech in the person's language (task 308; workspace → tts). Writes nothing."""

from thinkhow.access import CurrentUser
from thinkhow.platform.storage import Storage
from thinkhow.platform.tts import Tts, voice_for
from thinkhow.workspace.profile import language

MAX_SPEAK_BYTES = 4000  # the smaller of Cloud TTS's limits (Gemini-TTS); a constant, one line to change


def speak(storage: Storage, tts: Tts, user: CurrentUser, text: str) -> bytes:
    """Flow: the person's language → the text is something and within the limit → the voice."""
    code = language(storage, user).code
    clean = text.strip()
    if not clean:
        raise ValueError("an empty text is not spoken")
    if len(clean.encode("utf-8")) > MAX_SPEAK_BYTES:
        raise ValueError("the text is over the synthesis limit")
    return tts.synthesize(clean, code)


def has_voice(storage: Storage, user: CurrentUser) -> bool:
    return voice_for(language(storage, user).code) is not None
