"""Contract tests of minimal-design: the markup the «Seam» names (slice tester, from the contract)."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from mdesign_fakes import (
    ALICE,
    BOB,
    H_ALICE,
    H_OWNER,
    OWNER,
    App,
    Dom,
    El,
    choose_language,
    make_app,
    norm,
    seed_topic,
    topic_url,
)

ASK = "Хочу відкрити кав'ярню."
ANS = "Що може піти не так?"
PENDING_TEXT = "Фасилітатор відповідає…"


def _own_topic(tmp_path: Path) -> tuple[App, Dom]:
    app = make_app(tmp_path)
    choose_language(app.storage, ALICE)
    ref = seed_topic(app.storage, ALICE, "Кав'ярня біля дому", ((ASK, ANS),))
    r = app.client.get(topic_url(ref), headers=H_ALICE)
    assert r.status_code == 200
    return app, Dom(r.text)


def _home(tmp_path: Path) -> Dom:
    app = make_app(tmp_path)
    choose_language(app.storage, ALICE)
    seed_topic(app.storage, ALICE, "Кав'ярня біля дому")
    r = app.client.get("/", headers=H_ALICE)
    assert r.status_code == 200
    return Dom(r.text)


def _buttons_labelled(dom: Dom, label: str) -> list[El]:
    found = [e for e in dom.find("button") if norm(e.text()) == label]
    found += [
        e
        for e in dom.find("input")
        if (e.attrs.get("type") or "").lower() == "submit" and e.attrs.get("value") == label
    ]
    return found


def _element_siblings(el: El) -> list[El]:
    assert el.parent is not None
    return el.parent.children


def test_head_declares_color_scheme_light_dark(tmp_path: Path) -> None:
    dom = _home(tmp_path)
    metas = [e for e in dom.find("meta") if (e.attrs.get("name") or "").lower() == "color-scheme"]
    assert len(metas) == 1, f"<meta name=color-scheme> found {len(metas)} times"
    assert norm(metas[0].attrs.get("content") or "") == "light dark"
    assert any(a.tag == "head" for a in metas[0].ancestors()), "the meta is not in <head>"


def test_inline_style_element_is_gone_from_the_pages(tmp_path: Path) -> None:
    home = _home(tmp_path / "home")
    _, topic = _own_topic(tmp_path / "topic")
    assert home.find("style") == [], "an inline <style> on «Мої теми»"
    assert topic.find("style") == [], "an inline <style> on the topic page"


def test_navigation_links_live_in_header_site(tmp_path: Path) -> None:
    dom = _home(tmp_path)
    headers = [e for e in dom.find("header") if "site" in e.classes()]
    assert len(headers) == 1, f'<header class="site"> found {len(headers)} times'
    header = headers[0]
    inside = [
        (urlparse(e.attrs.get("href") or "").path, norm(e.text()))
        for e in dom.find("a")
        if header in e.ancestors()
    ]
    assert ("/", "ThinkHow") in inside, inside
    assert ("/language", "Мова") in inside, inside


def test_page_content_lives_in_main(tmp_path: Path) -> None:
    home = _home(tmp_path / "home")
    mains = home.find("main")
    assert len(mains) == 1, f"<main> on «Мої теми» found {len(mains)} times"
    forms = [e for e in home.find("form") if urlparse(e.attrs.get("action") or "").path == "/topics"]
    assert forms, "no new-topic form on «Мої теми»"
    assert all(mains[0] in f.ancestors() for f in forms), "the new-topic form is outside <main>"

    _, topic = _own_topic(tmp_path / "topic")
    mains = topic.find("main")
    assert len(mains) == 1, f"<main> on the topic page found {len(mains)} times"
    for el_id in ("t1", "t2", "send", "live"):
        assert mains[0] in topic.by_id(el_id).ancestors(), f"#{el_id} is outside <main>"
    for h1 in topic.find("h1"):
        assert mains[0] in h1.ancestors(), "the topic's <h1> is outside <main>"


def test_main_buttons_carry_class_primary(tmp_path: Path) -> None:
    home = _home(tmp_path / "home")
    app = make_app(tmp_path / "lang")
    choose_language(app.storage, ALICE)
    lang = Dom(app.client.get("/language", headers=H_ALICE).text)
    _, topic = _own_topic(tmp_path / "topic")
    for page, label in ((home, "Створити"), (lang, "Зберегти"), (topic, "Надіслати")):
        buttons = _buttons_labelled(page, label)
        assert buttons, f"no button «{label}»"
        for b in buttons:
            assert "primary" in b.classes(), f"«{label}» has class {b.attrs.get('class')!r}"


def test_send_pending_and_retry_are_siblings_in_div_actions(tmp_path: Path) -> None:
    _, dom = _own_topic(tmp_path)
    send, pending, retry = dom.by_id("send"), dom.by_id("pending"), dom.by_id("retry")
    parent = send.parent
    assert parent is not None
    assert pending.parent is parent and retry.parent is parent, "#send, #pending, #retry: not one parent"
    assert parent.tag == "div" and "actions" in parent.classes(), (
        f'their parent is <{parent.tag} class="{parent.attrs.get("class")}">, not <div class="actions">'
    )


def test_pending_is_a_static_span_right_after_send(tmp_path: Path) -> None:
    _, dom = _own_topic(tmp_path)
    pending = dom.by_id("pending")
    assert pending.tag == "span"
    assert "pending" in pending.classes()
    assert norm(pending.text()) == PENDING_TEXT
    siblings = _element_siblings(pending)
    send = dom.by_id("send")
    assert send in siblings
    assert siblings.index(pending) == siblings.index(send) + 1, "#pending is not the next element after #send"


def test_pending_is_only_on_ones_own_topic_page(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    choose_language(app.storage, ALICE, OWNER)
    alice_ref = seed_topic(app.storage, ALICE, "Своя тема", ((ASK, ANS),))
    bob_ref = seed_topic(app.storage, BOB, "Тема Боба", ((ASK, ANS),))
    own = Dom(app.client.get(topic_url(alice_ref), headers=H_ALICE).text)
    foreign = Dom(app.client.get(topic_url(bob_ref), headers=H_OWNER).text)
    assert len(own.find(id="pending")) == 1, "no #pending on one's own topic page"
    assert foreign.find(id="pending") == [], "#pending on a foreign topic page (no form there)"
    assert PENDING_TEXT not in foreign.root.text()


def test_send_and_retry_have_autocomplete_off(tmp_path: Path) -> None:
    _, dom = _own_topic(tmp_path)
    for el_id in ("send", "retry"):
        assert dom.by_id(el_id).attrs.get("autocomplete") == "off", f"#{el_id}"
