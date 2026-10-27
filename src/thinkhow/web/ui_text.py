"""The interface's words in the person's language (task 208): one catalog per language, read once.

The catalogs are JSON files in `locales/`, named by the first subtag of a listed code ("pl" for pl-PL,
"cmn" for cmn-Hans-CN). Ukrainian is the source; a key a catalog lacks falls back to English, then to
Ukrainian. A card's title is `card.<id>`; the Ukrainian one stays in the card itself. Reads only its own
files.
"""

import functools
import json
from collections.abc import Mapping
from pathlib import Path

from thinkhow.knowledge import Card
from thinkhow.workspace import LANGUAGES

LOCALES = Path(__file__).resolve().parent / "locales"
SOURCE = "uk"
FALLBACK = "en"
RTL = frozenset({"ar", "fa", "he", "sd"})
NAMES = frozenset(code.split("-")[0] for code in (lang.code for lang in LANGUAGES))
# Browser tags whose first subtag is not the one in the list.
ALIASES = {"zh": "cmn", "no": "nb", "nn": "nb", "tl": "fil", "iw": "he", "in": "id"}
CANTONESE = ("zh-hk", "zh-mo", "zh-hant-hk", "zh-hant-mo")


def catalog_name(code: str) -> str:
    """The catalog of a listed language code: its first subtag."""
    return code.split("-")[0]


@functools.cache
def texts(name: str) -> Mapping[str, str]:
    """Flow: Ukrainian ← English ← the language's own words; an unknown name is English."""
    if name == SOURCE:
        return _read(SOURCE)
    own = _read(name) if name in NAMES else {}
    return _read(SOURCE) | _read(FALLBACK) | own


def direction(name: str) -> str:
    return "rtl" if name in RTL else "ltr"


def card_title(card: Card, words: Mapping[str, str]) -> str:
    return words.get(f"card.{card.id}", card.title)


def from_header(header: str | None) -> str:
    """Before a choice (the language page, a fragment): the browser's first listed language; no header → the
    source language; a header with none of the listed languages → English."""
    if not header:
        return SOURCE
    for tag in _tags(header):
        name = _match(tag)
        if name:
            return name
    return FALLBACK


def _tags(header: str) -> list[str]:
    """The header's tags by weight, the order kept among equal weights; `*` and q=0 dropped."""
    weighted: list[tuple[float, int, str]] = []
    for at, part in enumerate(header.split(",")):
        tag, _, params = part.strip().partition(";")
        weight = 1.0
        if params.strip().startswith("q="):
            try:
                weight = float(params.strip()[2:])
            except ValueError:
                weight = 0.0
        if tag and tag != "*" and weight > 0:
            weighted.append((-weight, at, tag.lower()))
    return [tag for _, _, tag in sorted(weighted)]


def _match(tag: str) -> str | None:
    if tag.startswith(CANTONESE) or tag.startswith("yue"):
        return "yue"
    first = tag.split("-")[0]
    name = ALIASES.get(first, first)
    return name if name in NAMES else None


def _read(name: str) -> dict[str, str]:
    data = json.loads((LOCALES / f"{name}.json").read_text(encoding="utf-8"))
    return {str(k): str(v) for k, v in data.items()}
