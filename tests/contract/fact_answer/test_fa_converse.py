"""Contract tests of fact-answer, `facilitation`: `converse` on `answer` (Seam 1), the fact answer's
instruction and frame (Seam 3), its one streamed call, the retry of an invalid answer (Seam 4) and its
errors (slice tester; from the contract)."""

import json
from typing import Any

import pytest
from fa_fakes import (
    ANSWER_MD,
    CARD_RETRY_ASK,
    DELTAS,
    FACT,
    FACT_RETRY,
    FACT_RETRY_ASK,
    FOUND,
    FREE_MODE_LINE,
    HISTORY,
    INVALID_WITH_OTHER_REPLY,
    ITEM,
    LINE,
    QUESTION,
    REPLY,
    ROUTER_REPLY,
    RULE_PL,
    TRUNCATED,
    FaLlm,
    Stream,
    answer_raw,
    context,
    d_choose,
    d_end,
    fact_raw,
    fact_update_raw,
    flat,
    knowledge,
    no_lead,
)

from thinkhow.facilitation import FacilitationError, answer_fact, converse
from thinkhow.facilitation.respond import RESEARCH_SECTION
from thinkhow.facilitation.types import (
    FacilitatorUpdate,
    FactAnswer,
    MapUpdate,
    ProblemMap,
    ReplyDelta,
    ResearchEvent,
    RoutingEvent,
    Source,
)
from thinkhow.platform import llm as pl

SOURCES = (Source("Preisliste Octavia", "https://a.example/preis"), Source("Autobild", "https://b.example/o"))


def kinds(items: list[Any]) -> list[str]:
    return [type(i).__name__ for i in items]


def texts(items: list[Any]) -> list[str]:
    return [i.text for i in items if isinstance(i, ReplyDelta)]


def fact_update(reply: str, *updates: dict[str, Any]) -> FacilitatorUpdate:
    return FacilitatorUpdate(
        reply=reply,
        current_phase_id=None,
        phase_exit_met=False,
        map_updates=[MapUpdate.model_validate(u) for u in updates],
    )


def test_seam1_converse_on_answer_gives_the_decision_then_the_fact_answer_sources_research_and_update() -> (
    None
):
    llm = FaLlm(generate=[answer_raw(("alpha",))], streams=[Stream(list(DELTAS), fact_raw(), FOUND)])
    items: list[Any] = list(converse(context(()), knowledge(), llm, no_lead))
    assert kinds(items) == [
        "RoutingEvent",
        "ReplyDelta",
        "ReplyDelta",
        "ReplyDelta",
        "ResearchEvent",
        "FacilitatorUpdate",
    ]
    event = items[0]
    assert isinstance(event, RoutingEvent)
    d = event.decision
    assert (d.kind, d.card_id, d.turn, d.end) == ("answer", None, 3, None)
    assert [c.card_id for c in d.candidates] == ["alpha"]
    assert texts(items) == [*DELTAS, LINE]
    ev = items[4]
    assert isinstance(ev, ResearchEvent)
    assert (ev.depth, ev.queries, ev.sources, ev.suggestions_html) == (
        "quick",
        ("Škoda Octavia Combi ціна Німеччина",),
        SOURCES,
        "<div>підказки</div>",
    )
    assert items[-1] == fact_update(REPLY + LINE, FACT)
    assert all(ROUTER_REPLY not in t for t in texts(items))
    assert ROUTER_REPLY not in items[-1].reply
    assert [c.kind for c in llm.calls] == ["generate", "stream"]
    assert llm.calls[0].is_router


def test_seam3_the_instruction_is_answer_md_then_the_language_rule_then_the_facts_section() -> None:
    llm = FaLlm(streams=[Stream(list(DELTAS), fact_raw(), FOUND)])
    list(answer_fact(context(language="Polski (pl-PL)"), knowledge(), llm))
    (call,) = llm.stream_calls
    system = call.system
    assert flat(system).startswith(flat(ANSWER_MD))
    assert "\n\n# Мова відповіді\n" + RULE_PL + "\n\n" + RESEARCH_SECTION in system
    assert system.rstrip("\n").endswith(RESEARCH_SECTION)
    assert system.count("# Факти про світ") == 1
    assert system.count("# Мова відповіді") == 1
    assert "фасилітатор ThinkHow" not in system
    assert "# Картка" not in system
    assert "Заголовок картки" not in system


