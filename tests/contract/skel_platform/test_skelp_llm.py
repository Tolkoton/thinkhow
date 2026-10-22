"""Contract tests of skel-platform: llm.py (slice tester; written from the contract, not the code)."""

import json
from typing import Any

import httpx
import httpx2
import pytest
from pydantic import BaseModel, ValidationError
from skelp_fakes import Clock, FakeGenaiClient, LogCapture, Sleeps, api_error, cfg_get, install_log_capture

from thinkhow.platform.config import Settings
from thinkhow.platform.llm import (
    Done,
    KnowledgeRev,
    LlmUnavailable,
    ReplyDelta,
    ScriptedLlm,
    Turn,
    VertexLlm,
    make_llm,
)


class Reply(BaseModel):
    reply: str
    phase: str


class PhaseFirst(BaseModel):
    phase: str
    reply: str


TURNS = [Turn(role="user", text="хочу відкрити кав'ярню")]
OK_JSON = '{"reply": "Яку локацію ви пригледіли?", "phase": "p1"}'

# (raw JSON as the model streams it, the reply written out by hand)
CASES: list[tuple[str, str]] = [
    ('{"reply": "", "phase": "p1"}', ""),
    ('{"reply": "Привіт, світе! Як справи?", "phase": "p1"}', "Привіт, світе! Як справи?"),
    (
        '{"reply": "q \\" bs \\\\ nl \\n tab \\t sl \\/ u \\u0410\\u0431 pair \\ud83d\\ude00 end", '
        '"phase": "p2"}',
        'q " bs \\ nl \n tab \t sl / u Аб pair \U0001f600 end',
    ),
    (
        '{"reply": "literal \U0001f600 і \U0001f9ed кирилиця", "phase": "p1"}',
        "literal \U0001f600 і \U0001f9ed кирилиця",
    ),
    ('{\n  "reply" : "pretty \\"x\\"",\n  "phase": "p1"\n}', 'pretty "x"'),
    ('  {"reply":"tight","phase":"p1"}', "tight"),
    ('{"reply": "ends with backslash \\\\", "phase": "p1"}', "ends with backslash \\"),
    ('{"reply": "a}b,c:d \\"reply\\": {", "phase": "p1"}', 'a}b,c:d "reply": {'),
    ('{"reply": "\\\\\\"", "phase": "p1"}', '\\"'),
]


def vertex(
    plans: list[list[Any]], attempts: int = 3, timeout_s: float = 300.0
) -> tuple[VertexLlm, FakeGenaiClient, Sleeps]:
    client = FakeGenaiClient(plans)
    sleeps = Sleeps()
    llm = VertexLlm(client, "gemini-4-argon", timeout_s, attempts, sleep=sleeps, clock=Clock())
    return llm, client, sleeps


def split(items: list[ReplyDelta | Done]) -> tuple[str, list[Done]]:
    text = "".join(i.text for i in items if isinstance(i, ReplyDelta))
    return text, [i for i in items if isinstance(i, Done)]


def collect_until_error(llm: VertexLlm) -> tuple[list[ReplyDelta | Done], BaseException | None]:
    got: list[ReplyDelta | Done] = []
    try:
        for item in llm.stream_json("sys", TURNS, Reply, None):
            got.append(item)
    except Exception as exc:  # noqa: BLE001
        return got, exc
    return got, None


