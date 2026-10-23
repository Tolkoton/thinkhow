"""Disputed (Q1): the <option>s of /language follow the order of LANGUAGES. Not sealed until answered."""

from pathlib import Path

from vl_fakes import H_ALICE, TABLE, Html, make_app


def test_q1_language_page_lists_the_languages_in_the_order_of_the_list(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    r = app.client.get("/language", headers=H_ALICE)
    assert r.status_code == 200
    listed = [
        (attrs.get("value"), text) for attrs, text in Html(r.text).options("code") if attrs.get("value")
    ]
    assert listed == list(TABLE)
