"""Contract tests of research-display, `platform/llm.py`: the links are resolved in `VertexLlm` before `Done`
(Seam 1), `resolve_sources` in parallel with the order kept (Seam 3), `make_llm` wiring the resolver
(slice tester; from the contract)."""

import threading
import time
from typing import Any

import httpx
import pytest
from pydantic import BaseModel
from rd_fakes import GOOGLE, RecordingResolve
from rq_fakes import (
    Piece,
    SearchClient,
    Sleeps,
    answer,
    context,
    install_log_capture,
    knowledge,
    meta,
    split_chunks,
    web,
)

from thinkhow.facilitation import FacilitatorUpdate, ReplyDelta, ResearchEvent
from thinkhow.facilitation.respond import lead
from thinkhow.platform import llm as pl
from thinkhow.platform.config import Settings

G1 = GOOGLE + "AUZIYQ-rent"
G2 = GOOGLE + "AUZIYQ-market"
P1 = "https://a.example/rent"
P2 = "https://b.example/m"
HTML = '<style>.chip{}</style><a class="chip" href="' + GOOGLE + 's1">оренда</a>'
REPLY = "Оренда офісу в Лейпцигу коштує від 15 євро за метр. Скільки метрів вам треба?"
LINE = "\n\nДжерела: [Ціни оренди](https://a.example/rent), [Ринок](https://b.example/m)"


class Reply(BaseModel):
    reply: str
    phase: str


TURNS = [pl.Turn(role="user", text="Не знаю, скільки коштує оренда офісу в Лейпцигу.")]
OK = '{"reply": "Оренда коштує від 15 євро за метр.", "phase": "p1"}'


def grounded_plan(raw: str) -> list[Any]:
    pieces = split_chunks(raw, 3)
    gm = meta(["оренда офісу Лейпциг"], [web(G1, "Ціни оренди"), web(G2, "Ринок")], HTML)
    return [Piece(pieces[0]), Piece(pieces[1]), Piece(pieces[2], gm)]


def vertex(plans: list[list[Any]], resolve: Any) -> pl.VertexLlm:
    client = SearchClient(plans)
    return pl.VertexLlm(
        client, "gemini-4-argon", 300.0, 3, sleep=Sleeps(), clock=lambda: 10.0, search=True, resolve=resolve
    )


def only_done(items: list[Any]) -> pl.Done:
    done = [i for i in items if isinstance(i, pl.Done)]
    assert len(done) == 1 and items[-1] is done[0]
    return done[0]


@pytest.fixture(autouse=True)
def quiet_journal(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    install_log_capture(monkeypatch, capsys)


# ------------------------------------------------------------------ Seam 1


def test_seam1_vertex_resolves_the_sources_before_done_and_lead_streams_the_resolved_line() -> None:
    resolve = RecordingResolve({G1: P1, G2: P2})
    llm = vertex([grounded_plan(OK)], resolve)
    done = only_done(list(llm.stream_json("sys", TURNS, Reply, None)))
    assert done.found == pl.Found(
        ("оренда офісу Лейпциг",), (pl.Source("Ціни оренди", P1), pl.Source("Ринок", P2)), HTML
    )
    assert sorted(resolve.calls) == sorted([G1, G2])

    resolve2 = RecordingResolve({G1: P1, G2: P2})
    items = list(lead(context(), knowledge(), vertex([grounded_plan(answer(REPLY, "a_one"))], resolve2)))
    deltas = [i.text for i in items if isinstance(i, ReplyDelta)]
    assert "".join(deltas) == REPLY + LINE
    assert LINE in deltas
    (ev,) = [i for i in items if isinstance(i, ResearchEvent)]
    assert [(s.title, s.url) for s in ev.sources] == [("Ціни оренди", P1), ("Ринок", P2)]
    last = items[-1]
    assert isinstance(last, FacilitatorUpdate) and last.reply == REPLY + LINE
    assert sorted(resolve2.calls) == sorted([G1, G2])

    # no grounding metadata: found stays None and resolve is not called
    resolve3 = RecordingResolve({})
    done3 = only_done(list(vertex([[Piece(OK)]], resolve3).stream_json("sys", TURNS, Reply, None)))
    assert done3.found is None
    assert resolve3.calls == []


def test_seam1_vertex_without_resolve_keeps_the_links_as_in_s1() -> None:
    llm = vertex([grounded_plan(OK)], None)
    done = only_done(list(llm.stream_json("sys", TURNS, Reply, None)))
    assert done.found == pl.Found(
        ("оренда офісу Лейпциг",), (pl.Source("Ціни оренди", G1), pl.Source("Ринок", G2)), HTML
    )


# ------------------------------------------------------------------ Seam 3


def test_seam3_resolve_sources_runs_in_parallel_keeps_order_and_collapses_repeats() -> None:
    u1, u2, u3 = GOOGLE + "one", GOOGLE + "two", GOOGLE + "three"
    started = {u: threading.Event() for u in (u1, u2, u3)}
    overlapped: dict[str, bool] = {}
    finished: list[str] = []
    lock = threading.Lock()

    def before(url: str) -> None:
        started[url].set()
        if url in (u1, u2):
            # waits for the third call to have started: true only when the calls run at the same time
            overlapped[url] = started[u3].wait(timeout=2.0)
            if url == u1:
                time.sleep(0.2)
        with lock:
            finished.append(url)

    resolve = RecordingResolve({u1: P1, u2: P2, u3: P1}, before=before)
    sources = [pl.Source("Перше", u1), pl.Source("Друге", u2), pl.Source("Третє", u3)]
    got = pl.resolve_sources(sources, resolve)
    assert overlapped == {u1: True, u2: True}, "the calls of resolve did not run in parallel"
    assert finished[-1] == u1, finished
    assert got == (pl.Source("Перше", P1), pl.Source("Друге", P2))
    assert sorted(resolve.calls) == sorted([u1, u2, u3])


# ------------------------------------------------------------------ make_llm


class FakeResponse:
    def __init__(self, status_code: int, location: str | None) -> None:
        self.status_code = status_code
        self.headers = httpx.Headers({"location": location} if location is not None else {})


def script(system: str, contents: Any, schema: Any) -> str:
    return OK


def test_make_llm_outside_local_with_search_resolves_through_httpx_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    heads: list[tuple[Any, Any]] = []

    def fake_head(*args: Any, **kwargs: Any) -> FakeResponse:
        heads.append((args, kwargs))
        url = args[0] if args else kwargs["url"]
        return FakeResponse(302, {G1: P1, G2: P2}[url])

    monkeypatch.setattr("google.genai.Client", lambda *a, **k: SearchClient([grounded_plan(OK)]))
    monkeypatch.setattr(httpx, "head", fake_head)
    llm = pl.make_llm(Settings(local=False), script, search=True)
    done = only_done(list(llm.stream_json("sys", TURNS, Reply, None)))
    assert done.found is not None
    assert [s.url for s in done.found.sources] == [P1, P2]
    assert len(heads) == 2
    assert all(k.get("follow_redirects") is False and k.get("timeout") == 3.0 for _, k in heads), heads
