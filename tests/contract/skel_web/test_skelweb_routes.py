"""Contract tests of skel-web: routes, SSE, the one error handler, the login layer (slice tester)."""

import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from skelweb_fakes import (
    ALICE,
    BOB,
    H_ALICE,
    H_BOB,
    H_OWNER,
    T0,
    ArmedStorage,
    Boom,
    ListBroken,
    Page,
    conv,
    error_fragment,
    make_app,
    make_pending,
    seed_topic,
    sse_events,
    update,
)

from thinkhow.workspace import TopicRef, list_topics, open_topic

ASK = "Хочу відкрити кав'ярню."
ANS = "Що може піти не так?"


def url(ref: TopicRef, tail: str = "") -> str:
    return f"/topics/{ref.uid}/{ref.topic_id}{tail}"


# --- pages ---------------------------------------------------------------------------------------


def test_home_lists_my_topics_and_the_new_topic_form(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    seed_topic(app.storage, ALICE, "Моя кав'ярня")
    seed_topic(app.storage, BOB, "Тема Боба")
    r = app.client.get("/", headers=H_ALICE)
    assert r.status_code == 200
    page = Page(r.text)
    assert page.shows("Мої теми")
    assert page.shows("Моя кав'ярня")
    assert not page.shows("Тема Боба")
    assert not page.shows("Усі теми")
    assert any(a.get("name") == "title" for _, a in page.tags)


def test_owner_home_has_all_topics_with_title_and_uid(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    seed_topic(app.storage, BOB, "Тема Боба")
    r = app.client.get("/", headers=H_OWNER)
    assert r.status_code == 200
    page = Page(r.text)
    assert page.shows("Усі теми")
    assert page.shows("Тема Боба")
    assert page.shows("bob_2")


def test_html_routes_are_text_html_utf8(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    ref = seed_topic(app.storage, ALICE, "Тема")
    assert app.client.get("/", headers=H_ALICE).headers["content-type"] == "text/html; charset=utf-8"
    assert app.client.get(url(ref), headers=H_ALICE).headers["content-type"] == "text/html; charset=utf-8"


def test_every_request_ensures_the_profile_of_the_person(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    assert app.client.get("/", headers=H_BOB).status_code == 200
    raw = app.storage.read("users", "bob_2/profile.json")
    assert raw is not None
    assert json.loads(raw)["email"] == "bob@example.com"


def test_post_topics_creates_and_redirects_303_to_the_topic(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    r = app.client.post("/topics", data={"title": "Нова справа"}, headers=H_ALICE)
    assert r.status_code == 303
    topics = list_topics(app.storage, ALICE)
    assert [t.title for t in topics] == ["Нова справа"]
    assert urlparse(r.headers["location"]).path == f"/topics/alice-1/{topics[0].ref.topic_id}"


def test_topic_page_title_turn_anchors_roles_and_texts(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    ref = seed_topic(app.storage, ALICE, "Кав'ярня біля дому", [(ASK, ANS)])
    r = app.client.get(url(ref), headers=H_ALICE)
    assert r.status_code == 200
    page = Page(r.text)
    assert page.shows("Кав'ярня біля дому")
    t1, t2 = page.text_of("t1"), page.text_of("t2")
    assert "Ви" in t1 and ASK in t1
    assert "Фасилітатор" in t2 and ANS in t2
    assert ANS not in t1


def test_own_topic_page_has_reply_form_send_and_close(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    ref = seed_topic(app.storage, ALICE, "Тема", [(ASK, ANS)])
    page = Page(app.client.get(url(ref), headers=H_ALICE).text)
    assert page.has_tag("textarea", name="text")
    assert page.shows("Надіслати")
    assert page.shows("Завершити сесію")


def test_topic_awaiting_answer_shows_try_again(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    ref = seed_topic(app.storage, ALICE, "Тема")
    make_pending(app.storage, ALICE, ref, ASK)
    page = Page(app.client.get(url(ref), headers=H_ALICE).text)
    assert page.shows("Спробуйте ще раз")


def test_owner_on_a_foreign_topic_sees_it_without_form_and_buttons(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    ref = seed_topic(app.storage, BOB, "Тема Боба", [(ASK, ANS)])
    r = app.client.get(url(ref), headers=H_OWNER)
    assert r.status_code == 200
    page = Page(r.text)
    assert page.shows("Тема Боба")
    assert ASK in page.text_of("t1")
    assert not page.has_tag("textarea", name="text")
    assert not any(a.get("name") == "text" for _, a in page.tags)
    for label in ("Надіслати", "Спробуйте ще раз", "Завершити сесію"):
        assert not page.shows(label), label


# --- SSE -----------------------------------------------------------------------------------------


def test_reply_streams_saved_deltas_answered_and_deltas_equal_the_saved_answer(tmp_path: Path) -> None:
    deltas = ["Перший рядок,\n", "другий — «так» 🌍", "!"]
    app = make_app(tmp_path, [[*deltas, update("Перший рядок,\nдругий — «так» 🌍!")]])
    ref = seed_topic(app.storage, ALICE, "Тема")
    r = app.client.post(url(ref, "/reply"), data={"text": ASK}, headers=H_ALICE)
    assert r.status_code == 200
    assert sse_events(r.text) == [
        ("saved", {"turn": 1}),
        ("delta", {"text": "Перший рядок,\n"}),
        ("delta", {"text": "другий — «так» 🌍"}),
        ("delta", {"text": "!"}),
        ("answered", {"turn": 2}),
    ]
    turns = open_topic(app.storage, ALICE, ref, T0).sessions[0].turns
    assert [(t.no, t.role, t.text) for t in turns] == [
        (1, "user", ASK),
        (2, "model", "Перший рядок,\nдругий — «так» 🌍!"),
    ]


def test_sse_response_headers(tmp_path: Path) -> None:
    app = make_app(tmp_path, [["Так", update("Так")]])
    ref = seed_topic(app.storage, ALICE, "Тема")
    r = app.client.post(url(ref, "/reply"), data={"text": ASK}, headers=H_ALICE)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert r.headers["cache-control"] == "no-cache"
    assert r.headers["x-accel-buffering"] == "no"


def test_retry_streams_the_answer_without_saved(tmp_path: Path) -> None:
    app = make_app(tmp_path, [["Ще раз: що першим?", update("Ще раз: що першим?")]])
    ref = seed_topic(app.storage, ALICE, "Тема")
    make_pending(app.storage, ALICE, ref, ASK)
    r = app.client.post(url(ref, "/retry"), headers=H_ALICE)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert sse_events(r.text) == [("delta", {"text": "Ще раз: що першим?"}), ("answered", {"turn": 2})]


def test_close_redirects_303_to_the_topic_and_closes_the_session(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    ref = seed_topic(app.storage, ALICE, "Тема", [(ASK, ANS)])
    r = app.client.post(url(ref, "/close"), headers=H_ALICE)
    assert r.status_code == 303
    assert urlparse(r.headers["location"]).path == url(ref)
    assert b"<!-- thinkhow:closed 1 " in (conv(app.storage, ref) or b"")


def test_model_failure_mid_stream_is_a_failed_event_and_the_turn_stays(tmp_path: Path) -> None:
    app = make_app(tmp_path, [["Почато ", Boom("down")]])
    ref = seed_topic(app.storage, ALICE, "Тема")
    r = app.client.post(url(ref, "/reply"), data={"text": ASK}, headers=H_ALICE)
    assert r.status_code == 200
    assert sse_events(r.text) == [
        ("saved", {"turn": 1}),
        ("delta", {"text": "Почато "}),
        ("failed", {"reason": "Boom"}),
    ]
    assert ASK.encode() in (conv(app.storage, ref) or b"")


def test_storage_failure_mid_stream_is_failed_internal_and_the_stream_ends(tmp_path: Path) -> None:
    store = ArmedStorage(tmp_path / "data")

    def arm() -> None:
        store.armed = True

    app = make_app(tmp_path, [["Відповідь", arm, update("Відповідь")]], storage=store)
    ref = seed_topic(store, ALICE, "Тема")
    r = app.client.post(url(ref, "/reply"), data={"text": ASK}, headers=H_ALICE)
    assert r.status_code == 200
    assert sse_events(r.text) == [
        ("saved", {"turn": 1}),
        ("delta", {"text": "Відповідь"}),
        ("failed", {"reason": "Internal"}),
    ]


# --- the one error handler ---------------------------------------------------------------------


def test_foreign_topic_page_is_404_fragment(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    ref = seed_topic(app.storage, BOB, "Тема Боба", [(ASK, ANS)])
    r = app.client.get(url(ref), headers=H_ALICE)
    assert r.status_code == 404
    assert error_fragment(r.text) == "Тему не знайдено."
    assert ASK not in r.text and "Тема Боба" not in r.text
    r2 = app.client.get("/topics/alice-1/t-000000000000", headers=H_ALICE)
    assert r2.status_code == 404
    assert error_fragment(r2.text) == "Тему не знайдено."


def test_reply_to_a_foreign_topic_is_404_and_writes_nothing(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    ref = seed_topic(app.storage, BOB, "Тема Боба", [(ASK, ANS)])
    before = conv(app.storage, ref)
    r = app.client.post(url(ref, "/reply"), data={"text": "Чужий текст"}, headers=H_ALICE)
    assert r.status_code == 404
    assert error_fragment(r.text) == "Тему не знайдено."
    assert conv(app.storage, ref) == before
    assert app.fac.calls == []


def test_reply_while_awaiting_answer_is_409_fragment(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    ref = seed_topic(app.storage, ALICE, "Тема")
    make_pending(app.storage, ALICE, ref, ASK)
    before = conv(app.storage, ref)
    r = app.client.post(url(ref, "/reply"), data={"text": "Ще одна"}, headers=H_ALICE)
    assert r.status_code == 409
    assert error_fragment(r.text) == "Спершу дочекайтеся відповіді або натисніть «Спробуйте ще раз»."
    assert conv(app.storage, ref) == before


def test_retry_with_nothing_to_retry_is_409_fragment(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    ref = seed_topic(app.storage, ALICE, "Тема", [(ASK, ANS)])
    r = app.client.post(url(ref, "/retry"), headers=H_ALICE)
    assert r.status_code == 409
    error_fragment(r.text)
    assert app.fac.calls == []


def test_empty_reply_text_is_400_fragment_and_nothing_written(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    ref = seed_topic(app.storage, ALICE, "Тема")
    before = conv(app.storage, ref)
    for text in ("", "   "):
        r = app.client.post(url(ref, "/reply"), data={"text": text}, headers=H_ALICE)
        assert r.status_code == 400, text
        assert error_fragment(r.text) == "Порожню репліку не надіслано."
    assert conv(app.storage, ref) == before
    assert app.fac.calls == []


def test_empty_title_is_400_fragment_and_no_topic(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    for title in ("", "   "):
        r = app.client.post("/topics", data={"title": title}, headers=H_ALICE)
        assert r.status_code == 400, title
        assert error_fragment(r.text) == "Назва теми порожня."
    assert list_topics(app.storage, ALICE) == []


def test_value_error_on_another_route_is_400_request_not_accepted(tmp_path: Path) -> None:
    app = make_app(tmp_path, now=lambda: datetime(2026, 10, 22, 16, 0, 0))  # no time zone → ValueError (S4)
    ref = seed_topic(app.storage, ALICE, "Тема")
    r = app.client.get(url(ref), headers=H_ALICE)
    assert r.status_code == 400
    assert error_fragment(r.text) == "Запит не прийнято."


def test_no_or_bad_iap_assertion_is_401_sign_in_with_google(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    ref = seed_topic(app.storage, ALICE, "Тема")
    for headers in ({}, {"x-goog-iap-jwt-assertion": "forged"}):
        for method, path in (("GET", "/"), ("GET", url(ref)), ("POST", url(ref, "/reply"))):
            r = app.client.request(
                method, path, headers=headers, data={"text": ASK} if method == "POST" else None
            )
            assert r.status_code == 401, (headers, path)
            assert error_fragment(r.text).startswith("Потрібно увійти через Google"), r.text
    assert app.fac.calls == []


def test_unexpected_exception_is_500_fragment_without_trace(tmp_path: Path) -> None:
    app = make_app(tmp_path, storage=ListBroken(tmp_path / "data"))
    r = app.client.get("/", headers=H_ALICE)
    assert r.status_code == 500
    assert error_fragment(r.text) == "Щось пішло не так — спробуйте ще раз."
    assert "boom-internal-detail" not in r.text
    assert "Traceback" not in r.text
