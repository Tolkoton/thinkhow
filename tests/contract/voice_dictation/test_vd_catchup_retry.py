"""Catch-up (voice-dictation): the one retry rule in platform/_retry.py, written from the contract.

Contract, «Seam (contract)», GeminiSpeech: retry on 429, >= 500 and a timeout; the helpers
`retryable(exc)` and `backoff_s(attempt)` with `min(2**attempt, 30) * uniform(0.5, 1.0)` move from
platform.llm into platform/_retry.py and both modules import them; platform.speech does not import
platform.llm.
"""

import grimp
import httpx
import httpx2
from google.genai import errors

from thinkhow.platform._retry import backoff_s, retryable


def api_error(code: int) -> errors.APIError:
    body = {"error": {"code": code, "message": f"fake {code}", "status": "FAKE"}}
    if code >= 500:
        return errors.ServerError(code, body)
    return errors.ClientError(code, body)


def test_retryable_429_5xx_and_timeouts_are_retried() -> None:
    retried: list[Exception] = [
        api_error(429),
        api_error(500),
        api_error(502),
        api_error(503),
        api_error(504),
        httpx.ReadTimeout("slow"),
        httpx.ConnectTimeout("slow"),
        httpx2.ReadTimeout("slow"),
        httpx2.ConnectTimeout("slow"),
    ]
    for exc in retried:
        assert retryable(exc) is True, repr(exc)


def test_retryable_other_errors_are_not_retried() -> None:
    final: list[Exception] = [
        api_error(400),
        api_error(401),
        api_error(403),
        api_error(404),
        api_error(499),
        ValueError("bad part"),
        RuntimeError("boom"),
    ]
    for exc in final:
        assert retryable(exc) is False, repr(exc)


def test_backoff_s_is_two_to_the_attempt_capped_at_30_times_half_to_one() -> None:
    # min(2**attempt, 30), written out by hand
    ceiling = {0: 1.0, 1: 2.0, 2: 4.0, 3: 8.0, 4: 16.0, 5: 30.0, 6: 30.0, 10: 30.0}
    for attempt, top in ceiling.items():
        seen = {backoff_s(attempt) for _ in range(200)}
        for delay in seen:
            assert top * 0.5 <= delay <= top, (attempt, delay)
        assert len(seen) > 1, f"attempt {attempt}: no jitter, always {seen}"


def test_speech_and_llm_both_take_the_rule_from_retry_and_speech_never_reaches_llm() -> None:
    graph = grimp.build_graph("thinkhow")
    assert graph.direct_import_exists(
        importer="thinkhow.platform.speech", imported="thinkhow.platform._retry"
    )
    assert graph.direct_import_exists(importer="thinkhow.platform.llm", imported="thinkhow.platform._retry")
    assert (
        graph.find_shortest_chain(importer="thinkhow.platform.speech", imported="thinkhow.platform.llm")
        is None
    )
