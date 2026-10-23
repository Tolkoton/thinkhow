"""Contract tests of voice-language: the web side (Seams 1, 2, 3, 5), written from the contract."""

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from vl_fakes import (
    ALICE,
    BAD_CODES,
    FIRST_CHOOSE,
    H_ALICE,
    NOT_IN_LIST,
    PLACEHOLDER,
    TABLE,
    Html,
    assert_fragment,
    location_path,
    make_app,
    profile_bytes,
    put_profile,
)

from thinkhow.workspace import Language, NoLanguage, create_topic, language, set_language

T0 = datetime(2026, 10, 23, 16, 0, 0, tzinfo=UTC)
EMAIL_ONLY = b'{"email": "alice@example.com"}'


def _selected(page: Html) -> list[str | None]:
    return [attrs.get("value") for attrs, _ in page.options("code") if "selected" in attrs]


# --- Seam 1: no redirect loop -------------------------------------------------------------------


def test_seam1_language_page_without_a_language_lists_every_language_after_a_placeholder(
    tmp_path: Path,
) -> None:
    app = make_app(tmp_path)
    r = app.client.get("/language", headers=H_ALICE)
    assert r.status_code == 200
    page = Html(r.text)
    options = page.options("code")
    first_attrs, first_text = options[0]
    assert first_attrs.get("value") == ""
    assert first_text == PLACEHOLDER
    listed = [(attrs.get("value"), text) for attrs, text in options[1:]]
    assert len(listed) == 85
    assert len(set(listed)) == 85
    assert set(listed) == set(TABLE)
    assert page.shows("Зберегти")


def test_seam1_first_visit_chain_home_to_language_to_choice_to_home(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    c = app.client
    first = c.get("/language", headers=H_ALICE)
    assert first.status_code == 200
    assert "code" in Html(first.text).selects
    home = c.get("/", headers=H_ALICE)
    assert home.status_code == 303
    assert location_path(home.headers) == "/language"
    page = c.get("/language", headers=H_ALICE)
    assert page.status_code == 200
    chosen = c.post("/language", data={"code": "pl-PL"}, headers=H_ALICE)
    assert chosen.status_code == 303
    assert location_path(chosen.headers) == "/"
    again = c.get("/", headers=H_ALICE)
    assert again.status_code == 200


def test_seam1_language_page_marks_the_current_language_selected(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    set_language(app.storage, ALICE, "uk-UA")
    r = app.client.get("/language", headers=H_ALICE)
    assert r.status_code == 200
    assert _selected(Html(r.text)) == ["uk-UA"]


# --- Seam 2: the chosen language is not overwritten ----------------------------------------------


def test_seam2_chosen_language_survives_further_requests(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    c = app.client
    assert c.post("/language", data={"code": "pl-PL"}, headers=H_ALICE).status_code == 303
    for path in ("/", "/language", "/"):
        c.get(path, headers=H_ALICE)
    c.post("/topics", data={"title": "Тема"}, headers=H_ALICE)
    assert language(app.storage, ALICE) == Language("pl-PL", "Polski")
    raw = profile_bytes(app.storage, ALICE)
    assert raw is not None
    assert json.loads(raw.decode("utf-8")) == {"email": "alice@example.com", "language": "pl-PL"}


def test_seam2_profile_with_only_the_email_sends_home_to_the_language_page(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    put_profile(app.storage, ALICE, EMAIL_ONLY)
    r = app.client.get("/", headers=H_ALICE)
    assert r.status_code == 303
    assert location_path(r.headers) == "/language"
    assert profile_bytes(app.storage, ALICE) == EMAIL_ONLY


# --- Seam 3: Russian does not pass by any path ---------------------------------------------------


def test_seam3_post_language_off_the_list_empty_or_missing_is_400_and_the_profile_stays(
    tmp_path: Path,
) -> None:
    starts = (b'{"email": "alice@example.com", "language": "uk-UA"}', EMAIL_ONLY)
    forms: list[dict[str, str]] = [{"code": code} for code in BAD_CODES] + [{}]
    n = 0
    for start in starts:
        for form in forms:
            n += 1
            app = make_app(tmp_path / f"a{n}")
            put_profile(app.storage, ALICE, start)
            r = app.client.post("/language", data=form, headers=H_ALICE)
            assert r.status_code == 400, (start, form, r.status_code)
            assert_fragment(r.text, NOT_IN_LIST)
            assert profile_bytes(app.storage, ALICE) == start, (start, form)


# --- Seam 5: the NoLanguage handler splits by method ---------------------------------------------


def test_seam5_nolanguage_on_post_and_put_is_a_409_fragment_without_location(tmp_path: Path) -> None:
    app = make_app(tmp_path)

    def probe() -> None:
        raise NoLanguage()

    app.app.add_api_route("/__vl_probe", probe, methods=["POST"])
    app.app.add_api_route("/__vl_probe_put", probe, methods=["PUT"])
    for method, path in (("POST", "/__vl_probe"), ("PUT", "/__vl_probe_put")):
        r = app.client.request(method, path, headers=H_ALICE)
        assert r.status_code == 409, (method, r.status_code)
        assert "location" not in r.headers, method
        assert_fragment(r.text, FIRST_CHOOSE)


def test_seam5_nolanguage_on_get_of_home_and_own_topic_redirects_303_to_language(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    topic_id = create_topic(app.storage, ALICE, "Моя тема", T0)
    for path in ("/", f"/topics/alice-1/{topic_id}"):
        r = app.client.get(path, headers=H_ALICE)
        assert r.status_code == 303, (path, r.status_code)
        assert location_path(r.headers) == "/language", path


# --- pages ----------------------------------------------------------------------------------------


def test_home_shows_the_language_name_and_a_change_link_to_the_language_page(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    set_language(app.storage, ALICE, "uk-UA")
    r = app.client.get("/", headers=H_ALICE)
    assert r.status_code == 200
    page = Html(r.text)
    assert re.search(r"Мова:\s*Українська", page.joined_text()), page.joined_text()
    assert "змінити" in page.links_to("/language")


def test_every_page_has_the_language_link(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    set_language(app.storage, ALICE, "uk-UA")
    topic_id = create_topic(app.storage, ALICE, "Моя тема", T0)
    for path in ("/", "/language", f"/topics/alice-1/{topic_id}"):
        r = app.client.get(path, headers=H_ALICE)
        assert r.status_code == 200, (path, r.status_code)
        assert "Мова" in Html(r.text).links_to("/language"), path


def test_post_topics_does_not_require_a_language(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    r = app.client.post("/topics", data={"title": "Нова справа"}, headers=H_ALICE)
    assert r.status_code == 303
    assert location_path(r.headers).startswith("/topics/alice-1/")
