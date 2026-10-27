"""spoken-replies: with the flag, the section stands right after «# Мова відповіді» in each of the four
instructions, and the callers pass `ctx.spoken` (slice tester; Seam 2 of «Hardest seams»).

The expected strings are the pre-slice oracle (`sr_oracle.py`, captured at cefcb02) with
`"\\n" + LISTENING_SECTION + "\\n"` put at the point the contract names: right after the `language_rule(...)`
line and its `\\n`, before the `\\n` of the next section (in `deep` — at the end)."""

from sr_fakes import (
    ALPHA,
    BETA,
    CARDS,
    DEEP_RULES,
    HEAD,
    KNOWLEDGES,
    LANGUAGES,
    MEMORIES,
    MEMORY,
    ScenarioLlm,
    answer_key,
    deep_key,
    drain,
    fact_answer,
    knowledge,
    lead_answer,
    respond_key,
    route_key,
    router_ask,
)
from sr_oracle import ORACLE

from thinkhow.facilitation import deep
from thinkhow.facilitation.answer import answer_fact, answer_instruction
from thinkhow.facilitation.language import LISTENING_SECTION
from thinkhow.facilitation.respond import lead, system_instruction
from thinkhow.facilitation.route import route, router_instruction
from thinkhow.facilitation.types import FacilitationContext, MapItem, ProblemMap, Turn


def spliced(before: str) -> str:
    """The pre-slice string with the section inserted after the language line and its newline."""
    rule_start = before.index(HEAD) + len(HEAD)
    at = before.index("\n", rule_start) + 1
    return before[:at] + "\n" + LISTENING_SECTION + "\n" + before[at:]


def ctx(language: str | None, spoken: bool, card_id: str = "alpha") -> FacilitationContext:
    return FacilitationContext(
        card_id=card_id,
        history=[Turn(role="user", text="Хочу відкрити кав'ярню."), Turn(role="model", text="Який план?")],
        problem_map=ProblemMap(
            items=[MapItem(id="i1", type="plan", text="кав'ярня", turn="t1")], phase_id="a_one", last_turn=1
        ),
        turn_no=3,
        text="За пів року.",
        language=language,
        spoken=spoken,
    )


def test_system_instruction_spoken_puts_section_after_language_rule() -> None:
    for cid, card in CARDS.items():
        for mk, memory in MEMORIES.items():
            for lang in LANGUAGES:
                for routed in (False, True):
                    got = system_instruction(card, memory, lang, routed, spoken=True)
                    assert got == spliced(ORACLE[respond_key(cid, mk, lang, routed)]), (cid, mk, lang, routed)


def test_router_instruction_spoken_puts_section_before_cards_head() -> None:
    for kk, cards in KNOWLEDGES.items():
        for lang in LANGUAGES:
            got = router_instruction(knowledge(cards), lang, spoken=True)
            assert got == spliced(ORACLE[route_key(kk, lang)]), (kk, lang)


def test_answer_instruction_spoken_puts_section_before_research_section() -> None:
    for lang in LANGUAGES:
        assert answer_instruction(lang, spoken=True) == spliced(ORACLE[answer_key(lang)]), lang


def test_deep_system_spoken_appends_section_for_each_rule() -> None:
    for rule in DEEP_RULES:
        for lang in LANGUAGES:
            before = ORACLE[deep_key(rule, lang)]
            got = deep._system(rule, ctx(lang, True))
            assert got == before + "\n" + LISTENING_SECTION + "\n", (rule, lang)
            assert got == spliced(before), (rule, lang)


def test_lead_passes_ctx_spoken() -> None:
    for spoken in (True, False):
        llm = ScenarioLlm(deltas=["Pytanie?"], done_raw=lead_answer("Pytanie?", "a_one"))
        drain(lead(ctx("Polski (pl-PL)", spoken), knowledge(memory=MEMORY), llm))
        before = ORACLE[respond_key("alpha", "one", "Polski (pl-PL)", False)]
        assert llm.stream_systems[0] == (spliced(before) if spoken else before), spoken


def test_route_passes_ctx_spoken() -> None:
    for spoken in (True, False):
        llm = ScenarioLlm(generate=[router_ask()])
        route(ctx(None, spoken), knowledge((ALPHA, BETA)), llm)
        before = ORACLE[route_key("both", None)]
        assert llm.generate_systems[0] == (spliced(before) if spoken else before), spoken


def test_answer_fact_passes_ctx_spoken() -> None:
    for spoken in (True, False):
        llm = ScenarioLlm(deltas=["Близько 300 євро."], done_raw=fact_answer("Близько 300 євро."))
        drain(answer_fact(ctx("日本語 (ja-JP)", spoken), knowledge(), llm))
        before = ORACLE[answer_key("日本語 (ja-JP)")]
        assert llm.stream_systems[0] == (spliced(before) if spoken else before), spoken
