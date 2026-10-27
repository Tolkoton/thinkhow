"""Catch-up contract tests of conversation-resilience, DISPUTED (questions Q1 and Q2 of the slice tester's
catch-up hand-in): the smoke script's clean run.

Q1: «3 цикли» — exactly three, or at least three? These tests take «at least three».
Q2: «речень на `/speak` 200 менше, ніж запитів, на одне» with the 502 put by a Playwright `route` — counted as
the page sees it, or at the server? These tests count as the page sees it (after the route).
"""

from __future__ import annotations

from cres_catchup_run import clean_run, server_ran


def test_smoke_answers_the_second_speak_of_the_first_answer_with_502_and_no_other() -> None:
    run = clean_run()
    server_ran(run)
    seen = run.page_speak()
    assert len(seen) >= 3, f"the page made fewer than 3 /speak fetches: {seen}\n" + run.out
    assert seen.get(2) == "502", f"the page's second /speak did not get 502: {seen}"
    others = {n: status for n, status in seen.items() if n != 2}
    assert all(status == "200" for status in others.values()), (
        f"a /speak other than the second failed: {seen}"
    )
    order = [r for r in run.records if r.get("kind") in ("req", "beacon")]
    second_voice = [
        i
        for i, r in enumerate(order)
        if r.get("kind") == "req" and r.get("seg") == "voice" and r.get("n") == 2
    ]
    speak_2 = [i for i, r in enumerate(order) if r.get("kind") == "beacon" and r.get("what") == "speak-2-502"]
    assert second_voice and speak_2, f"no second /voice or no 502 /speak: {order}"
    assert speak_2[0] < second_voice[0], (
        "the 502 /speak came after the second /voice: it was not a sentence of the first answer"
    )


def test_smoke_runs_three_cycles_the_third_back_to_listening() -> None:
    run = clean_run()
    server_ran(run)
    voice = [r for r in run.requests("voice") if r["status"] == 200]
    reply = [r for r in run.requests("reply") if r["status"] == 200]
    assert len(voice) >= 3, f"fewer than 3 recognitions reached the server: {run.requests('voice')}"
    assert len(reply) >= 3, f"fewer than 3 answers came from the server: {run.requests('reply')}"
    listening = run.beacons("state-listening")
    assert listening >= 4, (
        f"#talk entered listening {listening} times: the first time after the click and once after each of "
        "3 answers make 4"
    )
