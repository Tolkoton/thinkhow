"""Disputed catch-up test of spoken-replies' smoke (slice tester), question Q1.

Contract («Exit criterion», Smoke): «`POST /reply` з `spoken=1` і без нього → 200 SSE `answered` в обох».
«Без нього» can be read as «without the field `spoken`» or as «without `spoken=1`» (e.g. `spoken=0` or an
empty value). This file takes the first reading: the plain reply carries no `spoken` field at all.
"""

from __future__ import annotations

from sr_catchup_smoke_run import app_served, clean_run


def test_smoke_plain_reply_carries_no_spoken_field() -> None:
    run = clean_run()
    app_served(run)
    plain = [r for r in run.replies() if r.spoken != ["1"]]
    assert plain, f"no POST …/reply without spoken=1: {[r.fields for r in run.replies()]}"
    assert any("spoken" not in r.fields for r in plain), [r.fields for r in plain]
