"""Helpers for the voice-language contract tests (slice tester). Built from the contract, not the code.

- TABLE: the 85 (code, name) pairs of the contract's «Seam» table, copied as a literal, in its order.
- make_app: `create_app(Deps(...))` with a local folder and `IapIdentity(verify_fake)`; returns the app too,
  so a test may add a route to it (Seam 5).
- profile_bytes / put_profile: `users/<uid>/profile.json` read and written past `workspace`.
- Html: tags, <option>s of a <select>, <a>s with their text, the visible text with whitespace collapsed.
- assert_fragment: the body is exactly one `<p class="error">TEXT</p>` (surrounding whitespace allowed).
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI
from fastapi.testclient import TestClient

from thinkhow.access import CurrentUser
from thinkhow.platform.config import load_settings
from thinkhow.platform.identity import IapIdentity
from thinkhow.platform.speech import ScriptedSpeech
from thinkhow.platform.storage import LocalStorage
from thinkhow.web.server import Deps, create_app

REPO = Path(__file__).resolve().parents[3]
GOOGLE_TABLE = REPO / ".engine/artifacts/spikes/voice-stt-2026-10-23/google_language_table.txt"

TABLE: tuple[tuple[str, str], ...] = (
    ("af-ZA", "Afrikaans"),
    ("rup-BG", "Armãneashti"),
    ("az-AZ", "Azərbaycan"),
    ("bs-BA", "Bosanski"),
    ("ca-ES", "Català"),
    ("ceb", "Cebuano"),
    ("cs-CZ", "Čeština"),
    ("da-DK", "Dansk"),
    ("de-DE", "Deutsch"),
    ("et-EE", "Eesti"),
    ("en-AU", "English (Australia)"),
    ("en-IN", "English (India)"),
    ("en-GB", "English (United Kingdom)"),
    ("en-US", "English (United States)"),
    ("es-ES", "Español (España)"),
    ("es-US", "Español (Estados Unidos)"),
    ("es-419", "Español (Latinoamérica)"),
    ("fil-PH", "Filipino"),
    ("fr-CA", "Français (Canada)"),
    ("fr-FR", "Français (France)"),
    ("gl-ES", "Galego"),
    ("ha-NG", "Hausa"),
    ("hr-HR", "Hrvatski"),
    ("id-ID", "Indonesia"),
    ("is-IS", "Íslenska"),
    ("it-IT", "Italiano"),
    ("jv-ID", "Jawa"),
    ("kea-CV", "Kabuverdianu"),
    ("sw-KE", "Kiswahili"),
    ("lv-LV", "Latviešu"),
    ("lt-LT", "Lietuvių"),
    ("ln-CD", "Lingála"),
    ("hu-HU", "Magyar"),
    ("mt-MT", "Malti"),
    ("ms-MY", "Melayu"),
    ("nl-NL", "Nederlands"),
    ("nb-NO", "Norsk bokmål"),
    ("uz-UZ", "O‘zbek"),
    ("pl-PL", "Polski"),
    ("pt-BR", "Português (Brasil)"),
    ("pt-PT", "Português (Portugal)"),
    ("ro-RO", "Română"),
    ("sk-SK", "Slovenčina"),
    ("sl-SI", "Slovenščina"),
    ("fi-FI", "Suomi"),
    ("sv-SE", "Svenska"),
    ("vi-VN", "Tiếng Việt"),
    ("tr-TR", "Türkçe"),
    ("el-GR", "Ελληνικά"),
    ("be-BY", "Беларуская"),
    ("bg-BG", "Български"),
    ("ky-KG", "Кыргызча"),
    ("mk-MK", "Македонски"),
    ("mn-MN", "Монгол"),
    ("sr-RS", "Српски"),
    ("tg-TJ", "Тоҷикӣ"),
    ("uk-UA", "Українська"),
    ("kk-KZ", "Қазақ тілі"),
    ("hy-AM", "Հայերեն"),
    ("he-IL", "עברית"),
    ("ar-EG", "العربية"),
    ("sd-Arab-IN", "سنڌي (ڀارت)"),
    ("fa-IR", "فارسی"),
    ("ne-NP", "नेपाली"),
    ("mr-IN", "मराठी"),
    ("hi-IN", "हिन्दी"),
    ("as-IN", "অসমীয়া"),
    ("bn-BD", "বাংলা (বাংলাদেশ)"),
    ("bn-IN", "বাংলা (ভারত)"),
    ("pa-Guru-IN", "ਪੰਜਾਬੀ (ਗੁਰਮੁਖੀ)"),
    ("pa-IN", "ਪੰਜਾਬੀ (ਭਾਰਤ)"),
    ("gu-IN", "ગુજરાતી"),
    ("or-IN", "ଓଡ଼ିଆ"),
    ("te-IN", "తెలుగు"),
    ("kn-IN", "ಕನ್ನಡ"),
    ("ml-IN", "മലയാളം"),
    ("th-TH", "ไทย"),
    ("my-MM", "မြန်မာ"),
    ("ka-GE", "ქართული"),
    ("ko-KR", "한국어"),
    ("am-ET", "አማርኛ"),
    ("km-KH", "ខ្មែរ"),
    ("cmn-Hans-CN", "中文 (简体)"),
    ("ja-JP", "日本語"),
    ("yue-Hant-HK", "粵語"),
)

ALICE = CurrentUser(id="alice-1", email="alice@example.com", is_owner=False)
BOB = CurrentUser(id="bob_2", email="bob@example.com", is_owner=False)

IAP = "x-goog-iap-jwt-assertion"
TOKENS: dict[str, dict[str, str]] = {
    "tok-alice": {"sub": "accounts.google.com:alice-1", "email": "alice@example.com"},
    "tok-bob": {"sub": "accounts.google.com:bob_2", "email": "bob@example.com"},
}
H_ALICE = {IAP: "tok-alice"}
H_BOB = {IAP: "tok-bob"}

NOT_IN_LIST = "Такої мови немає в переліку."
FIRST_CHOOSE = "Спершу оберіть мову (сторінка «Мова»)."
PLACEHOLDER = "— оберіть мову —"

# Strings that equal no code of the list exactly (Seam 3, I3).
BAD_CODES = (
    "ru-RU",
    "ru",
    "RU-ru",
    " ru-RU ",
    " pl-PL ",
    "PL-pl",
    "pl-pl",
    "pl_PL",
    "",
)


def verify_fake(token: str, audience: str) -> Mapping[str, object]:
    if token not in TOKENS:
        raise RuntimeError("bad signature")
    return TOKENS[token]


def _no_facilitate(context: Any) -> Iterator[Any]:
    raise AssertionError("facilitate is not called in voice-language tests")


@dataclass
class App:
    client: TestClient
    storage: LocalStorage
    app: FastAPI


def make_app(tmp_path: Path) -> App:
    store = LocalStorage(tmp_path / "data")
    settings = load_settings(
        {
            "THINKHOW_LOCAL": "true",
            "THINKHOW_LOCAL_DIR": str(tmp_path),
            "THINKHOW_OWNER_EMAIL": "owner@example.com",
        }
    )
    from datetime import UTC, datetime

    deps = Deps(
        storage=store,
        identity=IapIdentity("aud-test", verify_fake),
        settings=settings,
        facilitate=_no_facilitate,
        now=lambda: datetime(2026, 10, 23, 16, 0, 0, tzinfo=UTC),
        speech=ScriptedSpeech("(локальний режим) розпізнаний текст"),
    )
    fastapi_app = create_app(deps)
    client = TestClient(fastapi_app, raise_server_exceptions=False, follow_redirects=False)
    return App(client, store, fastapi_app)


def profile_path(user: CurrentUser) -> str:
    return f"{user.id}/profile.json"


def profile_bytes(store: LocalStorage, user: CurrentUser) -> bytes | None:
    return store.read("users", profile_path(user))


def put_profile(store: LocalStorage, user: CurrentUser, data: bytes) -> None:
    store.write("users", profile_path(user), data, "application/json")


def put_profile_json(store: LocalStorage, user: CurrentUser, obj: object) -> None:
    put_profile(store, user, json.dumps(obj, ensure_ascii=False).encode("utf-8"))


def location_path(headers: Mapping[str, str]) -> str:
    assert "location" in headers, f"no Location header: {dict(headers)!r}"
    return urlparse(headers["location"]).path


def assert_fragment(body: str, text: str) -> None:
    m = re.fullmatch(r'\s*<p class="error">(.*)</p>\s*', body, flags=re.S)
    assert m, f'the body is not one <p class="error"> fragment: {body!r}'
    assert m.group(1) == text, f"fragment text {m.group(1)!r} != {text!r}"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


class Html(HTMLParser):
    """Tags with attributes; the <option>s of each <select> by name; every <a> with its text."""

    def __init__(self, html: str) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self.selects: dict[str, list[tuple[dict[str, str | None], str]]] = {}
        self.anchors: list[tuple[str | None, str]] = []
        self._select: str | None = None
        self._option: tuple[dict[str, str | None], list[str]] | None = None
        self._anchor: tuple[str | None, list[str]] | None = None
        self._texts: list[str] = []
        self._in_script = False
        self.feed(html)
        self.close()

    def _end_option(self) -> None:
        if self._option is not None and self._select is not None:
            attrs, parts = self._option
            self.selects[self._select].append((attrs, "".join(parts).strip()))
        self._option = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        self.tags.append((tag, a))
        if tag == "select":
            self._select = a.get("name") or ""
            self.selects.setdefault(self._select, [])
        elif tag == "option":
            self._end_option()
            self._option = (a, [])
        elif tag == "a":
            self._anchor = (a.get("href"), [])
        elif tag == "script":
            self._in_script = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "option":
            self._end_option()
        elif tag == "select":
            self._end_option()
            self._select = None
        elif tag == "a" and self._anchor is not None:
            href, parts = self._anchor
            self.anchors.append((href, _norm("".join(parts))))
            self._anchor = None
        elif tag == "script":
            self._in_script = False

    def handle_data(self, data: str) -> None:
        if self._in_script:
            return
        self._texts.append(data)
        if self._option is not None:
            self._option[1].append(data)
        if self._anchor is not None:
            self._anchor[1].append(data)

    def joined_text(self) -> str:
        """The visible text with tags removed and whitespace collapsed (no separator added between nodes)."""
        return _norm("".join(self._texts))

    def options(self, name: str) -> list[tuple[dict[str, str | None], str]]:
        assert name in self.selects, f"no <select name={name!r}> on the page"
        return self.selects[name]

    def links_to(self, path: str) -> list[str]:
        """The texts of every <a> whose href points at `path`."""
        return [text for href, text in self.anchors if href is not None and urlparse(href).path == path]

    def shows(self, needle: str) -> bool:
        return needle in self.joined_text() or any(
            needle in (v or "") for _, a in self.tags for v in a.values()
        )
