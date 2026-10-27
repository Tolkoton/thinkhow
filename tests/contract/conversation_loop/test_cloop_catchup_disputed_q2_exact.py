"""Catch-up contract test of conversation-loop, DISPUTED (question Q2 of the slice tester's catch-up hand-in).

The contract («Exit criterion»): «на сервер пішли 3 `/voice`, 3 `/reply` (з `spoken=1`), ≥ 3 `/speak`».
Q2 asks whether «3» means exactly three (the line writes «≥ 3» for `/speak` only) or at least three.
This file takes the stricter reading: after the three cycles, the smoke ends before
a fourth turn reaches the server.
"""

from __future__ import annotations

from cloop_catchup_run import clean_run, server_ran


def test_smoke_sends_exactly_three_voice_and_three_reply_requests() -> None:
    run = clean_run()
    server_ran(run)
    assert len(run.requests("voice")) == 3, run.requests("voice")
    assert len(run.requests("reply")) == 3, run.requests("reply")
