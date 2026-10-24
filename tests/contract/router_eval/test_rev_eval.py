"""Contract tests of `scripts/router_eval.py`: the context of a situation as the product builds it (Seam 2),
the measures (Seam 3), the aggregation of invalid / unavailable answers, and the request id of the log in the
pool (Seam 6) (slice router-eval; slice tester, from the contract — fakes of the model port, no model)."""

import time
from pathlib import Path
from typing import Any

import pytest
from rev_fakes import (
    CASES,
    ProductLlm,
    answer,
    invalid_raw,
    knowledge,
    offer_raw,
    routing_lines,
    script,
)

from thinkhow.facilitation import current_card
from thinkhow.platform.llm import LlmUnavailable


def ev() -> Any:
    return script("router_eval")


def case(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "x-1",
        "kind": "positive",
        "text": "Чому в нас падає кількість реєстрацій?",
        "expect": "five-whys",
        "also_ok": ["is-is-not"],
        "not_first": ["issue-tree"],
        "history": [],
        "absent": ["pre-mortem"],
    }
    base.update(over)
    return base


OTHER = case(
    id="o-1",
    kind="other",
    history=[
        {"role": "user", "text": "Обираю садочок із чотирьох."},
        {"role": "model", "text": "Можемо так: (1) порівняти; (2) подивитися ширше. Що ближче?"},
    ],
    offered=["weighted-matrix", "wrap-decision"],
    absent=["weighted-matrix", "wrap-decision"],
    text="Ні, це не те. Я вже обрала, але боюся помилитися.",
    expect="pre-mortem",
    also_ok=[],
    not_first=[],
)
MIDWAY = case(
    id="m-1",
    kind="midway",
    ended={"card_id": "five-whys", "end": "not_fit"},
    history=[
        {"role": "user", "text": "Чому в нас падає кількість реєстрацій?"},
        {"role": "model", "text": "Що саме змінилося перед тим, як почалося падіння?"},
        {"role": "user", "text": "Не знаю, все наче як було."},
        {"role": "model", "text": "Що для вас зараз найважливіше далі?"},
    ],
    text="Хочу подивитися, де саме це трапляється, а де ні.",
    expect="is-is-not",
    also_ok=[],
    not_first=[],
    absent=["five-whys"],
)


# --- the context of a situation -----------------------------------------------------------------------------


def test_routing_of_other_is_one_offer_of_the_offered_cards_in_their_order() -> None:
    decisions = ev().routing_of(OTHER)
    assert [d.kind for d in decisions] == ["offer"]
    assert [c.card_id for c in decisions[0].candidates] == ["weighted-matrix", "wrap-decision"]


def test_routing_of_midway_is_offer_with_the_card_first_then_choose_it_then_its_end() -> None:
    decisions = ev().routing_of(MIDWAY)
    assert [d.kind for d in decisions] == ["offer", "choose", "end"]
    assert decisions[0].candidates[0].card_id == "five-whys"
    assert decisions[1].card_id == "five-whys"
    assert (decisions[2].card_id, decisions[2].end) == ("five-whys", "not_fit")


def test_turns_of_the_decisions_do_not_decrease() -> None:
    for c in (OTHER, MIDWAY):
        turns = [d.turn for d in ev().routing_of(c)]
        assert turns == sorted(turns), (c["id"], turns)


def test_every_case_of_the_set_needs_the_router() -> None:
    for c in ev().load_cases(CASES):
        assert current_card(ev().routing_of(c)) is None, c["id"]


def test_context_has_the_history_the_turn_number_an_empty_map_the_text_and_uk_ua() -> None:
    ctx = ev().context_of(MIDWAY)
    assert [(t.role, t.text) for t in ctx.history] == [(h["role"], h["text"]) for h in MIDWAY["history"]]
    assert ctx.turn_no == 5
    assert ctx.problem_map.items == []
    assert ctx.problem_map.last_turn == 4
    assert ctx.text == MIDWAY["text"]
    assert ctx.language is not None and "uk-UA" in ctx.language
    assert [d.kind for d in ctx.routing] == ["offer", "choose", "end"]


