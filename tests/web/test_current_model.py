"""Task 203: the topic page says which thinking model leads, at which phase; changes show in the history."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from thinkhow.access import CurrentUser
from thinkhow.facilitation.types import Decision, FacilitatorUpdate, ReplyDelta, Rev, RoutingEvent
from thinkhow.knowledge import Card
from thinkhow.platform.config import load_settings
from thinkhow.platform.identity import IapIdentity
from thinkhow.platform.speech import ScriptedSpeech
from thinkhow.platform.storage import LocalStorage
from thinkhow.web.method import FREE, caption, marks
from thinkhow.web.server import Deps, create_app
from thinkhow.workspace import TopicRef, create_topic, open_topic, reply, set_language

T0 = datetime(2026, 10, 24, 12, 0, 0, tzinfo=UTC)
ALICE = CurrentUser(id="alice-1", email="alice@example.com", is_owner=False)
HEADERS = {"x-goog-iap-jwt-assertion": "tok-alice"}
REV = Rev(rev=2, n=18)


def _card(cid: str, title: str, phases: list[str]) -> Card:
    return Card.model_validate(
        {
            "id": cid,
            "title": title,
            "router": {"needs": "n", "when_yes": ["y"], "when_no": ["n"], "signals": []},
            "facilitator": {
                "purpose": "p",
                "stance": "s",
                "needs": "n",
                "phases": [{"id": p, "title": p, "goal": "g", "how": [], "exit": "e"} for p in phases],
                "ending": "e",
                "traps": [],
                "pairs_well": "",
            },
        }
    )


MATRIX = _card("weighted-matrix", "Зважена матриця рішень", ["options", "criteria", "weights", "choice"])
PREMORTEM = _card("pre-mortem", "Pre-mortem", ["plan", "failure", "steps"])
CARDS = {c.id: c for c in (MATRIX, PREMORTEM)}


def _decision(turn: int, kind: str, card_id: str | None = None, end: str | None = None) -> Decision:
    return Decision.model_validate(
        {
            "turn": turn,
            "rev": REV.model_dump(),
            "kind": kind,
            "profile": None,
            "candidates": [],
            "card_id": card_id,
            "end": end,
            "why": "w",
        }
    )


# --- the caption --------------------------------------------------------------------------------------------


def test_no_routing_is_a_free_conversation() -> None:
    assert caption((), None, CARDS) == FREE == "вільна розмова"


def test_an_offer_or_ask_without_a_chosen_card_is_a_free_conversation() -> None:
    assert caption((_decision(1, "offer"), _decision(3, "ask")), None, CARDS) == FREE


def test_a_chosen_card_shows_its_title_and_the_phase_number_of_all() -> None:
    routing = (_decision(1, "offer"), _decision(3, "choose", "weighted-matrix"))
    assert caption(routing, "criteria", CARDS) == "Зважена матриця рішень · 2 з 4"


def test_a_chosen_card_without_a_known_phase_shows_its_title_only() -> None:
    routing = (_decision(3, "choose", "weighted-matrix"),)
    assert caption(routing, None, CARDS) == "Зважена матриця рішень"
    assert caption(routing, "gone", CARDS) == "Зважена матриця рішень"


def test_after_the_end_of_a_card_it_is_a_free_conversation_again() -> None:
    routing = (_decision(3, "choose", "pre-mortem"), _decision(9, "end", "pre-mortem", "done"))
    assert caption(routing, None, CARDS) == FREE


def test_a_card_the_knowledge_no_longer_has_is_a_free_conversation() -> None:
    assert caption((_decision(3, "choose", "five-whys"),), "x", CARDS) == FREE


# --- the marks in the history -------------------------------------------------------------------------------


def test_a_choice_marks_the_reply_from_which_the_card_leads() -> None:
    got = marks((_decision(1, "offer"), _decision(3, "choose", "pre-mortem")), CARDS)
    assert got == {4: ["Далі веде модель мислення «Pre-mortem»"]}


def test_an_end_marks_the_next_turn_as_free_and_a_new_choice_marks_its_own_reply() -> None:
    routing = (
        _decision(3, "choose", "pre-mortem"),
        _decision(9, "end", "pre-mortem", "done"),
        _decision(11, "choose", "weighted-matrix"),
        _decision(15, "end", "weighted-matrix", "not_fit"),
    )
    assert marks(routing, CARDS) == {
        4: ["Далі веде модель мислення «Pre-mortem»"],
        11: ["«Pre-mortem» пройдено · далі вільна розмова"],
        12: ["Далі веде модель мислення «Зважена матриця рішень»"],
        17: ["«Зважена матриця рішень» не підійшла · далі вільна розмова"],
    }


def test_a_choice_and_an_end_in_one_reply_both_mark() -> None:
    routing = (_decision(5, "choose", "pre-mortem"), _decision(5, "end", "pre-mortem", "not_fit"))
    assert marks(routing, CARDS) == {
        6: ["Далі веде модель мислення «Pre-mortem»"],
        7: ["«Pre-mortem» не підійшла · далі вільна розмова"],
    }


def test_a_card_the_knowledge_no_longer_has_is_marked_by_its_id() -> None:
    assert marks((_decision(3, "choose", "five-whys"),), CARDS) == {
        4: ["Далі веде модель мислення «five-whys»"]
    }


# --- the workspace gives the routing; the page shows both ------------------------------------------------


class Script:
    """A Facilitate double: each call yields the planned items of the next answer."""

    def __init__(self, *answers: list[Any]) -> None:
        self.answers = list(answers)

    def __call__(self, ctx: Any) -> Any:
        return iter(self.answers.pop(0))


def _update(text: str, phase: str | None) -> FacilitatorUpdate:
    return FacilitatorUpdate(reply=text, current_phase_id=phase, phase_exit_met=False, map_updates=[])


def _conversation(store: LocalStorage) -> TopicRef:
    """Turn 1 → the router offers; turn 3 → the person chose, the matrix leads at its second phase."""
    ref = TopicRef(ALICE.id, create_topic(store, ALICE, "Яку квартиру взяти", T0))
    offer = [
        RoutingEvent(_decision(1, "offer")),
        ReplyDelta("Можна так або так."),
        _update("Можна так або так.", None),
    ]
    lead = [
        RoutingEvent(_decision(3, "choose", "weighted-matrix")),
        ReplyDelta("Які критерії для вас важливі?"),
        _update("Які критерії для вас важливі?", "criteria"),
    ]
    list(reply(store, Script(offer), ALICE, ref, "Дві квартири, не можу обрати.", T0))
    list(reply(store, Script(lead), ALICE, ref, "Давай перше.", T0))
    return ref


def test_open_topic_gives_the_routing_of_the_topic(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path / "data")
    ref = _conversation(store)
    view = open_topic(store, ALICE, ref, T0)
    assert [d.kind for d in view.routing] == ["offer", "choose"]
    assert view.problem_map.phase_id == "criteria"


def _client(tmp_path: Path, store: LocalStorage, cards: dict[str, Card]) -> TestClient:
    settings = load_settings({"THINKHOW_LOCAL": "true", "THINKHOW_LOCAL_DIR": str(tmp_path)})
    tokens = {"tok-alice": {"sub": "accounts.google.com:alice-1", "email": "alice@example.com"}}
    identity = IapIdentity("aud", lambda token, audience: tokens[token])
    speech = ScriptedSpeech("текст")
    deps = Deps(store, identity, settings, Script(), lambda: T0, speech, cards)
    return TestClient(create_app(deps), raise_server_exceptions=False)


def test_the_topic_page_shows_the_caption_and_the_mark_apart_from_the_replies(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path / "data")
    set_language(store, ALICE, "uk-UA")
    ref = _conversation(store)
    page = _client(tmp_path, store, CARDS).get(f"/topics/{ref.uid}/{ref.topic_id}", headers=HEADERS).text
    assert '<aside class="method"' in page
    assert "Зважена матриця рішень · 2 з 4" in page
    assert page.index("Далі веде модель мислення «Зважена матриця рішень»") < page.index('id="t4"')
    assert page.index('id="t3"') < page.index("Далі веде модель мислення")
    assert '<p class="text">Які критерії для вас важливі?</p>' in page


def test_a_new_topic_page_says_free_conversation(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path / "data")
    set_language(store, ALICE, "uk-UA")
    ref = TopicRef(ALICE.id, create_topic(store, ALICE, "Тема", T0))
    page = _client(tmp_path, store, CARDS).get(f"/topics/{ref.uid}/{ref.topic_id}", headers=HEADERS).text
    assert "вільна розмова" in page
    assert "Далі веде" not in page


def test_the_end_of_a_card_marks_the_next_turn_and_the_caption_is_free_again(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path / "data")
    set_language(store, ALICE, "uk-UA")
    ref = _conversation(store)
    summary = "Отже, критерії ясні."
    ended = [
        RoutingEvent(_decision(5, "end", "weighted-matrix", "done")),
        ReplyDelta(summary),
        _update(summary, None),
    ]
    offer = [RoutingEvent(_decision(7, "offer")), ReplyDelta("Що далі?"), _update("Що далі?", None)]
    list(reply(store, Script(ended), ALICE, ref, "Гроші й час.", T0))
    list(reply(store, Script(offer), ALICE, ref, "А тепер?", T0))
    page = _client(tmp_path, store, CARDS).get(f"/topics/{ref.uid}/{ref.topic_id}", headers=HEADERS).text
    mark = "«Зважена матриця рішень» пройдено · далі вільна розмова"
    assert page.index('id="t6"') < page.index(mark) < page.index('id="t7"')
    assert "Модель мислення:</span> вільна розмова" in page
