"""Invariant tests of skel-facilitation (slice tester; inputs chosen by hand from each «Domain»)."""

from functools import partial
from pathlib import Path

import yaml
from skelf_fakes import (
    ALPHA,
    BETA,
    ScenarioLlm,
    answer,
    answer_reply_last,
    card,
    collect,
    context,
    knowledge,
    update_only,
)

from thinkhow.facilitation import FacilitationError, FacilitatorUpdate, ReplyDelta, respond
from thinkhow.knowledge import Card
from thinkhow.platform import llm as pl

ROOT = Path(__file__).resolve().parents[3]


def _scenarios() -> list[tuple[str, ScenarioLlm, str]]:
    """(name, fake, the text the person must end up seeing), one per kind of the I1 domain."""
    return [
        (
            "valid, reply first",
            ScenarioLlm(
                deltas=["Уявіть: ", "минув рік. ", "Що сталося?"],
                done_raw=answer("Уявіть: минув рік. Що сталося?", "a_one"),
            ),
            "Уявіть: минув рік. Що сталося?",
        ),
        (
            "valid, reply not first",
            ScenarioLlm(deltas=[], done_raw=answer_reply_last("Що стало причиною?", "a_two")),
            "Що стало причиною?",
        ),
        (
            "invalid with deltas (the Done JSON's reply differs from what was shown)",
            ScenarioLlm(
                deltas=["Що ", "сталося?"],
                done_raw='{"reply": "Що сталося? І ще", "current_phase_id": "a_one", "phase_exit_met": tr',
                generate=[update_only("a_one", True)],
            ),
            "Що сталося?",
        ),
        (
            "invalid without deltas",
            ScenarioLlm(
                deltas=[],
                done_raw=answer_reply_last("Інший текст?", "b_one"),
                generate=[answer("Який перший сигнал?", "a_three")],
            ),
            "Який перший сигнал?",
        ),
    ]


def test_I1_joined_deltas_equal_the_update_reply() -> None:
    for name, fake, seen in _scenarios():
        items, exc = collect(partial(respond, context(), knowledge(), fake))
        assert exc is None, name
        deltas = [i for i in items if isinstance(i, ReplyDelta)]
        updates = [i for i in items if isinstance(i, FacilitatorUpdate)]
        assert len(updates) == 1, name
        assert "".join(d.text for d in deltas) == updates[0].reply == seen, name


def test_I2_exactly_one_update_and_it_is_last_or_an_exception() -> None:
    cases = [fake for _, fake, _ in _scenarios()]
    cases += [
        # LlmUnavailable in the middle of the stream
        ScenarioLlm(
            deltas=["Що ", pl.LlmUnavailable("broke"), "сталося?"], done_raw=answer("Що сталося?", "a_one")
        ),
        # LlmUnavailable before any delta
        ScenarioLlm(deltas=[pl.LlmUnavailable("down")], done_raw=answer("Що?", "a_one")),
        # LlmUnavailable on the update-only retry, after shown text
        ScenarioLlm(deltas=["Що?"], done_raw=answer("Що?", "b_one"), generate=[pl.LlmUnavailable("down")]),
        # LlmUnavailable on the full retry
        ScenarioLlm(deltas=[], done_raw="{", generate=[pl.LlmUnavailable("down")]),
        # both the stream and the retry invalid
        ScenarioLlm(deltas=["Що?"], done_raw=answer("Що?", "b_one"), generate=[update_only("b_one")]),
        ScenarioLlm(deltas=[], done_raw="{", generate=["{"]),
    ]
    raised = 0
    for n, fake in enumerate(cases):
        items, exc = collect(partial(respond, context(), knowledge(), fake))
        updates = [i for i in items if isinstance(i, FacilitatorUpdate)]
        if exc is None:
            assert len(updates) == 1, n
            assert items[-1] is updates[0], n
        else:
            raised += 1
            assert updates == [], n
    assert raised == 6


def test_I3_current_phase_is_always_a_phase_of_the_chosen_card() -> None:
    real = Card.model_validate(
        yaml.safe_load((ROOT / "cards" / "pre-mortem.yaml").read_text(encoding="utf-8"))
    )
    single = card("solo", ["only"])
    many = card("many", ["p1", "p2", "p3", "p4", "p5", "p6", "p7"])
    real_phases = [p.id for p in real.facilitator.phases]
    cards = [ALPHA, BETA, single, many, real]
    for chosen in cards:
        own = [p.id for p in chosen.facilitator.phases]
        foreign = next(
            p
            for c in cards
            if c.id != chosen.id
            for p in (x.id for x in c.facilitator.phases)
            if p not in own
        )
        cases = [
            ScenarioLlm(deltas=["Що?"], done_raw=answer("Що?", own[-1])),
            ScenarioLlm(deltas=[], done_raw=answer_reply_last("Що?", own[0])),
            # a foreign phase in the stream, a lawful one in the update-only retry
            ScenarioLlm(deltas=["Що?"], done_raw=answer("Що?", foreign), generate=[update_only(own[0])]),
            # a foreign phase in the stream and again in the update-only retry
            ScenarioLlm(deltas=["Що?"], done_raw=answer("Що?", foreign), generate=[update_only(foreign)]),
            # a foreign phase with no deltas, then again in the full retry
            ScenarioLlm(
                deltas=[], done_raw=answer_reply_last("Що?", foreign), generate=[answer("Що?", foreign)]
            ),
            # a phase id no card has
            ScenarioLlm(
                deltas=["Що?"],
                done_raw=answer("Що?", "phase_1_time_travel_x"),
                generate=[update_only(own[-1])],
            ),
        ]
        for n, fake in enumerate(cases):
            items, exc = collect(partial(respond, context(card_id=chosen.id), knowledge(cards), fake))
            updates = [i for i in items if isinstance(i, FacilitatorUpdate)]
            if n in (3, 4):
                assert isinstance(exc, FacilitationError), (chosen.id, n)
                assert updates == [], (chosen.id, n)
            else:
                assert exc is None, (chosen.id, n, exc)
                assert len(updates) == 1 and updates[0].current_phase_id in own, (chosen.id, n)
    assert real_phases
