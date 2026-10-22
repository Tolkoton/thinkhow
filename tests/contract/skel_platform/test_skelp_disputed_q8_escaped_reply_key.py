"""Disputed catch-up test of skel-platform (question Q8 of the catch-up hand-in): a first key `reply`
written with a JSON escape. Not sealed until the slice planner answers."""

import json

from pydantic import BaseModel

from thinkhow.platform.llm import Done, ReplyDelta, ScriptedLlm, Turn


class Reply(BaseModel):
    reply: str
    phase: str


def test_q8_first_key_reply_spelled_with_an_escape_still_streams_the_reply() -> None:
    raw = '{"r\\u0065ply": "Привіт", "phase": "p"}'
    assert json.loads(raw) == {"reply": "Привіт", "phase": "p"}
    for size in (1, 4, len(raw)):
        items = list(
            ScriptedLlm(lambda s, c, m: raw, chunk=size).stream_json("sys", [Turn("user", "x")], Reply, None)
        )
        assert "".join(i.text for i in items if isinstance(i, ReplyDelta)) == "Привіт", size
        assert isinstance(items[-1], Done)
