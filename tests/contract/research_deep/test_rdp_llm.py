"""Contract tests of research-deep, `platform/llm.py` and `web/local.py`: `VertexLlm.search_text`
(Seam 5), `ScriptedLlm` with `search_script`, `make_llm` locally and `local_search`
(slice tester; from the contract)."""

from typing import Any

import pytest
from rdp_fakes import flat  # noqa: F401  (puts the sibling helper folders on sys.path)
from rq_fakes import (
    GENAI_USAGE,
    Sleeps,
    api_error,
    cfg_get,
    has_search_tool,
    install_log_capture,
    meta,
    response,
    web,
)

from thinkhow.platform import llm as pl
from thinkhow.platform.config import Settings
from thinkhow.web.local import local_search

GOOGLE = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/"
G1 = GOOGLE + "AUZIYQ-one"
G2 = GOOGLE + "AUZIYQ-two"
P1 = "https://a.example/mittelstand"
P2 = "https://b.example/markt"
HTML = '<a class="chip" href="' + GOOGLE + 's1">Mittelstand</a>'
SYSTEM = "Знайди факти з джерелами на це підпитання."
PROMPT = "Скільки коштує проєкт консалтингу для Mittelstand?"
TEXT = "Проєкт коштує від 8 000 до 25 000 євро."


class SearchModels:
    """`generate_content` by plan: `(text, grounding metadata)` or an exception; every call's kwargs kept."""

    def __init__(self, plans: list[Any]) -> None:
        self.plans = list(plans)
        self.calls: list[dict[str, Any]] = []

    def generate_content(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append({**kwargs, "args": args})
        if not self.plans:
            raise AssertionError("generate_content was called more times than the test planned")
        plan = self.plans.pop(0)
        if isinstance(plan, BaseException):
            raise plan
        text, gm = plan
        return response(text, gm, GENAI_USAGE)

    def generate_content_stream(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("search_text is one call without a stream")


class Client:
    def __init__(self, plans: list[Any]) -> None:
        self.models = SearchModels(plans)


class Resolve:
    def __init__(self, mapping: dict[str, str]) -> None:
        self.mapping = mapping
        self.calls: list[str] = []

    def __call__(self, url: str) -> str:
        self.calls.append(url)
        return self.mapping.get(url, url)


def vertex(plans: list[Any], resolve: Any = None, attempts: int = 3) -> tuple[pl.VertexLlm, Client]:
    client = Client(plans)
    llm = pl.VertexLlm(
        client,
        "gemini-4-argon",
        300.0,
        attempts,
        sleep=Sleeps(),
        clock=lambda: 10.0,
        search=True,
        resolve=resolve,
    )
    return llm, client


GM = meta(["Beratung Mittelstand Kosten", "Berater Preise"], [web(G1, "Studie"), web(G2, "Markt")], HTML)


def test_seam5_search_text_is_one_web_searched_call_without_json_its_found_resolved_and_one_llm_call(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    logs = install_log_capture(monkeypatch, capsys)
    resolve = Resolve({G1: P1, G2: P2})
    llm, client = vertex([(TEXT, GM)], resolve)
    text, found = llm.search_text(SYSTEM, PROMPT, pl.KnowledgeRev(rev=3, n=7))
    assert text == TEXT
    assert found == pl.Found(
        ("Beratung Mittelstand Kosten", "Berater Preise"),
        (pl.Source("Studie", P1), pl.Source("Markt", P2)),
        HTML,
    )
    assert sorted(resolve.calls) == sorted([G1, G2])
    (call,) = client.models.calls
    config = call.get("config")
    assert has_search_tool(call)
    assert cfg_get(config, "response_json_schema") is None
    assert cfg_get(config, "response_schema") is None
    system = cfg_get(config, "system_instruction")
    assert system is not None and SYSTEM in str(system)
    assert PROMPT in str(call.get("contents")) + str(call.get("args"))
    lines = logs.events("llm_call")
    assert len(lines) == 1
    assert lines[0]["search"] is True

    # without grounding metadata nothing was found (the rule of S1)
    llm, _ = vertex([(TEXT, None)], Resolve({}))
    assert llm.search_text(SYSTEM, PROMPT, None) == (TEXT, None)


def test_seam5_search_text_retries_a_temporary_error_like_generate_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    install_log_capture(monkeypatch, capsys)
    llm, client = vertex([api_error(503), (TEXT, GM)], Resolve({G1: P1, G2: P2}))
    text, found = llm.search_text(SYSTEM, PROMPT, None)
    assert text == TEXT
    assert found is not None and [s.url for s in found.sources] == [P1, P2]
    assert len(client.models.calls) == 2
    assert all(has_search_tool(c) for c in client.models.calls)


def test_seam5_search_text_with_the_attempts_exhausted_is_llm_unavailable_not_an_empty_answer(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    install_log_capture(monkeypatch, capsys)
    llm, client = vertex([api_error(503), api_error(500), api_error(429)], Resolve({}), attempts=3)
    with pytest.raises(pl.LlmUnavailable):
        llm.search_text(SYSTEM, PROMPT, None)
    assert len(client.models.calls) == 3


def script(system: str, contents: Any, schema: Any) -> str:
    raise AssertionError("search_text does not go through the JSON script")


class SearchRecorder:
    def __init__(self, answer: tuple[str, pl.Found | None]) -> None:
        self.answer = answer
        self.calls: list[tuple[str, str]] = []

    def __call__(self, system: str, prompt: str) -> tuple[str, pl.Found | None]:
        self.calls.append((system, prompt))
        return self.answer


FOUND = pl.Found(("Beratung Mittelstand Kosten",), (pl.Source("Markt", P2),), None)


def test_scripted_llm_search_text_answers_by_search_script_and_without_it_with_an_empty_text_and_none() -> (
    None
):
    rec = SearchRecorder((TEXT, FOUND))
    llm = pl.ScriptedLlm(script, search_script=rec)
    assert llm.search_text(SYSTEM, PROMPT, None) == (TEXT, FOUND)
    assert rec.calls == [(SYSTEM, PROMPT)]
    assert pl.ScriptedLlm(script).search_text(SYSTEM, PROMPT, None) == ("", None)


def test_make_llm_locally_passes_search_script_to_the_scripted_double() -> None:
    rec = SearchRecorder((TEXT, FOUND))
    llm = pl.make_llm(Settings(local=True), script, search=True, search_script=rec)
    assert llm.search_text(SYSTEM, PROMPT, None) == (TEXT, FOUND)
    assert rec.calls == [(SYSTEM, PROMPT)]


def test_local_search_answers_found_prompt_with_an_example_org_source() -> None:
    text, found = local_search(SYSTEM, PROMPT)
    assert text == "(локально) знайдено: " + PROMPT
    assert found is not None
    assert found.sources and all("example.org" in s.url for s in found.sources)