def test_router_frame_of_every_other_case_has_one_offer_line_of_its_offered_cards(tmp_path: Path) -> None:
    others = [c for c in ev().load_cases(CASES) if c["kind"] == "other"]
    assert others
    llm = ProductLlm(router=lambda no, text: offer_raw("issue-tree", "scamper"))
    ev().run(others, knowledge(tmp_path), llm, workers=1)
    for c in others:
        frames = [k.frame for k in llm.router_calls if k.text == c["text"]]
        assert frames, c["id"]
        offers = [line for line in routing_lines(frames[0]) if " offer " in line]
        assert len(offers) == 1, (c["id"], offers)
        assert offers[0].endswith(f"offer {', '.join(c['offered'])} (запропоновано)"), offers


def test_router_frame_of_every_midway_case_has_offer_choose_end_in_this_order(tmp_path: Path) -> None:
    mids = [c for c in ev().load_cases(CASES) if c["kind"] == "midway"]
    assert mids
    llm = ProductLlm(router=lambda no, text: offer_raw("issue-tree", "scamper"))
    ev().run(mids, knowledge(tmp_path), llm, workers=1)
    for c in mids:
        frames = [k.frame for k in llm.router_calls if k.text == c["text"]]
        assert frames, c["id"]
        lines = routing_lines(frames[0])
        cid, end = c["ended"]["card_id"], c["ended"]["end"]
        at_offer = [i for i, ln in enumerate(lines) if f" offer {cid}" in ln]
        at_choose = [i for i, ln in enumerate(lines) if f" choose {cid}" in ln]
        at_end = [i for i, ln in enumerate(lines) if f" end {cid} — {end}" in ln]
        assert at_offer and at_choose and at_end, (c["id"], lines)
        assert at_offer[0] < at_choose[0] < at_end[0], (c["id"], lines)


# --- the measures (Seam 3) ----------------------------------------------------------------------------------


def test_offer_with_expect_first_is_first_ok_and_offered_ok() -> None:
    o = ev().measure(case(), answer("offer", ["five-whys", "issue-tree"]))
    assert o.action == "offer"
    assert o.first == "five-whys"
    assert set(o.offered) == {"five-whys", "issue-tree"}
    assert (o.first_ok, o.offered_ok, o.negative_ok, o.absent_ok) == (True, True, True, True)


def test_also_ok_first_counts_as_first_ok() -> None:
    o = ev().measure(case(), answer("offer", ["is-is-not", "five-whys"]))
    assert o.first == "is-is-not"
    assert o.first_ok is True
    assert o.offered_ok is True


def test_expect_second_is_offered_ok_but_not_first_ok() -> None:
    o = ev().measure(case(), answer("offer", ["scamper", "five-whys"]))
    assert o.first == "scamper"
    assert o.first_ok is False
    assert o.offered_ok is True
    assert o.negative_ok is True


def test_a_not_first_card_first_is_negative_not_ok() -> None:
    o = ev().measure(case(), answer("offer", ["issue-tree", "scamper"]))
    assert o.first == "issue-tree"
    assert o.negative_ok is False
    assert o.first_ok is False
    assert o.offered_ok is False


def test_an_absent_card_among_the_offered_is_absent_not_ok() -> None:
    o = ev().measure(case(), answer("offer", ["five-whys", "pre-mortem"]))
    assert o.absent_ok is False
    assert o.first_ok is True


def test_tie_also_ok_first_without_expect_is_first_ok_but_not_offered_ok() -> None:
    tie = case(kind="tie")
    o = ev().measure(tie, answer("offer", ["is-is-not", "scamper"]))
    assert o.first_ok is True
    assert o.offered_ok is False


def test_choose_first_is_its_card_and_it_counts_as_offered() -> None:
    o = ev().measure(case(), answer("choose", [], "five-whys"))
    assert o.action == "choose"
    assert o.first == "five-whys"
    assert "five-whys" in o.offered
    assert o.first_ok is True
    assert o.offered_ok is True


