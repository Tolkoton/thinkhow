"""A dictated turn's text: own topic, the person's language, the speech model (F13; M3 workspace → speech).

The model also gets the topic's vocabulary — names and foreign words from the title and the latest turns —
so it writes a word the conversation already has the way it is written there (task 304). Writes nothing: the
text goes back to the page, and the person sends it as an ordinary turn.
"""

import re
import unicodedata
from collections import Counter
from collections.abc import Iterator

from thinkhow.access import CurrentUser
from thinkhow.platform.speech import Speech
from thinkhow.platform.storage import Storage
from thinkhow.workspace.conversation import Conversation
from thinkhow.workspace.model import TopicRef
from thinkhow.workspace.profile import language
from thinkhow.workspace.topics import _can_write, _read_conversation

RECENT_TURNS = 6
VOCABULARY_SIZE = 100
WORD = re.compile(r"\w+(?:[-'’]\w+)*")
OPENERS = " \t«\"„“'(-—–*•"
SENTENCE_ENDS = ".!?…\n"


def transcribe(
    storage: Storage, speech: Speech, user: CurrentUser, ref: TopicRef, audio: bytes, mime: str
) -> str:
    """Flow: the write rule → the conversation → the person's language → the audio is something → model."""
    _can_write(user, ref)
    conv = _read_conversation(storage, ref)
    code = language(storage, user).code
    _check_audio(audio, mime)
    return speech.transcribe(audio, mime, code, vocabulary(conv))


def vocabulary(conv: Conversation) -> list[str]:
    """Flow: the latest turns newest first, then the title → their name-like words, each once, capped."""
    texts = [turn.text for session in conv.sessions for turn in session.turns][-RECENT_TURNS:][::-1]
    texts.append(conv.title)
    main = _main_script(texts)
    words = dict.fromkeys(w for text in texts for w in _name_like(text, main))
    return list(words)[:VOCABULARY_SIZE]


def _name_like(text: str, main: str | None) -> Iterator[str]:
    """Words in another script than the conversation's; words with a capital where no sentence starts."""
    for match in WORD.finditer(text):
        word = match.group()
        if len(word) < 2 or not any(c.isalpha() for c in word):
            continue
        if _script(word) != main or any(c.isupper() for c in word[1:]):
            yield word
        elif word[0].isupper() and not _starts_sentence(text, match.start()):
            yield word


def _starts_sentence(text: str, at: int) -> bool:
    before = text[:at].rstrip(OPENERS)
    return not before or before[-1] in SENTENCE_ENDS


def _main_script(texts: list[str]) -> str | None:
    """The script most words are in — by words, so a few long names do not outvote short common words."""
    words = (m.group() for text in texts for m in WORD.finditer(text))
    counts = Counter(_script(w) for w in words if any(c.isalpha() for c in w))
    return counts.most_common(1)[0][0] if counts else None


def _script(word: str) -> str:
    return _letter_script(next(c for c in word if c.isalpha()))


def _letter_script(letter: str) -> str:
    """LATIN, CYRILLIC, GREEK… — the first word of the letter's Unicode name."""
    return unicodedata.name(letter, "UNKNOWN").split(" ")[0]


def _check_audio(audio: bytes, mime: str) -> None:
    """Something was recorded, and it says it is audio; the type itself goes to the model as it came."""
    if not audio:
        raise ValueError("an empty recording")
    if not mime.split(";")[0].strip().lower().startswith("audio/"):
        raise ValueError(f"not an audio type: {mime!r}")
