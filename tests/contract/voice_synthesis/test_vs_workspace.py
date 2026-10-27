"""Contract tests of voice-synthesis: workspace.speak and workspace.has_voice (Seam 4), from the contract."""

from pathlib import Path

import pytest
from vs_fakes import ALICE, snapshot

from thinkhow.platform.storage import LocalStorage
from thinkhow.platform.tts import NoVoice, ScriptedTts
from thinkhow.workspace import MAX_SPEAK_BYTES, NoLanguage, has_voice, set_language, speak


def _store(tmp_path: Path, code: str | None = "uk-UA") -> LocalStorage:
    store = LocalStorage(tmp_path / "data")
    if code is not None:
        set_language(store, ALICE, code)
    return store


def test_speak_synthesizes_the_text_in_the_persons_language(tmp_path: Path) -> None:
    store = _store(tmp_path, "pl-PL")
    tts = ScriptedTts(b"mp3!")
    assert speak(store, tts, ALICE, "Dzień dobry.") == b"mp3!"
    assert tts.calls == [("Dzień dobry.", "pl-PL")]


def test_speak_without_a_language_raises_nolanguage(tmp_path: Path) -> None:
    store = _store(tmp_path, None)
    tts = ScriptedTts()
    with pytest.raises(NoLanguage):
        speak(store, tts, ALICE, "Добрий день.")
    assert tts.calls == []


def test_speak_empty_or_blank_text_is_valueerror(tmp_path: Path) -> None:
    store = _store(tmp_path)
    tts = ScriptedTts()
    with pytest.raises(ValueError):
        speak(store, tts, ALICE, "")
    with pytest.raises(ValueError):
        speak(store, tts, ALICE, "   \n\t ")
    assert tts.calls == []


def test_seam4_limit_is_4000_utf8_bytes_not_characters(tmp_path: Path) -> None:
    assert MAX_SPEAK_BYTES == 4000
    store = _store(tmp_path)
    tts = ScriptedTts(b"mp3!")
    assert speak(store, tts, ALICE, "ж" * 2000) == b"mp3!"
    with pytest.raises(ValueError):
        speak(store, tts, ALICE, "ж" * 2001)
    assert len(tts.calls) == 1


def test_speak_language_without_voice_raises_novoice(tmp_path: Path) -> None:
    store = _store(tmp_path, "kk-KZ")
    with pytest.raises(NoVoice):
        speak(store, ScriptedTts(), ALICE, "Сәлем")


def test_speak_writes_nothing(tmp_path: Path) -> None:
    store = _store(tmp_path)
    before = snapshot(tmp_path / "data")
    speak(store, ScriptedTts(), ALICE, "Добрий день.")
    assert snapshot(tmp_path / "data") == before


def test_has_voice_by_the_persons_language(tmp_path: Path) -> None:
    assert has_voice(_store(tmp_path / "a", "uk-UA"), ALICE) is True
    assert has_voice(_store(tmp_path / "b", "ka-GE"), ALICE) is True
    assert has_voice(_store(tmp_path / "c", "kk-KZ"), ALICE) is False