def test_seam3_the_frame_is_the_history_then_the_map_and_the_turn_without_any_state_line() -> None:
    routing = (d_choose(1, "alpha"), d_end(1, "alpha", "not_fit"))
    pm = ProblemMap(items=[ITEM], phase_id=None, last_turn=2)
    llm = FaLlm(streams=[Stream(list(DELTAS), fact_raw(), FOUND)])
    list(answer_fact(context(routing, pm=pm, turn_no=3), knowledge(), llm))
    (call,) = llm.stream_calls
    assert call.contents[:-1] == [pl.Turn(t.role, t.text) for t in HISTORY]
    last = call.contents[-1]
    assert last.role == "user"
    head = "[Карта проблеми зараз]\n"
    tail = "\n\n[Репліка людини #3]\n" + QUESTION
    assert last.text.startswith(head) and last.text.endswith(tail)
    map_json = last.text[len(head) : len(last.text) - len(tail)]
    assert json.loads(map_json) == {
        "items": [{"id": "i1", "type": "goal", "text": "купити машину", "turn": "t1"}],
        "phase_id": None,
        "last_turn": 2,
    }
    assert "[Стан" not in last.text
    assert FREE_MODE_LINE not in last.text


def test_answer_fact_is_one_streamed_call_with_the_fact_answer_schema_and_the_revision() -> None:
    llm = FaLlm(streams=[Stream(list(DELTAS), fact_raw(), None)])
    items: list[Any] = list(answer_fact(context(), knowledge(rev=4, n=9), llm))
    (call,) = llm.calls
    assert call.kind == "stream"
    assert call.schema is FactAnswer
    assert call.rev == pl.KnowledgeRev(rev=4, n=9)
    assert items == [ReplyDelta(DELTAS[0]), ReplyDelta(DELTAS[1]), fact_update(REPLY, FACT)]


def test_seam4_invalid_stream_after_shown_text_retries_only_the_map_changes_with_the_fact_retry_ask() -> None:
    llm = FaLlm(
        streams=[Stream(list(DELTAS), INVALID_WITH_OTHER_REPLY, FOUND)],
        generate=[fact_update_raw()],
    )
    items: list[Any] = list(answer_fact(context(), knowledge(), llm))
    stream, retry = llm.calls
    assert (stream.kind, retry.kind) == ("stream", "generate")
    assert set(retry.schema.model_fields) == {"map_updates"}
    assert retry.system == stream.system
    assert retry.contents[-1].role == "user" and retry.contents[-1].text == FACT_RETRY_ASK
    assert all(t.text != CARD_RETRY_ASK for t in retry.contents)
    assert retry.contents[: len(stream.contents)] == stream.contents
    assert kinds(items) == ["ReplyDelta", "ReplyDelta", "ReplyDelta", "ResearchEvent", "FacilitatorUpdate"]
    assert texts(items) == [*DELTAS, LINE]
    assert items[-1] == fact_update(REPLY + LINE, FACT_RETRY)


def test_seam4_invalid_stream_without_shown_text_retries_the_full_fact_answer() -> None:
    llm = FaLlm(streams=[Stream([], TRUNCATED, FOUND)], generate=[fact_raw()])
    items: list[Any] = list(answer_fact(context(), knowledge(), llm))
    stream, retry = llm.calls
    assert (stream.kind, retry.kind) == ("stream", "generate")
    assert set(retry.schema.model_fields) == {"reply", "map_updates"}
    assert retry.system == stream.system and retry.contents == stream.contents
    assert kinds(items) == ["ReplyDelta", "ReplyDelta", "ResearchEvent", "FacilitatorUpdate"]
    assert texts(items) == [REPLY, LINE]
    assert items[-1] == fact_update(REPLY + LINE, FACT)


def test_errors_on_answer_as_in_lead_unavailable_passes_up_and_invalid_twice_is_a_facilitation_error() -> (
    None
):
    down = FaLlm(generate=[answer_raw()], streams=[pl.LlmUnavailable("model down")])
    with pytest.raises(pl.LlmUnavailable):
        list(converse(context(()), knowledge(), down, no_lead))
    shown = FaLlm(generate=[answer_raw(), TRUNCATED], streams=[Stream(list(DELTAS), TRUNCATED, FOUND)])
    with pytest.raises(FacilitationError):
        list(converse(context(()), knowledge(), shown, no_lead))
    blank = FaLlm(generate=[answer_raw(), TRUNCATED], streams=[Stream([], TRUNCATED, FOUND)])
    with pytest.raises(FacilitationError):
        list(converse(context(()), knowledge(), blank, no_lead))
    assert [c.kind for c in blank.calls] == ["generate", "stream", "generate"]