@pytest.fixture
def logs(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> LogCapture:
    return install_log_capture(monkeypatch, capsys)


# ------------------------------------------------------------------ Seam 1 / I1


def test_I1_joined_reply_deltas_equal_the_reply_however_the_stream_is_cut(logs: LogCapture) -> None:
    for raw, expected in CASES:
        assert json.loads(raw)["reply"] == expected  # the hand-written value is the JSON's own
        # ScriptedLlm: every chunk size, 1 character included
        for size in range(1, len(raw) + 1):
            items = list(
                ScriptedLlm(lambda s, c, m, raw=raw: raw, chunk=size).stream_json("sys", TURNS, Reply, None)
            )
            text, done = split(items)
            assert text == expected, (raw, size)
            assert len(done) == 1 and isinstance(items[-1], Done)
            assert json.loads(done[0].raw_json) == json.loads(raw)
        # VertexLlm: one cut at every position, and every character its own chunk
        cuts = [[raw[:i], raw[i:]] for i in range(1, len(raw))] + [list(raw)]
        for pieces in cuts:
            llm, _, _ = vertex([pieces])
            items = list(llm.stream_json("sys", TURNS, Reply, None))
            text, done = split(items)
            assert text == expected, (raw, pieces)
            assert len(done) == 1 and isinstance(items[-1], Done)
            assert json.loads(done[0].raw_json) == json.loads(raw)


# ------------------------------------------------------------------ ScriptedLlm


def test_scripted_stream_gives_reply_deltas_then_one_done_and_records_the_call() -> None:
    raw = '{"reply": "Що для вас означає успіх цього плану?", "phase": "p1"}'
    llm = ScriptedLlm(lambda s, c, m: raw)
    items = list(llm.stream_json("SYS", TURNS, Reply, KnowledgeRev(1, 2)))
    deltas = [i for i in items if isinstance(i, ReplyDelta)]
    assert len(deltas) >= 2  # chunks of 7 characters: the reply arrives in pieces
    assert "".join(d.text for d in deltas) == "Що для вас означає успіх цього плану?"
    assert [type(i) for i in items].count(Done) == 1 and isinstance(items[-1], Done)
    assert llm.calls == [("SYS", TURNS, Reply)]


def test_make_llm_local_is_the_scripted_double() -> None:
    seen: list[str] = []

    def script(system: str, contents: object, schema: type[BaseModel]) -> str:
        seen.append(system)
        return OK_JSON

    llm = make_llm(Settings(local=True), script)
    assert isinstance(llm, ScriptedLlm)
    assert llm.generate_json("S", TURNS, Reply, None) == Reply(reply="Яку локацію ви пригледіли?", phase="p1")
    assert seen == ["S"]


# ------------------------------------------------------------------ both implementations


def test_reply_not_first_gives_no_delta_and_a_whole_done(logs: LogCapture) -> None:
    raws = [
        '{"phase": "p1", "reply": "late"}',
        '{"phase": "say \\"reply\\": \\"x\\"", "reply": "late"}',
        '{"meta": {"reply": "inner"}, "reply": "late"}',
    ]
    for raw in raws:
        items = list(
            ScriptedLlm(lambda s, c, m, raw=raw: raw, chunk=1).stream_json("sys", TURNS, PhaseFirst, None)
        )
        assert not [i for i in items if isinstance(i, ReplyDelta)], raw
        assert len(items) == 1 and isinstance(items[0], Done)
        assert json.loads(items[0].raw_json) == json.loads(raw)
        llm, _, _ = vertex([[raw[i : i + 3] for i in range(0, len(raw), 3)]])
        items = list(llm.stream_json("sys", TURNS, PhaseFirst, None))
        assert not [i for i in items if isinstance(i, ReplyDelta)], raw
        assert len(items) == 1 and isinstance(items[0], Done)
        assert json.loads(items[0].raw_json) == json.loads(raw)


def test_generate_json_returns_the_validated_schema_instance(logs: LogCapture) -> None:
    want = Reply(reply="Яку локацію ви пригледіли?", phase="p1")
    assert ScriptedLlm(lambda s, c, m: OK_JSON).generate_json("sys", TURNS, Reply, None) == want
    llm, client, _ = vertex([[OK_JSON]])
    assert llm.generate_json("sys", TURNS, Reply, None) == want
    assert len(client.calls) == 1


def test_generate_json_on_invalid_json_raises_validation_error(logs: LogCapture) -> None:
    for bad in ('{"reply": "no phase"}', '{"reply": "cut", "pha', '{"reply": 5, "phase": []}'):
        with pytest.raises(ValidationError):
            ScriptedLlm(lambda s, c, m, bad=bad: bad).generate_json("sys", TURNS, Reply, None)
        llm, _, _ = vertex([[bad]])
        with pytest.raises(ValidationError):
            llm.generate_json("sys", TURNS, Reply, None)


# ------------------------------------------------------------------ VertexLlm: request shape, laziness


def test_vertex_asks_for_json_with_the_schema_model_and_timeout(logs: LogCapture) -> None:
    llm, client, _ = vertex([[OK_JSON], [OK_JSON]], timeout_s=12.5)
    list(llm.stream_json("sys", TURNS, Reply, None))
    llm.generate_json("sys", TURNS, Reply, None)
    assert len(client.calls) == 2
    for call in client.calls:
        assert call.get("model") == "gemini-4-argon"
        config = call.get("config")
        assert cfg_get(config, "response_mime_type") == "application/json"
        assert cfg_get(config, "response_json_schema") == Reply.model_json_schema()
        assert cfg_get(cfg_get(config, "http_options"), "timeout") == 12500


def test_vertex_gives_the_first_delta_before_the_stream_ends(logs: LogCapture) -> None:
    llm, client, _ = vertex([['{"reply": "Hel', "lo wor", 'ld", "phase": "p1"}']])
    stream = llm.stream_json("sys", TURNS, Reply, None)
    first = next(iter(stream))
    assert isinstance(first, ReplyDelta) and first.text
    assert client.models.last_chunk_pulled is False
    rest = list(stream)
    text, done = split([first, *rest])
    assert text == "Hello world"
    assert len(done) == 1


# ------------------------------------------------------------------ Seam 2: retries


def test_vertex_retries_429_raised_on_first_next_then_streams(logs: LogCapture) -> None:
    llm, client, sleeps = vertex([[api_error(429)], [api_error(429)], [OK_JSON[:15], OK_JSON[15:]]])
    items = list(llm.stream_json("sys", TURNS, Reply, None))
    text, done = split(items)
    assert text == "Яку локацію ви пригледіли?"
    assert len(done) == 1
    assert len(client.calls) == 3
    assert len(sleeps.delays) == 2
    assert 0.5 <= sleeps.delays[0] <= 2.0
    assert 1.0 <= sleeps.delays[1] <= 4.0
    [line] = logs.events("llm_call")
    assert line["outcome"] == "ok"
    assert line["attempts"] == 3


def test_vertex_retries_5xx_and_a_chunk_without_reply_text_is_not_a_delta(logs: LogCapture) -> None:
    llm, client, sleeps = vertex([['{"', api_error(503)], [api_error(500)], [OK_JSON]])
    items = list(llm.stream_json("sys", TURNS, Reply, None))
    text, done = split(items)
    assert text == "Яку локацію ви пригледіли?"
    assert len(done) == 1
    assert len(client.calls) == 3
    assert len(sleeps.delays) == 2


def test_vertex_retries_a_timeout_before_the_first_delta(logs: LogCapture) -> None:
    for timeout in (httpx.ReadTimeout("slow"), httpx2.ReadTimeout("slow")):
        llm, client, sleeps = vertex([[timeout], [OK_JSON]])
        text, done = split(list(llm.stream_json("sys", TURNS, Reply, None)))
        assert text == "Яку локацію ви пригледіли?"
        assert len(done) == 1
        assert len(client.calls) == 2
        assert len(sleeps.delays) == 1


def test_vertex_error_after_the_first_delta_is_unavailable_without_retry(logs: LogCapture) -> None:
    for failure in (api_error(503), api_error(429), httpx.ReadTimeout("slow"), httpx2.ReadTimeout("slow")):
        llm, client, sleeps = vertex([['{"reply": "Hel', failure], [OK_JSON]])
        got, exc = collect_until_error(llm)
        assert isinstance(exc, LlmUnavailable), failure
        assert "".join(i.text for i in got if isinstance(i, ReplyDelta)) == "Hel"
        assert not [i for i in got if isinstance(i, Done)]
        assert len(client.calls) == 1
        assert sleeps.delays == []
    lines = logs.events("llm_call")
    assert len(lines) == 4
    assert all(line["outcome"] == "unavailable" for line in lines)


def test_vertex_exhausted_attempts_is_unavailable(logs: LogCapture) -> None:
    llm, client, _ = vertex([[api_error(503)], [api_error(500)], [api_error(429)]], attempts=3)
    got, exc = collect_until_error(llm)
    assert isinstance(exc, LlmUnavailable)
    assert got == []
    assert len(client.calls) == 3
    [line] = logs.events("llm_call")
    assert line["outcome"] == "unavailable"
    assert line["attempts"] == 3


def test_vertex_4xx_other_than_429_is_unavailable_without_retry(logs: LogCapture) -> None:
    for code in (400, 403, 404):
        llm, client, sleeps = vertex([[api_error(code)], [OK_JSON]])
        got, exc = collect_until_error(llm)
        assert isinstance(exc, LlmUnavailable), code
        assert len(client.calls) == 1
        assert sleeps.delays == []


def test_vertex_backoff_is_capped_at_30_seconds(logs: LogCapture) -> None:
    llm, client, sleeps = vertex([[api_error(503)] for _ in range(10)], attempts=10)
    _, exc = collect_until_error(llm)
    assert isinstance(exc, LlmUnavailable)
    assert len(client.calls) == 10
    assert len(sleeps.delays) >= 9
    assert all(0.5 <= d <= 30.0 for d in sleeps.delays)
    assert all(15.0 <= d <= 30.0 for d in sleeps.delays[5:9])


def test_vertex_generate_json_takes_the_same_retry_path(logs: LogCapture) -> None:
    llm, client, sleeps = vertex([[api_error(429)], [OK_JSON]])
    assert llm.generate_json("sys", TURNS, Reply, None) == Reply(
        reply="Яку локацію ви пригледіли?", phase="p1"
    )
    assert len(client.calls) == 2
    assert len(sleeps.delays) == 1
    llm, client, sleeps = vertex([[api_error(400)], [OK_JSON]])
    with pytest.raises(LlmUnavailable):
        llm.generate_json("sys", TURNS, Reply, None)
    assert len(client.calls) == 1
    assert sleeps.delays == []


# ------------------------------------------------------------------ the journal


def test_vertex_writes_one_llm_call_line_per_call_without_text(logs: LogCapture) -> None:
    secret_reply = "REPLY-SECRET-7"
    raw = '{"reply": "' + secret_reply + '", "phase": "p1"}'
    llm, _, _ = vertex([[raw[:12], raw[12:]], [raw]])
    turns = [Turn(role="user", text="USER-SECRET-3")]
    list(llm.stream_json("SYSTEM-SECRET-1", turns, Reply, KnowledgeRev(rev=4, n=17)))
    llm.generate_json("SYSTEM-SECRET-1", turns, Reply, None)
    lines = logs.events("llm_call")
    assert len(lines) == 2
    first = lines[0]
    for key in (
        "model",
        "prompt_tokens",
        "output_tokens",
        "thought_tokens",
        "latency_ms",
        "attempts",
        "rev",
        "n",
        "outcome",
    ):
        assert key in first, key
        assert key in lines[1], key
    assert first["model"] == "gemini-4-argon"
    assert first["prompt_tokens"] == 11
    assert first["thought_tokens"] == 5
    assert first["latency_ms"] == 2500
    assert first["attempts"] == 1
    assert first["rev"] == 4 and first["n"] == 17
    assert first["outcome"] == "ok"
    assert lines[1]["outcome"] == "ok"
    text = logs.text()
    for secret in ("REPLY-SECRET-7", "USER-SECRET-3", "SYSTEM-SECRET-1"):
        assert secret not in text
