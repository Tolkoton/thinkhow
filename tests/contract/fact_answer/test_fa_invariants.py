"""Contract tests of fact-answer, the invariants I1–I3, each over hand-chosen inputs of its «Domain»
(slice tester; from the contract)."""

from pathlib import Path
from typing import Any

from fa_fakes import (
    ALPHA,
    BETA,
    CARDS,
    DELTAS,
    EMPTY_FOUND,
    FACT,
    FACT_RETRY,
    FOUND,
    INVALID_WITH_OTHER_REPLY,
    ITEM,
    LINE,
    PREMORTEM,
    REPLY,
    TRUNCATED,
    FaLlm,
    Stream,
    answer_raw,
    card_texts,
    context,
    d_answer,
    d_choose,
    d_end,
    d_offer,
    fact_raw,
    fact_update_raw,
    flat,
    knowledge,
    no_lead,
    offer_raw,
)

import thinkhow.facilitation as facilitation_pkg
from thinkhow.facilitation import answer_fact, converse
from thinkhow.facilitation.types import (
    Decision,
    FacilitatorUpdate,
    MapItem,
    ProblemMap,
    ReplyDelta,
    RoutingEvent,
    current_card,
)
from thinkhow.platform import llm as pl

RULES_MD = Path(facilitation_pkg.__file__).with_name("rules.md").read_text(encoding="utf-8")
OTHER = "Новий Octavia Combi коштує від 33 000 євро, універсал — від 34 500. Що для вас тут важливо далі?"


def decision_of(items: list[Any]) -> Decision:
    (event,) = [i for i in items if isinstance(i, RoutingEvent)]
    return event.decision


def test_I1_after_an_answer_there_is_no_card_and_the_next_turn_is_led_by_the_router() -> None:
    k = knowledge()
    priors: list[tuple[Decision, ...]] = [
        (),
        (d_offer(1, "alpha", "beta"),),
        (d_choose(1, "alpha"), d_end(1, "alpha", "done")),
        (d_offer(1, "alpha", "beta"), d_choose(3, "beta"), d_end(3, "beta", "not_fit")),
        (d_answer(1),),
    ]
    for prior in priors:
        llm = FaLlm(
            generate=[answer_raw(("alpha", "beta"))], streams=[Stream(list(DELTAS), fact_raw(), FOUND)]
        )
        items: list[Any] = list(converse(context(prior, turn_no=5), k, llm, no_lead))
        decision = decision_of(items)
        assert decision.kind == "answer" and decision.card_id is None, prior
        assert [c.kind for c in llm.calls] == ["generate", "stream"], prior
        sequences = [(*prior, decision)]
        if prior:
            sequences.append((*prior[:-1], decision))
        for routing in sequences:
            assert current_card(routing) is None, routing
            nxt = FaLlm(generate=[offer_raw("alpha", "beta")])
            later: list[Any] = list(
                converse(context(routing, text="А дизельний?", turn_no=7), k, nxt, no_lead)
            )
            assert len(nxt.calls) == 1 and nxt.calls[0].is_router, routing
            assert decision_of(later).kind == "offer", routing
    # an answer straight after a choose (the card is closed only by the answer being last)
    routing = (d_choose(1, "alpha"), d_answer(3))
    assert current_card(routing) is None
    nxt = FaLlm(generate=[offer_raw("alpha", "beta")])
    list(converse(context(routing, turn_no=5), k, nxt, no_lead))
    assert len(nxt.calls) == 1 and nxt.calls[0].is_router


def test_I2_on_the_answer_path_the_streamed_text_equals_the_recorded_reply_with_the_sources_line() -> None:
    queries_only = pl.Found(("Octavia Combi Preis",), (), None)
    chars = list(REPLY)
    cases: list[tuple[str, Stream, list[str], str]] = [
        ("valid, found", Stream(list(DELTAS), fact_raw(), FOUND), [], REPLY + LINE),
        ("valid, no found", Stream(list(DELTAS), fact_raw(), None), [], REPLY),
        ("valid, empty found", Stream(list(DELTAS), fact_raw(), EMPTY_FOUND), [], REPLY),
        ("valid, queries only", Stream(list(DELTAS), fact_raw(), queries_only), [], REPLY),
        ("valid, one char a delta", Stream(chars, fact_raw(), FOUND), [], REPLY + LINE),
        ("valid, nothing shown", Stream([], fact_raw(OTHER), FOUND), [], OTHER + LINE),
        (
            "invalid with shown, other reply in raw",
            Stream(list(DELTAS), INVALID_WITH_OTHER_REPLY, FOUND),
            [fact_update_raw()],
            REPLY + LINE,
        ),
        ("invalid with shown, no found", Stream(list(DELTAS), TRUNCATED, None), [fact_update_raw()], REPLY),
        (
            "invalid with shown, empty found",
            Stream(chars, TRUNCATED, EMPTY_FOUND),
            [fact_update_raw()],
            REPLY,
        ),
        ("invalid without shown, found", Stream([], TRUNCATED, FOUND), [fact_raw(OTHER)], OTHER + LINE),
        (
            "invalid without shown, no found",
            Stream([], TRUNCATED, None),
            [fact_raw(OTHER, [FACT_RETRY])],
            OTHER,
        ),
    ]
    for name, stream, generate, expected in cases:
        llm = FaLlm(streams=[stream], generate=list(generate))
        items: list[Any] = list(answer_fact(context(), knowledge(), llm))
        shown = "".join(i.text for i in items if isinstance(i, ReplyDelta))
        (update,) = [i for i in items if isinstance(i, FacilitatorUpdate)]
        assert shown == update.reply == expected, name
        assert isinstance(items[-1], FacilitatorUpdate), name
        assert update.current_phase_id is None and update.phase_exit_met is False, name
        assert [u.id for u in update.map_updates] == ["i2"], name
    assert FACT["id"] == FACT_RETRY["id"] == "i2"


def test_I3_the_fact_answer_instruction_has_no_facilitator_rules_and_no_card_text() -> None:
    rule_lines = [flat(line) for line in RULES_MD.split("\n") if len(line.strip()) >= 20]
    assert rule_lines
    maps = [
        ProblemMap(),
        ProblemMap(items=[ITEM], phase_id="a_one", last_turn=2),
        ProblemMap(
            items=[ITEM, MapItem(id="i2", type="threat", text="Заголовок картки alpha", turn="t2")],
            phase_id="pm_one",
            last_turn=2,
        ),
    ]
    variants = [
        (knowledge(), None, maps[0], "pre-mortem"),
        (knowledge(), "Polski (pl-PL)", maps[1], "alpha"),
        (knowledge((PREMORTEM,), rev=1, n=1), "English (en-US)", maps[1], "pre-mortem"),
        (knowledge((), rev=9, n=0), None, maps[0], "alpha"),
        (knowledge((ALPHA, BETA), rev=12, n=30), "Українська (uk-UA)", maps[2], "beta"),
    ]
    for k, language, pm, card_id in variants:
        llm = FaLlm(streams=[Stream(list(DELTAS), fact_raw(), FOUND)])
        list(answer_fact(context(pm=pm, language=language, card_id=card_id), k, llm))
        (call,) = llm.stream_calls
        system = flat(call.system)
        for line in rule_lines:
            assert line not in system, (language, card_id, line)
        assert "Ти — фасилітатор ThinkHow" not in system
        for c in CARDS:
            for text in card_texts(c):
                assert text not in system, (language, card_id, text)
        assert "# Картка" not in call.system
