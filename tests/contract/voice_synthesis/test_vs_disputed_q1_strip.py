"""Disputed (Q1): `speak` hands the tts the text trimmed at the edges, not the text as it came."""

from pathlib import Path

from vs_fakes import ALICE

from thinkhow.platform.storage import LocalStorage
from thinkhow.platform.tts import ScriptedTts
from thinkhow.workspace import set_language, speak


def test_q1_speak_passes_the_trimmed_text_to_the_tts(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path / "data")
    set_language(store, ALICE, "uk-UA")
    tts = ScriptedTts()
    speak(store, tts, ALICE, "  Добрий день.\n ")
    assert tts.calls == [("Добрий день.", "uk-UA")]