def test_ask_with_candidates_ranks_them_first_is_candidates_0() -> None:
    o = ev().measure(case(), answer("ask", ["issue-tree", "five-whys"]))
    assert o.action == "ask"
    assert o.first == "issue-tree"
    assert set(o.offered) == {"issue-tree", "five-whys"}
    assert o.first_ok is False
    assert o.offered_ok is True
    assert o.negative_ok is False


def test_ask_with_an_absent_candidate_is_absent_not_ok() -> None:
    o = ev().measure(case(), answer("ask", ["five-whys", "pre-mortem"]))
    assert o.absent_ok is False


def test_ask_without_candidates_has_no_first_and_is_neither_first_ok_nor_offered_ok() -> None:
    o = ev().measure(case(), answer("ask", []))
    assert o.first is None
    assert list(o.offered) == []
    assert o.first_ok is False
    assert o.offered_ok is False
    assert o.absent_ok is True


def test_invalid_outcome_is_a_miss() -> None:
    o = ev().invalid(case(), "the router's answer stayed invalid after one retry")
    assert o.action == "invalid"
    assert o.first is None
    assert o.first_ok is False
    assert o.offered_ok is False


def test_unavailable_outcome_is_marked_unavailable() -> None:
    o = ev().unavailable(case(), "LlmUnavailable")
    assert o.action == "unavailable"


# --- run: one call, failures, the request id ----------------------------------------------------------------


def test_run_makes_one_route_call_per_case(tmp_path: Path) -> None:
    cs = [case(id=f"r-{i}", text=f"Ситуація номер {i}: чому падають продажі?") for i in range(3)]
    llm = ProductLlm(router=lambda no, text: offer_raw("five-whys", "issue-tree"))
    outcomes = ev().run(cs, knowledge(tmp_path), llm, workers=1)
    assert len(llm.router_calls) == 3
    assert sorted(o.case_id for o in outcomes) == ["r-0", "r-1", "r-2"]
    assert all(o.first == "five-whys" and o.first_ok for o in outcomes)


def test_run_turns_facilitation_error_into_invalid_and_llm_unavailable_into_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(time, "sleep", lambda s: None)
    bad = case(id="bad-1", text="Перша ситуація: модель відповідає невалідно.")
    down = case(id="down-1", text="Друга ситуація: модель недоступна.")
    good = case(id="good-1", text="Третя ситуація: чому падають продажі?")

    def router(no: int, text: str) -> str:
        if text == bad["text"]:
            return invalid_raw()
        if text == down["text"]:
            raise LlmUnavailable("service down")
        return offer_raw("five-whys", "issue-tree")

    outcomes = ev().run([bad, down, good], knowledge(tmp_path), ProductLlm(router=router), workers=1)
    by_id = {o.case_id: o for o in outcomes}
    assert set(by_id) == {"bad-1", "down-1", "good-1"}
    assert by_id["bad-1"].action == "invalid"
    assert (by_id["bad-1"].first_ok, by_id["bad-1"].offered_ok) == (False, False)
    assert by_id["down-1"].action == "unavailable"
    assert by_id["good-1"].action == "offer" and by_id["good-1"].first_ok is True


def test_every_model_call_in_the_pool_carries_its_case_id_as_request_id(tmp_path: Path) -> None:
    cs = [case(id=f"p-{i}", text=f"Ситуація {i}: чому в нас падає кількість реєстрацій?") for i in range(6)]
    by_text = {c["text"]: c["id"] for c in cs}

    def router(no: int, text: str) -> str:
        time.sleep(0.02)
        return offer_raw("five-whys", "issue-tree")

    llm = ProductLlm(router=router)
    ev().run(cs, knowledge(tmp_path), llm, workers=2)
    assert len(llm.router_calls) == 6
    for call in llm.router_calls:
        assert call.request_id == by_text[call.text], (call.text, call.request_id)
