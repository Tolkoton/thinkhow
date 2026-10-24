"""Task 304: the speech model hears the words of the conversation (title, latest turns) as a vocabulary.

The language from the profile stays the pin; the vocabulary goes in the config (`custom_vocabulary`), never as
text in the request, and the journal gets only its size.
"""

from __future__ import annotations

import io
import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from google.genai import types

from thinkhow.access import CurrentUser
from thinkhow.platform import log
from thinkhow.platform.speech import GeminiSpeech, ScriptedSpeech
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import TopicRef, create_topic, set_language, transcribe
from thinkhow.workspace import conversation as conv_file
from thinkhow.workspace.voice import RECENT_TURNS, VOCABULARY_SIZE, vocabulary

T0 = datetime(2026, 10, 24, 12, 0, 0, tzinfo=UTC)
ALICE = CurrentUser(id="alice-1", email="alice@example.com", is_owner=False)
AUDIO = b"\x1aE\xdf\xa3 webm"
WEBM = "audio/webm;codecs=opus"


def conv(title: str, *texts: str) -> conv_file.Conversation:
    turns = [
        conv_file.Turn(no=i + 1, role="user" if i % 2 == 0 else "model", at=T0 + timedelta(minutes=i), text=t)
        for i, t in enumerate(texts)
    ]
    return conv_file.Conversation(title, [conv_file.SessionDoc(no=1, turns=turns)])


# --- which words ---------------------------------------------------------------------------------


def test_names_in_another_script_and_mid_sentence_capitals_are_taken_common_words_are_not() -> None:
    words = vocabulary(
        conv(
            "Перші клієнти в Німеччині",
            "Я думаю йти не на біржі, а прямо до компаній.",
            "Upwork дає лише дрібні замовлення. Ви маєте на увазі Mittelstand, сімейні фірми?",
            "Так, у регіонах, де я бував: Баден-Вюртемберг, Schwarzwald. Їм потрібне SEO.",
        )
    )
    assert {"Upwork", "Mittelstand", "Schwarzwald", "SEO", "Баден-Вюртемберг", "Німеччині"} <= set(words)
    for common in ("Перші", "клієнти", "Я", "думаю", "Так", "Ви", "Їм", "дрібні", "регіонах"):
        assert common not in words, common


def test_a_same_script_name_only_at_a_sentence_start_is_not_taken_it_is_where_it_stands_mid_sentence() -> (
    None
):
    """A capital that starts a sentence says nothing: such a name counts only where it stands mid-sentence."""
    assert vocabulary(conv("Тема", "Київ — гарне місто. Львів теж.")) == []
    assert vocabulary(conv("Тема", "Київ — гарне місто. Я жив у Києві.")) == ["Києві"]


def test_lower_case_words_of_another_script_are_taken_too() -> None:
    words = vocabulary(conv("Робота", "Мені потрібен pitch deck і трохи networking."))
    assert {"pitch", "deck", "networking"} <= set(words)


def test_in_a_latin_conversation_latin_words_are_common_and_only_names_count() -> None:
    words = vocabulary(conv("Neue Kunden", "Ich suche Kunden im Mittelstand, nicht auf Upwork.", "Wo genau?"))
    assert {"Mittelstand", "Upwork", "Kunden"} <= set(words)
    for common in ("Ich", "suche", "nicht", "Wo", "genau", "Neue"):
        assert common not in words, common


def test_newest_turns_first_each_word_once_title_counts_and_only_the_latest_turns_are_read() -> None:
    old = [f"Старе {i}: Alpha{i}." for i in range(4)]
    recent = [f"Нове: Beta{i}, і ще раз Beta{i}." for i in range(RECENT_TURNS)]
    words = vocabulary(conv("Тема про Gamma", *old, *recent))
    betas = [f"Beta{i}" for i in reversed(range(RECENT_TURNS))]
    assert words[: len(betas)] == betas
    assert "Gamma" in words
    assert not any(w.startswith("Alpha") for w in words)


