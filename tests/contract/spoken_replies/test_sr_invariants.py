"""Invariants I1-I2 of spoken-replies (slice tester; inputs chosen by hand from each «Domain»).

I1's oracle is `sr_oracle.py`: the strings of commit cefcb02, captured once, not rebuilt here from the same
pieces the code uses. Domain: a card without and with «Метод», memory empty and not, language None / a listed
one / a non-Latin one, `routed` both ways, every rule of the deep cycle; the router with two cards and
one."""

from dataclasses import replace
from typing import Any

from sr_fakes import (
    CARDS,
    DEEP_RULES,
    HEAD,
    KNOWLEDGES,
    LANGUAGES,
    LISTENING_HEAD,
    MEMORY,
    ScenarioLlm,
    answer_key,
    deep_key,
    knowledge,
    lead_answer,
    respond_key,
    route_key,
)
from sr_oracle import ORACLE

from thinkhow.facilitation import deep
from thinkhow.facilitation.answer import answer_instruction
from thinkhow.facilitation.respond import lead, system_instruction
from thinkhow.facilitation.route import router_instruction
from thinkhow.facilitation.types import FacilitationContext, MapItem, ProblemMap, Turn


def ctx(language: str | None, **flag: Any) -> FacilitationContext:
    return FacilitationContext(
        card_id="alpha",
        history=[Turn(role="user", text="Хочу відкрити кав'ярню.")],
        problem_map=ProblemMap(
            items=[MapItem(id="i1", type="plan", text="кав'ярня", turn="t1")], phase_id="a_one", last_turn=1
        ),
        turn_no=2,
        text="За пів року.",
        language=language,
        **flag,
    )


def all_four(spoken: bool | None) -> dict[str, str]:
    """Every instruction of the domain; `None` — called without the flag at all."""
    kw: dict[str, Any] = {} if spoken is None else {"spoken": spoken}
    got: dict[str, str] = {}
    for cid, card in CARDS.items():
        for mk, memory in (("empty", []), ("one", MEMORY)):
            for lang in LANGUAGES:
                for routed in (False, True):
                    got[respond_key(cid, mk, lang, routed)] = system_instruction(
                        card, memory, lang, routed, **kw
                    )
    for kk, cards in KNOWLEDGES.items():
        for lang in LANGUAGES:
            got[route_key(kk, lang)] = router_instruction(knowledge(cards), lang, **kw)
    for lang in LANGUAGES:
        got[answer_key(lang)] = answer_instruction(lang, **kw)
    for rule in DEEP_RULES:
        for lang in LANGUAGES:
            got[deep_key(rule, lang)] = deep._system(rule, ctx(lang, **kw))
    return got


def test_I1_without_the_flag_each_instruction_is_byte_equal_to_before() -> None:
    got = all_four(None)
    assert set(got) == set(ORACLE)
    for key, before in ORACLE.items():
        assert got[key] == before, key


def test_I2_with_the_flag_the_section_stands_once_after_the_language_section() -> None:
    got = all_four(True)
    assert set(got) == set(ORACLE)
    for key, text in got.items():
        assert text.count(LISTENING_HEAD) == 1, key
        assert text.index(HEAD) < text.index(LISTENING_HEAD), key

    # lead itself, alone and under the router (`ctx.routing` set): still exactly once
    for routing in (None, ()):
        llm = ScenarioLlm(deltas=["Питання?"], done_raw=lead_answer("Питання?", "a_one"))
        c = ctx(None, spoken=True)
        if routing is not None:
            c = replace(c, routing=routing)
        try:
            list(lead(c, knowledge(), llm))
        except NotImplementedError:
            raise
        except Exception:  # the routed schema may refuse the fake's answer; the system is recorded first
            pass
        system = llm.stream_systems[0]
        assert system.count(LISTENING_HEAD) == 1, routing
        assert system.index(HEAD) < system.index(LISTENING_HEAD), routing
