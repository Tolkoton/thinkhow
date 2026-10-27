"""Catch-up contract test of conversation-loop, DISPUTED (question Q3 of the slice tester's catch-up hand-in).

The contract («Exit criterion», Smoke): «Вивід — у `.engine/artifacts/conversation-loop/smoke.txt`».
Q3 asks whether the script itself writes that file, or whether its output (stdout) is saved there by whoever
runs the command. This file takes the stricter reading: a run of the exit criterion's command, with no
redirection, leaves a non-empty `smoke.txt` in that folder (the helper removes the old one first and puts
it back afterwards).
"""

from __future__ import annotations

from cloop_catchup_run import clean_run, server_ran


def test_smoke_writes_its_output_to_the_artifact() -> None:
    run = clean_run()
    server_ran(run)
    assert run.smoke_txt is not None, "the smoke wrote no .engine/artifacts/conversation-loop/smoke.txt"
    assert run.smoke_txt.strip(), "smoke.txt is empty"
