"""Catch-up contract tests of skel-platform: the `reply` delta extraction (slice tester).

Written from the contract (.engine/slices/skel-platform.md, Decisions Q2 and Q2a), not the code. The
contract says ScriptedLlm and VertexLlm share one extraction of deltas ("через той самий витяг дельт,
що й `VertexLlm`"); the builder keeps it in `_reply_stream`. It is reached here only through the public
seam — `stream_json` of both implementations — never imported.
"""

import itertools
import json

import pytest
from pydantic import BaseModel
from skelp_fakes import Clock, FakeGenaiClient, LogCapture, Sleeps, install_log_capture

from thinkhow.platform.llm import Done, ReplyDelta, ScriptedLlm, Turn, VertexLlm


class Reply(BaseModel):
    reply: str
    phase: str


TURNS = [Turn(role="user", text="хочу відкрити кав'ярню")]


@pytest.fixture
def logs(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> LogCapture:
    return install_log_capture(monkeypatch, capsys)


def run_vertex(pieces: list[str]) -> list[ReplyDelta | Done]:
    llm = VertexLlm(FakeGenaiClient([pieces]), "gemini-4-argon", 300.0, 3, sleep=Sleeps(), clock=Clock())
    return list(llm.stream_json("sys", TURNS, Reply, None))


def run_scripted(raw: str, size: int) -> list[ReplyDelta | Done]:
    return list(ScriptedLlm(lambda s, c, m: raw, chunk=size).stream_json("sys", TURNS, Reply, None))


def joined(items: list[ReplyDelta | Done]) -> str:
    return "".join(i.text for i in items if isinstance(i, ReplyDelta))


def one_done_last(items: list[ReplyDelta | Done], raw: str) -> bool:
    dones = [i for i in items if isinstance(i, Done)]
    return len(dones) == 1 and items[-1] is dones[0] and json.loads(dones[0].raw_json) == json.loads(raw)


# (raw JSON as the model streams it, the reply written out by hand)
ESCAPES: list[tuple[str, str]] = [
    # the escapes the earlier cases did not use: \r \b \f, upper-case hex, NUL
    ('{"reply": "cr\\r bs\\b ff\\f \\u00C9\\u00e9 nul\\u0000.", "phase": "p"}', "cr\r bs\b ff\f Éé nul\x00."),
    # a surrogate pair right after an escaped quote and before an escaped backslash
    ('{"reply": "\\"\\uD83E\\uDDED\\\\\\ud83d\\ude00", "phase": "p"}', '"\U0001f9ed\\\U0001f600'),
    # two pairs back to back, then a BMP escape, then a literal emoji
    (
        '{"reply": "\\ud83d\\ude00\\ud83d\\ude01\\u0456\U0001f600", "phase": "p"}',
        "\U0001f600\U0001f601і\U0001f600",
    ),
]


def test_escapes_and_surrogate_pairs_decode_whole_under_any_two_cuts(logs: LogCapture) -> None:
    for raw, expected in ESCAPES:
        assert json.loads(raw)["reply"] == expected  # the hand-written value is the JSON's own
        # VertexLlm: three chunks, cut at every pair of positions (a pair cut in two places included)
        for i, j in itertools.combinations(range(1, len(raw)), 2):
            pieces = [raw[:i], raw[i:j], raw[j:]]
            items = run_vertex(pieces)
            assert joined(items) == expected, (raw, pieces)
            assert one_done_last(items, raw), (raw, pieces)
        # ScriptedLlm: every chunk size
        for size in range(1, len(raw) + 1):
            items = run_scripted(raw, size)
            assert joined(items) == expected, (raw, size)
            assert one_done_last(items, raw), (raw, size)


# the first top-level key is not `reply`, though `reply` comes later
NOT_FIRST: list[str] = [
    '{"reply_text": "early", "reply": "late"}',  # a key that only starts with `reply`
    '{"x_reply": "early", "reply": "late"}',  # a key that only ends with `reply`
    '{"Reply": "early", "reply": "late"}',  # JSON keys are case-sensitive
    '{"kind": "reply", "reply": "late"}',  # the string "reply" as the first VALUE, not a key
    '{"kind": "reply" , "reply": "late"}',
    '{"n": 1, "reply": "late"}',  # a number first
    '{"tags": ["reply", "x"], "reply": "late"}',  # "reply" inside an array first
]


def test_a_first_key_that_is_not_exactly_reply_gives_no_delta(logs: LogCapture) -> None:
    for raw in NOT_FIRST:
        for size in (1, 3, len(raw)):
            items = run_scripted(raw, size)
            assert not [i for i in items if isinstance(i, ReplyDelta)], (raw, size)
            assert len(items) == 1 and one_done_last(items, raw), (raw, size)
            items = run_vertex([raw[k : k + size] for k in range(0, len(raw), size)])
            assert not [i for i in items if isinstance(i, ReplyDelta)], (raw, size)
            assert len(items) == 1 and one_done_last(items, raw), (raw, size)
