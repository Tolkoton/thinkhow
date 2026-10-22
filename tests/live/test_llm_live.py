"""Seam 4: one real streamed call to Gemini on Vertex AI (`pytest -m live`)."""

import json
import os

import pytest
from pydantic import BaseModel

from thinkhow.platform.config import load_settings
from thinkhow.platform.llm import Done, ReplyDelta, Turn, make_llm


class Answer(BaseModel):
    reply: str
    topic: str


@pytest.mark.live
def test_vertex_streams_reply_deltas_that_join_into_the_reply() -> None:
    settings = load_settings(
        {
            **os.environ,
            "THINKHOW_LOCAL": "false",
            "THINKHOW_USERS_BUCKET": "-",
            "THINKHOW_SYSTEM_BUCKET": "-",
            "THINKHOW_OWNER_EMAIL": "-",
        }
    )
    llm = make_llm(settings, script=lambda *_: "")
    events = list(
        llm.stream_json(
            "Відповідай українською, трьома-чотирма реченнями.",
            [Turn("user", "Розкажи, навіщо людині передбачати, чому її план може провалитися.")],
            Answer,
            None,
        )
    )
    deltas = [e.text for e in events if isinstance(e, ReplyDelta)]
    done = events[-1]
    assert isinstance(done, Done)
    assert len(deltas) >= 2
    assert "".join(deltas) == json.loads(done.raw_json)["reply"]
