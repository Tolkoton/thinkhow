"""Contract tests of voice-language: invariants I1-I4, inputs chosen by hand from each «Domain»."""

import json
from pathlib import Path

import pytest
from vl_fakes import (
    ALICE,
    BAD_CODES,
    H_ALICE,
    TABLE,
    location_path,
    make_app,
    profile_bytes,
    put_profile,
    put_profile_json,
)

from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import Language, NoLanguage, ensure_profile, language, set_language

# Contents of profile.json that hold no language of the list (I1 Domain).
NO_LANGUAGE_CONTENTS: tuple[bytes, ...] = (
    b"",
    b"not json",
    b"{",
    b"[]",
    b'"x"',
    b"null",
    b"5",
    b"\xff\xfe\xfd",
    b'{"email": "\xff"}',
    b"{}",
    b'{"email": "alice@example.com"}',
    b'{"email": "alice@example.com", "language": null}',
    b'{"email": "alice@example.com", "language": 5}',
    b'{"email": "alice@example.com", "language": ["pl-PL"]}',
    b'{"email": "alice@example.com", "language": {"code": "pl-PL"}}',
    b'{"email": "alice@example.com", "language": true}',
    b'{"email": "alice@example.com", "language": "ru-RU"}',
    b'{"email": "alice@example.com", "language": "ru"}',
    b'{"email": "alice@example.com", "language": "RU-ru"}',
    b'{"email": "alice@example.com", "language": " ru-RU "}',
    b'{"email": "alice@example.com", "language": "ru-UA"}',
    b'{"email": "alice@example.com", "language": ""}',
    b'{"email": "alice@example.com", "language": " pl-PL "}',
    b'{"email": "alice@example.com", "language": "pl-pl"}',
    b'{"email": "alice@example.com", "language": "PL-pl"}',
    b'{"email": "alice@example.com", "language": "pl_PL"}',
    b'{"email": "alice@example.com", "language": "Polski"}',
    b'{"email": "alice@example.com", "language": "xx-YY"}',
)


def test_I1_language_returns_only_a_language_of_the_list_never_russian(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path / "direct")
    # no file at all
    with pytest.raises(NoLanguage):
        language(store, ALICE)
    for content in NO_LANGUAGE_CONTENTS:
        put_profile(store, ALICE, content)
        with pytest.raises(NoLanguage):
            language(store, ALICE)
    # lawful contents give exactly the language of the list
    put_profile_json(store, ALICE, {"email": "alice@example.com", "language": "pl-PL"})
    assert language(store, ALICE) == Language("pl-PL", "Polski")
    put_profile_json(store, ALICE, {"language": "uk-UA"})
    assert language(store, ALICE) == Language("uk-UA", "Українська")
    put_profile_json(store, ALICE, {"email": "alice@example.com", "language": "yue-Hant-HK", "x": 1})
    assert language(store, ALICE) == Language("yue-Hant-HK", "粵語")
    # web level: a spoiled profile -> GET / 303 to /language, GET /language 200
    web_contents = (
        b"not json",
        b"\xff\xfe\xfd",
        b"[]",
        b'{"email": "alice@example.com", "language": "ru-RU"}',
    )
    for i, content in enumerate(web_contents):
        app = make_app(tmp_path / f"web{i}")
        put_profile(app.storage, ALICE, content)
        home = app.client.get("/", headers=H_ALICE)
        assert home.status_code == 303, (content, home.status_code)
        assert location_path(home.headers) == "/language"
        assert app.client.get("/language", headers=H_ALICE).status_code == 200, content


def _prior_states() -> list[tuple[str, bytes | None]]:
    return [
        ("absent", None),
        ("email only", b'{"email": "alice@example.com"}'),
        ("another language, another email", b'{"email": "old@example.com", "language": "en-US"}'),
        ("spoiled", b"\xff{not json"),
    ]


def test_I2_set_language_then_language_round_trips_and_keeps_the_email(tmp_path: Path) -> None:
    assert len(TABLE) == 85
    n = 0
    for code, name in TABLE:
        for state, content in _prior_states():
            n += 1
            store = LocalStorage(tmp_path / f"s{n}")
            if content is not None:
                put_profile(store, ALICE, content)
            set_language(store, ALICE, code)
            assert language(store, ALICE) == Language(code, name), (code, state)
            raw = profile_bytes(store, ALICE)
            assert raw is not None, (code, state)
            assert json.loads(raw.decode("utf-8")) == {"email": "alice@example.com", "language": code}, (
                code,
                state,
            )


def test_I3_set_language_with_a_code_off_the_list_raises_and_changes_nothing(tmp_path: Path) -> None:
    others = ("Polski", "pl", "uk", "en", "en-us", "EN-US", "pl-PL\n", "\tpl-PL", "ru-UA", "xx-YY")
    n = 0
    for code in BAD_CODES + others:
        for state, content in [
            *_prior_states(),
            ("with a language", b'{"email": "alice@example.com", "language": "pl-PL"}'),
        ]:
            n += 1
            store = LocalStorage(tmp_path / f"s{n}")
            if content is not None:
                put_profile(store, ALICE, content)
            with pytest.raises(ValueError):
                set_language(store, ALICE, code)
            assert profile_bytes(store, ALICE) == content, (code, state)
    # a refused code after a lawful one: the lawful one stays
    store = LocalStorage(tmp_path / "after")
    set_language(store, ALICE, "pl-PL")
    before = profile_bytes(store, ALICE)
    with pytest.raises(ValueError):
        set_language(store, ALICE, "ru-RU")
    assert profile_bytes(store, ALICE) == before
    assert language(store, ALICE) == Language("pl-PL", "Polski")


def test_I4_ensure_profile_never_changes_an_existing_profile(tmp_path: Path) -> None:
    contents = (
        b'{"email": "alice@example.com"}',
        b'{"email": "alice@example.com", "language": "pl-PL"}',
        b'{"email": "old@example.com", "language": "ru-RU"}',
        b"not json",
        b"\xff\xfe",
        b"[]",
        b"",
    )
    for i, content in enumerate(contents):
        store = LocalStorage(tmp_path / f"s{i}")
        put_profile(store, ALICE, content)
        for _ in range(3):
            ensure_profile(store, ALICE)
            assert profile_bytes(store, ALICE) == content, content
    # after set_language, any number of calls
    store = LocalStorage(tmp_path / "chosen")
    ensure_profile(store, ALICE)
    set_language(store, ALICE, "uk-UA")
    chosen = profile_bytes(store, ALICE)
    for _ in range(3):
        ensure_profile(store, ALICE)
    assert profile_bytes(store, ALICE) == chosen
    assert language(store, ALICE) == Language("uk-UA", "Українська")
    # through requests after set_language (the login layer calls ensure_profile on each)
    app = make_app(tmp_path / "web")
    set_language(app.storage, ALICE, "de-DE")
    chosen = profile_bytes(app.storage, ALICE)
    for path in ("/", "/language", "/", "/language"):
        app.client.get(path, headers=H_ALICE)
        assert profile_bytes(app.storage, ALICE) == chosen, path
    assert language(app.storage, ALICE) == Language("de-DE", "Deutsch")
