"""Contract tests of research-quick, `platform/llm.py`: grounding metadata in the stream (Seam 1), the search
tool only where it belongs (Seam 2), the journal, ScriptedLlm and make_llm
(slice tester; from the contract)."""

from collections.abc import Sequence
from typing import Any

import pytest
from pydantic import BaseModel
from rq_fakes import (
    LogCapture,
    Piece,
    SearchClient,
    api_error,
    has_search_tool,
    install_log_capture,
    meta,
    no_tools,
    vertex,
    web,
)

from thinkhow.platform.config import Settings
from thinkhow.platform.llm import Done, Found, ReplyDelta, ScriptedLlm, Source, Turn, make_llm


class Reply(BaseModel):
    reply: str
    phase: str


TURNS = [Turn(role="user", text="Не знаю, скільки коштує оренда офісу в Лейпцигу.")]
HEAD = '{"reply": "Оренда'
MID = " коштує від 15 євро"
TAIL = ' за метр.", "phase": "p1"}'
OK = HEAD + MID + TAIL
REPLY = "Оренда коштує від 15 євро за метр."


@pytest.fixture
def logs(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> LogCapture:
    return install_log_capture(monkeypatch, capsys)


def stream_done(plans: list[list[Any]], search: bool = True) -> tuple[Done, str, SearchClient]:
    llm, client = vertex(plans, search=search)
    items = list(llm.stream_json("sys", TURNS, Reply, None))
    done = [i for i in items if isinstance(i, Done)]
    assert len(done) == 1 and isinstance(items[-1], Done)
    text = "".join(i.text for i in items if isinstance(i, ReplyDelta))
    return done[0], text, client


A = Source("Ціни оренди", "https://a.example/rent")
B = Source("Ринок офісів", "https://b.example/offices")
C = Source("Статистика", "https://c.example/stats")


# ------------------------------------------------------------------ Seam 1


def test_seam1_found_is_the_union_of_all_chunks_without_repeats_in_first_appearance_order(
    logs: LogCapture,
) -> None:
    wa, wb, wc = web(A.url, A.title), web(B.url, B.title), web(C.url, C.title)
    full = meta(["оренда офісу Лейпциг", "ціни оренди Лейпциг"], [wa, wb])
    cases: dict[str, tuple[list[Any], Found]] = {
        "in the middle chunk": (
            [Piece(HEAD), Piece(MID, meta(["оренда офісу Лейпциг"], [wa])), Piece(TAIL)],
            Found(("оренда офісу Лейпциг",), (A,), None),
        ),
        "in the last chunk": (
            [Piece(HEAD), Piece(MID), Piece(TAIL, meta(["оренда офісу Лейпциг"], [wa, wb]))],
            Found(("оренда офісу Лейпциг",), (A, B), None),
        ),
        "queries in one chunk, sources in another": (
            [Piece(HEAD, meta(["оренда офісу Лейпциг"])), Piece(MID), Piece(TAIL, meta(None, [wb, wa]))],
            Found(("оренда офісу Лейпциг",), (B, A), None),
        ),
        "sources and queries in parts across chunks": (
            [
                Piece(HEAD, meta(["q-один"], [wc])),
                Piece(MID, meta(["q-два"], [wa])),
                Piece(TAIL, meta(["q-один", "q-три"], [wb, wc])),
            ],
            Found(("q-один", "q-два", "q-три"), (C, A, B), None),
        ),
        "the same full metadata in every chunk": (
            [Piece(HEAD, full), Piece(MID, full), Piece(TAIL, full)],
            Found(("оренда офісу Лейпциг", "ціни оренди Лейпциг"), (A, B), None),
        ),
    }
    for name, (plan, want) in cases.items():
        done, text, _ = stream_done([plan])
        assert text == REPLY, name
        assert done.found == want, name


def test_seam1_suggestions_html_is_the_last_non_empty_rendered_content(logs: LogCapture) -> None:
    wa = web(A.url, A.title)
    cases: list[tuple[list[Any], str]] = [
        (
            [
                Piece(HEAD, meta(["q"], [wa], "<div>перше</div>")),
                Piece(MID, meta(None, None, "<div>друге</div>")),
                Piece(TAIL),
            ],
            "<div>друге</div>",
        ),
        (
            [
                Piece(HEAD, meta(["q"], [wa], "<div>перше</div>")),
                Piece(MID, meta(["q"], [wa], "")),
                Piece(TAIL),
            ],
            "<div>перше</div>",
        ),
    ]
    for plan, want in cases:
        done, _, _ = stream_done([plan])
        assert done.found == Found(("q",), (A,), want)


def test_seam1_found_is_none_without_queries_and_sources_and_a_chunk_without_metadata_is_no_error(
    logs: LogCapture,
) -> None:
    plans: list[list[Any]] = [
        [Piece(HEAD), Piece(MID), Piece(TAIL)],
        [Piece(HEAD, meta(None, None, "<div>лише підказки</div>")), Piece(MID), Piece(TAIL)],
        [
            Piece(HEAD, meta([], [])),
            Piece(MID, meta(None, [web(None, "без адреси"), web("", "порожня")])),
            Piece(TAIL),
        ],
    ]
    for plan in plans:
        done, text, _ = stream_done([plan])
        assert text == REPLY
        assert done.found is None
    # the edge: queries alone, or sources alone, are already «found»
    alone: list[tuple[Any, Found]] = [
        (meta(["лише запит"]), Found(("лише запит",), (), None)),
        (meta(None, [web(A.url, A.title)]), Found((), (A,), None)),
    ]
    for gm, want in alone:
        done, _, _ = stream_done([[Piece(HEAD), Piece(MID, gm), Piece(TAIL)]])
        assert done.found == want


def test_seam1_a_source_is_a_web_chunk_with_a_non_empty_uri_titled_by_title_then_domain_then_url(
    logs: LogCapture,
) -> None:
    import google.genai.types as gt

    chunks = [
        web("https://t.example/1", "Назва", "t.example"),
        web("https://d.example/2", None, "d.example"),
        web("https://u.example/3", None, None),
        web(None, "без адреси", "x.example"),
        web("", "порожня адреса", "y.example"),
        gt.GroundingChunk(
            retrieved_context=gt.GroundingChunkRetrievedContext(uri="https://r.example", title="R")
        ),
    ]
    done, _, _ = stream_done([[Piece(HEAD, meta(["q"], chunks)), Piece(MID), Piece(TAIL)]])
    assert done.found == Found(
        ("q",),
        (
            Source("Назва", "https://t.example/1"),
            Source("d.example", "https://d.example/2"),
            Source("https://u.example/3", "https://u.example/3"),
        ),
        None,
    )


def test_seam1_an_attempt_that_failed_before_the_retry_leaves_nothing(logs: LogCapture) -> None:
    old = meta(["старий запит"], [web("https://old.example/x", "Старе")], "<div>старе</div>")
    failed: list[Any] = [Piece('{"', old), api_error(503)]
    done, text, client = stream_done([failed, [Piece(HEAD), Piece(MID), Piece(TAIL)]])
    assert len(client.calls) == 2
    assert text == REPLY
    assert done.found is None

    fresh = meta(["новий запит"], [web(B.url, B.title)])
    done, _, _ = stream_done([list(failed), [Piece(HEAD), Piece(MID, fresh), Piece(TAIL)]])
    assert done.found == Found(("новий запит",), (B,), None)


# ------------------------------------------------------------------ Seam 2


def test_seam2_stream_json_carries_enterprise_web_search_only_on_a_search_instance(logs: LogCapture) -> None:
    llm, client = vertex([[OK]], search=True)
    list(llm.stream_json("sys", TURNS, Reply, None))
    llm_off, client_off = vertex([[OK]], search=False)
    list(llm_off.stream_json("sys", TURNS, Reply, None))
    assert has_search_tool(client.calls[0])
    assert no_tools(client_off.calls[0])


# ------------------------------------------------------------------ the journal


def test_llm_call_has_search_and_the_number_of_queries(logs: LogCapture) -> None:
    searched = meta(["q-один", "q-два"], [web(A.url, A.title)])
    llm, _ = vertex([[Piece(HEAD), Piece(MID, searched), Piece(TAIL)], [OK], [OK]], search=True)
    list(llm.stream_json("sys", TURNS, Reply, None))
    list(llm.stream_json("sys", TURNS, Reply, None))
    llm.generate_json("sys", TURNS, Reply, None)
    off, _ = vertex([[OK]], search=False)
    list(off.stream_json("sys", TURNS, Reply, None))
    lines = logs.events("llm_call")
    assert len(lines) == 4
    assert [(line.get("search"), line.get("queries")) for line in lines] == [
        (True, 2),
        (True, 0),
        (False, 0),
        (False, 0),
    ]
    assert all(type(line["search"]) is bool and type(line["queries"]) is int for line in lines)


# ------------------------------------------------------------------ ScriptedLlm and make_llm

FOUND = Found(("скільки коштує оренда",), (A,), None)


class FoundRecorder:
    def __init__(self, found: Found | None) -> None:
        self.found = found
        self.calls: list[tuple[str, list[Turn], type[BaseModel]]] = []

    def __call__(self, system: str, contents: Sequence[Turn], schema: type[BaseModel]) -> Found | None:
        self.calls.append((system, list(contents), schema))
        return self.found


def script(system: str, contents: Sequence[Turn], schema: type[BaseModel]) -> str:
    return OK


def done_of(items: list[Any]) -> Done:
    assert isinstance(items[-1], Done)
    return items[-1]


def test_scripted_llm_puts_found_script_into_done_found_only_in_stream_json() -> None:
    rec = FoundRecorder(FOUND)
    llm = ScriptedLlm(script, found_script=rec)
    items = list(llm.stream_json("SYS", TURNS, Reply, None))
    assert done_of(items).found == FOUND
    assert rec.calls == [("SYS", TURNS, Reply)]
    assert llm.generate_json("SYS", TURNS, Reply, None) == Reply(reply=REPLY, phase="p1")
    assert len(rec.calls) == 1
    assert done_of(list(ScriptedLlm(script).stream_json("SYS", TURNS, Reply, None))).found is None


def test_make_llm_local_passes_found_script_only_with_search() -> None:
    on = make_llm(Settings(local=True), script, search=True, found_script=FoundRecorder(FOUND))
    assert done_of(list(on.stream_json("SYS", TURNS, Reply, None))).found == FOUND
    off = make_llm(Settings(local=True), script, found_script=FoundRecorder(FOUND))
    assert done_of(list(off.stream_json("SYS", TURNS, Reply, None))).found is None


def test_make_llm_outside_local_gives_the_search_tool_by_search(
    monkeypatch: pytest.MonkeyPatch, logs: LogCapture
) -> None:
    made: list[SearchClient] = []

    def factory(*args: Any, **kwargs: Any) -> SearchClient:
        client = SearchClient([[OK]])
        made.append(client)
        return client

    monkeypatch.setattr("google.genai.Client", factory)
    for search, want_tool in ((True, True), (False, False)):
        llm = make_llm(Settings(local=False), script, search=search, found_script=FoundRecorder(FOUND))
        list(llm.stream_json("SYS", TURNS, Reply, None))
        assert has_search_tool(made[-1].calls[0]) is want_tool
    llm = make_llm(Settings(local=False), script)
    list(llm.stream_json("SYS", TURNS, Reply, None))
    assert no_tools(made[-1].calls[0])
