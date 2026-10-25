"""Contract tests of fact-answer through `workspace.reply`: the whole `answer` path with the files it writes
(Seam 1), the answer without search (Q8) and the router again on the next turn (Seam 2)
(slice tester; from the contract)."""

from functools import partial
from pathlib import Path
from typing import Any

from fa_fakes import (
    ALICE,
    ANSWER_LINE_1,
    ASK_TAIL,
    DELTAS,
    EMPTY_FOUND,
    FOUND,
    LINE,
    OFFER_REPLY,
    QUESTION,
    REPLY,
    ROUTER_REPLY,
    T0,
    FaLlm,
    Stream,
    answer_raw,
    context,
    fact_raw,
    knowledge,
    no_lead,
    offer_raw,
    read_json,
    read_routing,
    topic,
)

from thinkhow.facilitation import ResearchEvent, converse, respond
from thinkhow.facilitation.types import FacilitatorUpdate, ReplyDelta
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import Answered, Delta, open_topic, reply

FACT1 = {
    "op": "add",
    "id": "i1",
    "type": "fact",
    "text": "Octavia Combi у Німеччині — від 33 000 €.",
    "turn": "t1",
}
FACT1_ITEM = {"id": "i1", "type": "fact", "text": "Octavia Combi у Німеччині — від 33 000 €.", "turn": "t1"}


def facilitate(llm: FaLlm) -> Any:
    return partial(respond, knowledge=knowledge(), llm=llm)


def say(store: LocalStorage, fac: Any, ref: Any, text: str) -> tuple[list[Any], str]:
    got = list(reply(store, fac, ALICE, ref, text, T0))
    assert isinstance(got[-1], Answered), got[-1]
    return got, "".join(e.text for e in got if isinstance(e, Delta))


def conversation_texts(store: LocalStorage, ref: Any) -> list[str]:
    return [t.text for s in open_topic(store, ALICE, ref, T0).sessions for t in s.turns]


def test_seam1_through_workspace_reply_answer_writes_routing_research_map_and_the_shown_answer(
    tmp_path: Path,
) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    llm = FaLlm(
        generate=[answer_raw(("alpha",))], streams=[Stream(list(DELTAS), fact_raw(updates=[FACT1]), FOUND)]
    )
    _, shown = say(store, facilitate(llm), ref, QUESTION)
    recorded = open_topic(store, ALICE, ref, T0).sessions[-1].turns[-1].text
    assert shown == recorded == REPLY + LINE
    assert all(ROUTER_REPLY not in t for t in conversation_texts(store, ref))
    routing = read_routing(store, ref)
    assert routing is not None and len(routing) == 1
    assert (routing[0].kind, routing[0].card_id, routing[0].turn) == ("answer", None, 1)
    assert read_json(store, ref, "research.json") == {
        "entries": [
            {
                "turn": 2,
                "depth": "quick",
                "queries": ["Škoda Octavia Combi ціна Німеччина"],
                "sources": [
                    {"title": "Preisliste Octavia", "url": "https://a.example/preis"},
                    {"title": "Autobild", "url": "https://b.example/o"},
                ],
                "suggestions_html": "<div>підказки</div>",
                "question": None,
                "report": None,
            }
        ]
    }
    assert FACT1_ITEM in read_json(store, ref, "map.json")["items"]


def test_seam1_q8_without_found_no_sources_line_no_research_and_the_fact_item_stays(tmp_path: Path) -> None:
    for i, found in enumerate((None, EMPTY_FOUND)):
        llm = FaLlm(generate=[answer_raw()], streams=[Stream(list(DELTAS), fact_raw(updates=[FACT1]), found)])
        items: list[Any] = list(converse(context((), turn_no=1, history=[]), knowledge(), llm, no_lead))
        assert not any(isinstance(x, ResearchEvent) for x in items), found
        assert [x.text for x in items if isinstance(x, ReplyDelta)] == DELTAS, found
        (update,) = [x for x in items if isinstance(x, FacilitatorUpdate)]
        assert update.reply == REPLY and update.current_phase_id is None, found
        assert [u.type for u in update.map_updates] == ["fact"], found

        store = LocalStorage(tmp_path / str(i))
        ref = topic(store)
        llm = FaLlm(generate=[answer_raw()], streams=[Stream(list(DELTAS), fact_raw(updates=[FACT1]), found)])
        _, shown = say(store, facilitate(llm), ref, QUESTION)
        recorded = open_topic(store, ALICE, ref, T0).sessions[-1].turns[-1].text
        assert shown == recorded == REPLY, found
        assert "Джерела:" not in recorded
        assert store.read("users", f"{ref.uid}/{ref.topic_id}/research.json") is None, found
        assert FACT1_ITEM in read_json(store, ref, "map.json")["items"], found
        routing = read_routing(store, ref)
        assert routing is not None and [d.kind for d in routing] == ["answer"]


def test_seam2_after_answer_the_next_turn_is_led_by_the_router_whose_frame_names_the_answer(
    tmp_path: Path,
) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    llm = FaLlm(
        generate=[answer_raw(), offer_raw("alpha", "beta")],
        streams=[Stream(list(DELTAS), fact_raw(updates=[FACT1]), FOUND)],
    )
    fac = facilitate(llm)
    say(store, fac, ref, QUESTION)
    first = len(llm.calls)
    assert [c.kind for c in llm.calls] == ["generate", "stream"]
    _, shown = say(store, fac, ref, "А що з цього важливо, якщо я ще думаю, чи брати її взагалі?")
    later = llm.calls[first:]
    assert len(later) == 1 and later[0].is_router
    frame = later[0].contents[-1].text
    assert ANSWER_LINE_1 in frame.split("\n")
    assert ASK_TAIL not in frame
    assert "[Репліка людини #3]" in frame
    assert shown == OFFER_REPLY
    routing = read_routing(store, ref)
    assert routing is not None
    assert [(d.kind, d.turn) for d in routing] == [("answer", 1), ("offer", 3)]
