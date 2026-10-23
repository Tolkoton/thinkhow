"""A dictated turn's text: own topic, the person's language, the speech model (F13; M3 workspace → speech).

Writes nothing: the text goes back to the page, and the person sends it as an ordinary turn.
"""

from thinkhow.access import CurrentUser
from thinkhow.platform.speech import Speech
from thinkhow.platform.storage import Storage
from thinkhow.workspace.model import TopicRef
from thinkhow.workspace.profile import language
from thinkhow.workspace.topics import _can_write, _read_conversation


def transcribe(
    storage: Storage, speech: Speech, user: CurrentUser, ref: TopicRef, audio: bytes, mime: str
) -> str:
    """Flow: the write rule of the topic → the person's language → the audio is something → the model."""
    _can_write(user, ref)
    _read_conversation(storage, ref)
    code = language(storage, user).code
    _check_audio(audio, mime)
    return speech.transcribe(audio, mime, code)


def _check_audio(audio: bytes, mime: str) -> None:
    """Something was recorded, and it says it is audio; the type itself goes to the model as it came."""
    if not audio:
        raise ValueError("an empty recording")
    if not mime.split(";")[0].strip().lower().startswith("audio/"):
        raise ValueError(f"not an audio type: {mime!r}")
