"""Seam 3 of voice-reply-language: the real facilitator answers in the person's language, never Russian.

Run with `-m live`. Quoted spans are cut out before every check: a reply is judged by its own words.
"""

import os
import re
from pathlib import Path

import pytest

from thinkhow.facilitation import FacilitationContext, FacilitatorUpdate, ProblemMap
from thinkhow.facilitation.respond import respond
from thinkhow.knowledge import CurrentKnowledge, current, seed
from thinkhow.platform.config import load_settings
from thinkhow.platform.llm import Llm, make_llm
from thinkhow.platform.storage import LocalStorage

CARDS = Path(__file__).resolve().parents[2] / "cards"
QUOTES = re.compile(r"«[^»]*»|\"[^\"]*\"|“[^”]*”|„[^“”]*[“”]")
CYRILLIC = re.compile(r"[Ѐ-ӿ]")
RUSSIAN_LETTERS = re.compile(r"[ыэъёЫЭЪЁ]")
UKRAINIAN_LETTERS = re.compile(r"[іїєґІЇЄҐ]")
POLISH_LETTERS = re.compile(r"[ąęłśżźćńóĄĘŁŚŻŹĆŃÓ]")
RUSSIAN_WORDS = {"что", "это", "как", "хорошо", "понятно", "если", "или", "мы", "сейчас"}
POLISH_WORDS = {"nie", "czy", "jak", "się", "co"}
ENGLISH_WORDS = {"the", "you", "what", "your", "is"}


def words(text: str) -> set[str]:
    return {w.casefold() for w in re.findall(r"\w+", text)}


def own(reply: str) -> str:
    return QUOTES.sub(" ", reply)


def first_sentence(text: str) -> str:
    return re.split(r"[.?!]", text.strip(), maxsplit=1)[0]


@pytest.fixture(scope="module")
def model(tmp_path_factory: pytest.TempPathFactory) -> tuple[CurrentKnowledge, Llm]:
    storage = LocalStorage(tmp_path_factory.mktemp("knowledge"))
    seed(storage, CARDS)
    environ = {
        **os.environ,
        "THINKHOW_LOCAL": "false",
        "THINKHOW_USERS_BUCKET": "-",
        "THINKHOW_SYSTEM_BUCKET": "-",
        "THINKHOW_OWNER_EMAIL": "-",
    }
    return current(storage), make_llm(load_settings(environ), script=lambda *_: "")


def answer(model: tuple[CurrentKnowledge, Llm], language: str, text: str) -> str:
    knowledge, llm = model
    ctx = FacilitationContext("pre-mortem", [], ProblemMap(), 1, text, language)
    update = list(respond(ctx, knowledge, llm))[-1]
    assert isinstance(update, FacilitatorUpdate)
    print(f"\n[{language}] {text}\n→ {update.reply}")
    return update.reply


@pytest.mark.live
def test_a_polish_person_writing_polish_gets_polish(model: tuple[CurrentKnowledge, Llm]) -> None:
    reply = own(
        answer(model, "Polski (pl-PL)", "Chcę w ciągu trzech miesięcy otworzyć kawiarnię w Krakowie.")
    )
    assert not CYRILLIC.search(reply), reply
    assert POLISH_LETTERS.search(reply) or words(reply) & POLISH_WORDS, reply


@pytest.mark.live
@pytest.mark.parametrize("run", range(5))
def test_a_ukrainian_person_writing_russian_gets_ukrainian(
    model: tuple[CurrentKnowledge, Llm], run: int
) -> None:
    text = "Хочу за три месяца открыть кофейню во Львове. Давайте проверим план, пока не поздно."
    reply = own(answer(model, "Українська (uk-UA)", text))
    head = first_sentence(reply)
    print(f"first sentence: {head}")
    for part in (head, reply):
        assert not RUSSIAN_LETTERS.search(part), part
        assert not words(part) & RUSSIAN_WORDS, (words(part) & RUSSIAN_WORDS, part)
    assert UKRAINIAN_LETTERS.search(reply), reply


@pytest.mark.live
def test_an_english_person_writing_ukrainian_gets_english(model: tuple[CurrentKnowledge, Llm]) -> None:
    text = "Хочу за три місяці відкрити кав'ярню у Львові. Перевірмо план, поки не пізно."
    reply = own(answer(model, "English (United States) (en-US)", text))
    assert not CYRILLIC.search(reply), reply
    assert words(reply) & ENGLISH_WORDS, reply
