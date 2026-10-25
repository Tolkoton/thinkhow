"""Block tests of research-in-conversation (task 303): one per line of «Inter-slice contracts», and the
acceptance criteria that can be shown locally (AC2, AC4).

Slice tester, mode `block`; from `.engine/architecture/feature/research-in-conversation.md` and the public
signatures, not the bodies. Every test drives two or more slices together through the seam its line names,
through `respond` (the app's Facilitate) and `workspace.reply`, or the web app. Expected values are written
by hand from the artifact and the sealed scenarios of the slices.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel
from ric_fakes import (
    ALICE,
    T0,
    TwoArgLlm,
    fa,
    facilitate,
    last_model_text,
    rdp,
    rq,
    say,
    sw,
    web_app,
)

from thinkhow.facilitation import respond
from thinkhow.facilitation.types import (
    FacilitatorUpdate,
    ReplyDelta,
    ResearchEvent,
    RoutingEvent,
    current_card,
)
from thinkhow.platform import llm as pl
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import Answered, open_topic
from thinkhow.workspace.conversation import normalize

# --- the scenario, by hand ---------------------------------------------------------------------------------

ASK_RENT = "Не знаю, скільки коштує оренда кав'ярні в Лейпцигу."
RENT_REPLY = "Оренда в центрі Лейпцига — від 15 євро за метр. Яка площа вам потрібна?"
RENT_DELTAS = ["Оренда в центрі Лейпцига — від 15 євро за метр. ", "Яка площа вам потрібна?"]
RENT_FOUND = pl.Found(
    ("оренда кав'ярня Лейпциг ціна", "Gewerbemiete Leipzig"),
    (pl.Source("Mietspiegel Leipzig", "https://m.example/miete"), pl.Source("IHK", "https://i.example/ihk")),
    "<div>підказки оренди</div>",
)
RENT_LINE = "\n\nДжерела: [Mietspiegel Leipzig](https://m.example/miete), [IHK](https://i.example/ihk)"
RENT_ENTRY = {
    "turn": 2,
    "depth": "quick",
    "queries": ["оренда кав'ярня Лейпциг ціна", "Gewerbemiete Leipzig"],
    "sources": [
        {"title": "Mietspiegel Leipzig", "url": "https://m.example/miete"},
        {"title": "IHK", "url": "https://i.example/ihk"},
    ],
    "suggestions_html": "<div>підказки оренди</div>",
    "question": None,
    "report": None,
}
RENT_FACT = {
    "op": "add",
    "id": "f1",
    "type": "fact",
    "text": "Оренда в центрі Лейпцига — від 15 €/м².",
    "turn": "t1",
}
RENT_FACT_ITEM = {k: v for k, v in RENT_FACT.items() if k != "op"}

PLAIN_REPLY = "Що для вас у цьому найважливіше?"

FA_ENTRY = {
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
FA_FACT = {
    "op": "add",
    "id": "f1",
    "type": "fact",
    "text": "Octavia Combi у Німеччині — від 33 000 €.",
    "turn": "t1",
}
FA_FACT_ITEM = {k: v for k, v in FA_FACT.items() if k != "op"}

SOURCES_ABC = [
    {"title": "Mittelstand Studie", "url": "https://a.example/mittelstand"},
    {"title": "Beratermarkt", "url": "https://b.example/markt"},
    {"title": "IHK Leipzig", "url": "https://c.example/ihk"},
]


def deep_entry(turn: int) -> dict[str, Any]:
    return {
        "turn": turn,
        "depth": "deep",
        "queries": list(rdp.QUERIES_ABC),
        "sources": SOURCES_ABC,
        "suggestions_html": "<div>підказки Б</div>",
        "question": rdp.DQ,
        "report": rdp.REPORT,
    }


def choose_alpha() -> str:
    raw: str = fa.router_raw("choose", card_id="alpha", why="людина обрала alpha")
    return raw


def card_raw(reply: str, updates: Sequence[dict[str, Any]] = (), deep_question: Any = None) -> str:
    if deep_question is None:
        raw: str = rdp.card_answer(reply, "a_one", False, list(updates))
    else:
        raw = rdp.card_answer(reply, "a_one", False, list(updates), deep_question=deep_question)
    return raw


def research(store: LocalStorage, ref: Any) -> list[dict[str, Any]] | None:
    entries: list[dict[str, Any]] | None = rq.read_research(store, ref)
    return entries


def raw_research(store: LocalStorage, ref: Any) -> bytes | None:
    data: bytes | None = rq.raw_research(store, ref)
    return data


def kinds(items: Sequence[Any]) -> list[str]:
    names = {
        ReplyDelta: "delta",
        FacilitatorUpdate: "update",
        ResearchEvent: "research",
        RoutingEvent: "routing",
    }
    return [names.get(type(x), type(x).__name__) for x in items]


# ------------------------------------------------------------------ Inter-slice contracts


# «Запечатані фейки Llm не змінюються … без `found` `lead` поводиться точно як досі»
def test_sealed_fake_shape_two_arg_done_no_search_text_leads_as_before_through_router_and_workspace(
    tmp_path: Path,
) -> None:
    store = LocalStorage(tmp_path)
    ref = rq.topic(store)
    llm = TwoArgLlm(
        streams=[(["Що для вас ", "у цьому найважливіше?"], card_raw(PLAIN_REPLY))],
        generate=[choose_alpha()],
    )
    got, shown = say(store, facilitate(llm), ref, "Хочу відкрити кав'ярню.")
    assert isinstance(got[-1], Answered), got[-1]
    assert llm.kinds == ["generate", "stream"]  # the router, then the card's one streamed call
    assert shown == PLAIN_REPLY
    assert last_model_text(store, ref) == PLAIN_REPLY
    assert "Джерела:" not in shown
    assert raw_research(store, ref) is None
    routing = fa.read_routing(store, ref)
    assert routing is not None and [(d.kind, d.card_id) for d in routing] == [("choose", "alpha")]


# «`ScriptedLlm(script, found_script=None)` бере «що знайдено» з функції-заготовки; без неї — `None`»
def test_scripted_llm_found_script_reaches_the_sources_line_and_research_json_without_it_nothing(
    tmp_path: Path,
) -> None:
    def script(system: str, contents: Sequence[pl.Turn], schema: type[BaseModel]) -> str:
        if "action" in schema.model_fields:
            return choose_alpha()
        return card_raw(RENT_REPLY, [RENT_FACT])

    def found_script(system: str, contents: Sequence[pl.Turn], schema: type[BaseModel]) -> pl.Found | None:
        return RENT_FOUND if "reply" in schema.model_fields and "action" not in schema.model_fields else None

    store = LocalStorage(tmp_path / "with")
    ref = rq.topic(store)
    got, shown = say(store, facilitate(pl.ScriptedLlm(script, found_script=found_script)), ref, ASK_RENT)
    assert isinstance(got[-1], Answered), got[-1]
    assert shown == RENT_REPLY + RENT_LINE
    assert last_model_text(store, ref) == normalize(RENT_REPLY + RENT_LINE)
    assert research(store, ref) == [RENT_ENTRY]
    assert RENT_FACT_ITEM in rq.read_map(store, ref)["items"]

    store = LocalStorage(tmp_path / "without")
    ref = rq.topic(store)
    got, shown = say(store, facilitate(pl.ScriptedLlm(script)), ref, ASK_RENT)
    assert isinstance(got[-1], Answered), got[-1]
    assert shown == RENT_REPLY
    assert raw_research(store, ref) is None


# «`found` є лише в екземпляра з пошуком … `llm_call` має `search` і `queries`»
def test_vertex_search_instance_found_flows_into_research_json_and_llm_call_has_search_and_queries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    cap = rq.install_log_capture(monkeypatch, capsys)
    raw = card_raw(RENT_REPLY, [RENT_FACT])
    pieces = rq.split_chunks(raw, 3)
    gm = rq.meta(
        ["оренда кав'ярня Лейпциг ціна", "Gewerbemiete Leipzig"],
        [rq.web("https://m.example/miete", "Mietspiegel Leipzig"), rq.web("https://i.example/ihk", "IHK")],
        "<div>підказки оренди</div>",
    )
    llm, client = rq.vertex(
        [[choose_alpha()], [rq.Piece(pieces[0]), rq.Piece(pieces[1]), rq.Piece(pieces[2], gm)]], search=True
    )
    store = LocalStorage(tmp_path)
    ref = rq.topic(store)
    got, shown = say(store, facilitate(llm), ref, ASK_RENT)
    assert isinstance(got[-1], Answered), got[-1]
    assert client.models.kinds == ["generate", "stream"]
    assert not rq.has_search_tool(client.calls[0])  # the router: generate_json never searches
    assert rq.has_search_tool(client.calls[1])
    assert shown == RENT_REPLY + RENT_LINE
    assert research(store, ref) == [RENT_ENTRY]
    calls = cap.events("llm_call")
    assert [(c["search"], c["queries"]) for c in calls] == [(False, 0), (True, 2)]


# «`ResearchEvent` іде в потоці `Facilitate` **перед** `FacilitatorUpdate`» — the card's path and «answer»
def test_research_event_comes_before_the_update_on_the_card_path_and_on_the_answer_path() -> None:
    lead_llm = rdp.deep_llm(
        streams=[rdp.Stream(list(RENT_DELTAS), card_raw(RENT_REPLY, [RENT_FACT]), RENT_FOUND)]
    )
    items = list(respond(rq.context(routing=rq.ROUTED), rq.knowledge(), lead_llm))
    assert kinds(items) == ["delta", "delta", "delta", "research", "update"]
    assert [x.text for x in items if isinstance(x, ReplyDelta)] == [*RENT_DELTAS, RENT_LINE]
    (event,) = [x for x in items if isinstance(x, ResearchEvent)]
    assert (event.depth, event.queries, event.question, event.report) == (
        "quick",
        ("оренда кав'ярня Лейпциг ціна", "Gewerbemiete Leipzig"),
        None,
        None,
    )
    assert isinstance(items[-1], FacilitatorUpdate)
    assert items[-1].reply == RENT_REPLY + RENT_LINE

    answer_llm = rdp.deep_llm(
        router=[fa.answer_raw()],
        streams=[rdp.Stream(list(fa.DELTAS), fa.fact_raw(updates=[FA_FACT]), fa.FOUND)],
    )
    items = list(respond(rq.context(routing=()), fa.knowledge(), answer_llm))
    assert kinds(items) == ["routing", "delta", "delta", "delta", "research", "update"]
    assert isinstance(items[-1], FacilitatorUpdate)
    assert items[-1].reply == fa.REPLY + fa.LINE
    assert items[-1].current_phase_id is None


# «`workspace._answer` збирає їх і після запису відповіді дописує в `research.json` з `turn` = номер відповіді
# моделі; без подій файл не чіпає» — quick (S1), a turn without search, deep (S3) in one topic
def test_one_topic_quick_then_no_search_then_deep_entries_keep_the_model_turns_and_the_file_is_left_alone(
    tmp_path: Path,
) -> None:
    store = LocalStorage(tmp_path)
    ref = rq.topic(store)
    llm = rdp.deep_llm(
        router=[choose_alpha()],
        streams=[
            rdp.Stream(list(RENT_DELTAS), card_raw(RENT_REPLY, [RENT_FACT]), RENT_FOUND),
            rdp.Stream([PLAIN_REPLY], card_raw(PLAIN_REPLY)),
            rdp.Stream(["Досліджую глибше."], card_raw("Досліджую глибше.", deep_question=rdp.DQ)),
        ],
        plans=[rdp.plan_raw()],
        reports=[rdp.report_raw()],
    )
    fac = facilitate(llm)
    got, _ = say(store, fac, ref, ASK_RENT)
    assert isinstance(got[-1], Answered) and got[-1].turn_no == 2, got[-1]
    assert research(store, ref) == [RENT_ENTRY]
    before = raw_research(store, ref)

    got, _ = say(store, fac, ref, "Площа — метрів сорок.")
    assert isinstance(got[-1], Answered) and got[-1].turn_no == 4, got[-1]
    assert raw_research(store, ref) == before

    got, shown = say(store, fac, ref, "Так, досліди глибоко, як купує Mittelstand.")
    assert isinstance(got[-1], Answered) and got[-1].turn_no == 6, got[-1]
    assert research(store, ref) == [RENT_ENTRY, deep_entry(6)]
    assert shown.endswith("\n\n" + rdp.REPORT + rdp.LINE_ABC)
    assert len(llm.of("search")) == 3


# «одна функція «джерела під відповіддю» … той самий текст іде в потік і в `reply`, тож показане наживо =
# записане в `conversation.md`» — on the three paths: the card (S1), «answer» (S2), deep (S3)
def test_the_sources_line_shown_live_is_the_one_recorded_on_the_card_answer_and_deep_paths(
    tmp_path: Path,
) -> None:
    # the card's path
    store = LocalStorage(tmp_path / "card")
    ref = rq.topic(store)
    rq.put_routing(store, ref, [rq.d_choose(1, "alpha")])
    llm = rdp.deep_llm(streams=[rdp.Stream(list(RENT_DELTAS), card_raw(RENT_REPLY, [RENT_FACT]), RENT_FOUND)])
    _, shown = say(store, facilitate(llm), ref, ASK_RENT)
    assert shown == RENT_REPLY + RENT_LINE
    assert last_model_text(store, ref) == normalize(shown)

    # the router's «answer»
    store = LocalStorage(tmp_path / "answer")
    ref = rq.topic(store)
    llm = rdp.deep_llm(
        router=[fa.answer_raw()],
        streams=[rdp.Stream(list(fa.DELTAS), fa.fact_raw(updates=[FA_FACT]), fa.FOUND)],
    )
    _, shown = say(store, facilitate(llm, fa.knowledge()), ref, fa.QUESTION)
    assert shown == fa.REPLY + fa.LINE
    assert last_model_text(store, ref) == normalize(shown)

    # deep, on the router's «answer» with a deep question
    store = LocalStorage(tmp_path / "deep")
    ref = rq.topic(store)
    llm = rdp.full_deep(router=[rdp.with_deep_question(fa.answer_raw(), rdp.DQ)])
    _, shown = say(store, facilitate(llm, fa.knowledge()), ref, "Так, досліди глибоко.")
    assert shown.endswith("\n\n" + rdp.REPORT + rdp.LINE_ABC)
    assert shown.count("Джерела: ") == 1
    assert last_model_text(store, ref) == normalize(shown)


# «якщо потоковий JSON невалідний, `_settle` повторює через `generate_json` (без пошуку); `Found` першого
# виклику зберігається і рядок джерел дописується до відповіді повтору»
def test_an_invalid_stream_is_retried_without_search_and_the_first_calls_found_stays_with_its_line(
    tmp_path: Path,
) -> None:
    store = LocalStorage(tmp_path)
    ref = rq.topic(store)
    rq.put_routing(store, ref, [rq.d_choose(1, "alpha")])
    truncated = '{"reply": "Оренда в центрі Лейпцига — від 15 євро за метр. Яка площа'
    llm = rdp.deep_llm(
        streams=[rdp.Stream(list(RENT_DELTAS), truncated, RENT_FOUND)],
        updates=[rdp.card_update("a_one")],
    )
    got, shown = say(store, facilitate(llm), ref, ASK_RENT)
    assert isinstance(got[-1], Answered), got[-1]
    assert [c.kind for c in llm.calls] == ["stream", "update"]
    assert llm.of("search") == []
    assert shown == RENT_REPLY + RENT_LINE
    assert last_model_text(store, ref) == normalize(RENT_REPLY + RENT_LINE)
    assert research(store, ref) == [RENT_ENTRY]


# «після `answered` сторінка перезавантажується … і показує `TopicView.research`» — links clickable too
def test_after_answered_the_topic_view_and_page_show_the_suggestions_and_the_clickable_sources(
    tmp_path: Path,
) -> None:
    llm = rdp.deep_llm(
        router=[choose_alpha()],
        streams=[rdp.Stream(list(RENT_DELTAS), card_raw(RENT_REPLY, [RENT_FACT]), RENT_FOUND)],
    )
    app = web_app(tmp_path, facilitate(llm))
    sw.choose_language(app.storage, ALICE)
    ref = rq.topic(app.storage)
    url = f"/topics/{ref.uid}/{ref.topic_id}"
    stream = app.client.post(f"{url}/reply", data={"text": ASK_RENT}, headers=sw.H_ALICE)
    events = sw.sse_events(stream.text)
    assert events[-1] == ("answered", {"turn": 2})
    assert "".join(d["text"] for n, d in events if n == "delta") == RENT_REPLY + RENT_LINE

    view = open_topic(app.storage, ALICE, ref, T0)
    assert [(r.turn, r.suggestions_html) for r in view.research] == [(2, "<div>підказки оренди</div>")]

    page = sw.Page(app.client.get(url, headers=sw.H_ALICE).text)
    iframes = [a for t, a in page.tags if t == "iframe"]
    assert len(iframes) == 1 and "підказки оренди" in (iframes[0].get("srcdoc") or "")
    assert iframes[0].get("sandbox") is not None
    hrefs = [a.get("href") for t, a in page.tags if t == "a"]
    assert "https://m.example/miete" in hrefs and "https://i.example/ihk" in hrefs


# S2: «`Decision.kind` += `"answer"` … `current_card` не змінюється (останнє `answer` → роутер знову на
# наступній репліці)»
def test_after_a_fact_answer_the_router_comes_again_and_a_choice_then_leads_the_card(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = rq.topic(store)
    llm = rdp.deep_llm(
        router=[fa.answer_raw(), choose_alpha()],
        streams=[
            rdp.Stream(list(fa.DELTAS), fa.fact_raw(updates=[FA_FACT]), fa.FOUND),
            rdp.Stream([PLAIN_REPLY], card_raw(PLAIN_REPLY)),
        ],
    )
    fac = facilitate(llm, fa.knowledge())
    say(store, fac, ref, fa.QUESTION)
    routing = fa.read_routing(store, ref)
    assert routing is not None and [(d.kind, d.card_id, d.turn) for d in routing] == [("answer", None, 1)]
    assert current_card(routing) is None

    _, shown = say(store, fac, ref, "Добре, допоможіть мені обрати між двома варіантами.")
    assert [c.kind for c in llm.calls] == ["router", "stream", "router", "stream"]
    assert fa.ASK_TAIL not in llm.of("router")[1].contents[-1].text
    assert shown == PLAIN_REPLY
    routing = fa.read_routing(store, ref)
    assert routing is not None and [(d.kind, d.card_id, d.turn) for d in routing] == [
        ("answer", None, 1),
        ("choose", "alpha", 3),
    ]
    assert current_card(routing) == "alpha"
    assert research(store, ref) == [FA_ENTRY]


# ------------------------------------------------------------------ Acceptance criteria shown locally


# AC2: «Пряме фактичне питання («скільки коштує …») — відповідь з джерелом, без ведення моделлю мислення.»
def test_ac2_a_direct_price_question_through_the_web_is_answered_with_sources_and_no_card_is_led(
    tmp_path: Path,
) -> None:
    llm = rdp.deep_llm(
        router=[fa.answer_raw()],
        streams=[rdp.Stream(list(fa.DELTAS), fa.fact_raw(updates=[FA_FACT]), fa.FOUND)],
    )
    app = web_app(tmp_path, facilitate(llm, fa.knowledge()))
    sw.choose_language(app.storage, ALICE)
    ref = rq.topic(app.storage)
    url = f"/topics/{ref.uid}/{ref.topic_id}"
    events = sw.sse_events(
        app.client.post(f"{url}/reply", data={"text": fa.QUESTION}, headers=sw.H_ALICE).text
    )
    assert events[-1] == ("answered", {"turn": 2})
    assert "".join(d["text"] for n, d in events if n == "delta") == fa.REPLY + fa.LINE
    system = llm.of("stream")[0].system
    for c in fa.CARDS:
        assert c.facilitator.purpose not in system
    assert rq.read_map(app.storage, ref)["phase_id"] is None
    assert FA_FACT_ITEM in rq.read_map(app.storage, ref)["items"]
    routing = fa.read_routing(app.storage, ref)
    assert routing is not None and [d.kind for d in routing] == ["answer"]
    hrefs = [a.get("href") for t, a in sw.Page(app.client.get(url, headers=sw.H_ALICE).text).tags if t == "a"]
    assert "https://a.example/preis" in hrefs and "https://b.example/o" in hrefs


# AC4: «Результати досліджень лягають у тему поруч із розмовою з джерелами і пам'ятаються між розмовами.»
def test_ac4_what_was_found_stays_in_the_topic_and_the_next_session_s_call_carries_the_fact(
    tmp_path: Path,
) -> None:
    store = LocalStorage(tmp_path)
    ref = rq.topic(store)
    llm = rdp.deep_llm(
        router=[fa.answer_raw(), fa.offer_raw("alpha", "beta")],
        streams=[rdp.Stream(list(fa.DELTAS), fa.fact_raw(updates=[FA_FACT]), fa.FOUND)],
    )
    fac = facilitate(llm, fa.knowledge())
    say(store, fac, ref, fa.QUESTION)
    later = T0 + timedelta(hours=25)  # a new conversation: more than 24 h of silence
    got, _ = say(store, fac, ref, "Я повернувся: думаю, чи брати машину взагалі.", now=later)
    assert isinstance(got[-1], Answered) and got[-1].turn_no == 4, got[-1]

    view = open_topic(store, ALICE, ref, later)
    assert len(view.sessions) == 2
    assert view.sessions[0].turns[-1].text == normalize(fa.REPLY + fa.LINE)
    assert [(r.turn, r.suggestions_html) for r in view.research] == [(2, "<div>підказки</div>")]
    assert research(store, ref) == [FA_ENTRY]
    assert FA_FACT_ITEM in [i.model_dump() for i in view.problem_map.items]
    second_router = llm.of("router")[1]
    assert FA_FACT["text"] in "\n".join(t.text for t in second_router.contents)
    assert json.loads(json.dumps(FA_FACT_ITEM)) in rq.read_map(store, ref)["items"]