def test_the_vocabulary_is_capped() -> None:
    many = " ".join(f"Name{i}" for i in range(VOCABULARY_SIZE + 50))
    words = vocabulary(conv("Тема", f"names: {many}"))
    assert len(words) == VOCABULARY_SIZE
    assert words[0] == "Name0"


def test_a_new_topic_gives_at_most_the_title_words() -> None:
    assert vocabulary(conv("Як знайти роботу")) == []
    assert vocabulary(conv("Робота в Berlin")) == ["Berlin"]


# --- workspace passes it -------------------------------------------------------------------------


class Remembering:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    def transcribe(self, audio: bytes, mime: str, language: str, vocabulary: Sequence[str] = ()) -> str:
        self.calls.append((language, tuple(vocabulary)))
        return "текст"


def test_workspace_sends_the_topic_vocabulary_with_the_profile_language(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path / "data")
    set_language(store, ALICE, "uk-UA")
    ref = TopicRef(ALICE.id, create_topic(store, ALICE, "Клієнти в Schwarzwald", T0))
    path = f"{ref.uid}/{ref.topic_id}/conversation.md"
    raw = store.read("users", path)
    assert raw is not None
    doc = conv_file.parse(raw.decode("utf-8"))
    doc.sessions[0].turns.append(conv_file.Turn(no=1, role="model", at=T0, text="А як щодо Mittelstand?"))
    store.write("users", path, conv_file.render(doc).encode("utf-8"), "text/markdown")
    speech = Remembering()
    assert transcribe(store, speech, ALICE, ref, AUDIO, WEBM) == "текст"
    assert speech.calls == [("uk-UA", ("Mittelstand", "Schwarzwald"))]


# --- platform sends it ---------------------------------------------------------------------------


class FakeModels:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def generate_content(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        part = types.Part(text="Mittelstand")
        return SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[part]))])


def gemini() -> tuple[GeminiSpeech, FakeModels]:
    models = FakeModels()
    speech = GeminiSpeech(
        SimpleNamespace(models=models), "gemini-3.5-transcribe", 120.0, 3, sleep=lambda s: None
    )
    return speech, models


def test_gemini_puts_the_vocabulary_in_the_config_and_the_audio_alone_in_contents() -> None:
    speech, models = gemini()
    assert speech.transcribe(AUDIO, WEBM, "uk-UA", vocabulary=("Mittelstand", "Upwork")) == "Mittelstand"
    call = models.calls[0]
    assert len(call["contents"]) == 1 and call["contents"][0].inline_data.data == AUDIO
    atc = call["config"].audio_transcription_config
    assert atc.language_codes == ["uk-UA"]
    assert atc.custom_vocabulary == ["Mittelstand", "Upwork"]


def test_gemini_without_a_vocabulary_sends_none() -> None:
    speech, models = gemini()
    speech.transcribe(AUDIO, WEBM, "uk-UA")
    assert models.calls[0]["config"].audio_transcription_config.custom_vocabulary is None


def test_the_journal_gets_the_vocabulary_size_not_its_words(monkeypatch: pytest.MonkeyPatch) -> None:
    journal = io.StringIO()
    monkeypatch.setattr(log.log_event, "__defaults__", (journal,))
    speech, _ = gemini()
    speech.transcribe(AUDIO, WEBM, "uk-UA", vocabulary=("SecretName42", "Upwork"))
    assert "SecretName42" not in journal.getvalue()
    line = json.loads(journal.getvalue().splitlines()[-1])
    assert (line["event"], line["vocabulary"]) == ("speech_call", 2)


def test_the_local_double_takes_a_vocabulary_and_ignores_it() -> None:
    assert ScriptedSpeech("т").transcribe(AUDIO, WEBM, "uk-UA", vocabulary=("Upwork",)) == "т"
