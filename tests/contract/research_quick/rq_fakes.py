"""Helpers for the research-quick contract tests (slice tester; from the contract, not the code).

- SearchClient: a fake genai client whose stream chunks may carry `candidate.grounding_metadata`
  (Seam 1); every call's kwargs are recorded, so `config.tools` can be read (Seam 2).
  A failing stream raises on `next()`.
- FoundLlm: a fake `platform.llm.Llm` whose `stream_json` yields planned deltas and then
  `Done(raw, usage, found)`; `generate_json` validates the next planned raw JSON by the schema it was given.
- Cards, knowledge, contexts and decisions built by hand.
- RESEARCH_SECTION: the text of `facilitation/research.md`, word for word from the contract «Seam».
"""

from __future__ import annotations

import io
import json
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from google.genai import errors, types
from pydantic import BaseModel

from thinkhow.access import CurrentUser
from thinkhow.facilitation.types import (
    Decision,
    FacilitationContext,
    FacilitatorUpdate,
    MapItem,
    ProblemMap,
    Profile,
    Rev,
    Turn,
)
from thinkhow.knowledge import Card, CurrentKnowledge
from thinkhow.platform import llm as pl
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import TopicRef, create_topic

T0 = datetime(2026, 10, 25, 10, 0, 0, tzinfo=UTC)
ALICE = CurrentUser(id="alice-1", email="alice@example.com", is_owner=False)
REV = Rev(rev=3, n=7)
ROUTED_HEAD = "# Коли картку пройдено або вона не підходить"

RESEARCH_SECTION = "\n".join(
    [
        "# Факти про світ",
        "У тебе є пошук в інтернеті. Коли людина каже «не знаю», розрізняй, чого саме вона не знає:",
        "- Факт про світ, який можна дізнатися (ціни, ринок, як зазвичай роблять інші, де шукають клієнтів,"
        " правила, строки,",
        "  статистика), — не питай людину про нього: знайди сам і коротко дай знайдене в reply"
        " своїми словами, без посилань у",
        "  тексті (джерела система допише сама). Так само, коли людина прямо питає такий факт.",
        "- Те, що покаже лише реальність (чи відповідять клієнти, чи спрацює саме в неї), — не шукай і не"
        " вгадуй: запропонуй",
        "  дешевий спосіб перевірити це як її крок.",
        "- Факт про саму людину (її гроші, час, бажання, досвід) — питай її; про неї не шукай.",
        "Знайдене — підстава для її думки, не оцінка її варіантів: рішення й вибір лишаються"
        " за людиною. Після знайденого —",
        "як завжди, одне питання. Кожен знайдений факт, на який людина спиратиметься, коротко додай у"
        " map_updates пунктом",
        "типу «fact» (одне речення, з числом чи назвою, без посилань).",
    ]
)

# ------------------------------------------------------------------ cards, knowledge, contexts


def phase_dict(pid: str) -> dict[str, Any]:
    return {
        "id": pid,
        "title": f"Назва фази {pid}",
        "goal": f"мета фази {pid}",
        "how": [f"як іти фазою {pid}"],
        "exit": f"вихід фази {pid}",
    }


def card(cid: str, phase_ids: Sequence[str]) -> Card:
    return Card.model_validate(
        {
            "id": cid,
            "title": f"Заголовок {cid}",
            "router": {
                "needs": f"роутер-потреба {cid}",
                "when_yes": [f"коли так {cid}"],
                "when_no": [f"коли ні {cid}"],
                "signals": [f"сигнал {cid}"],
            },
            "facilitator": {
                "purpose": f"навіщо фасилітатору {cid}",
                "stance": f"позиція фасилітатора {cid}",
                "needs": f"на вході фасилітатора {cid}",
                "phases": [phase_dict(p) for p in phase_ids],
                "ending": f"кінець картки {cid}",
                "traps": [{"name": "Не той випадок", "text": f"текст пастки {cid}"}],
                "pairs_well": f"добре поєднується {cid}",
            },
        }
    )


ALPHA = card("alpha", ["a_one", "a_two", "a_three"])
BETA = card("beta", ["b_one", "b_two"])
PREMORTEM = card("pre-mortem", ["pm_one", "pm_two"])


def knowledge() -> CurrentKnowledge:
    return CurrentKnowledge(rev=3, n=7, cards={c.id: c for c in (ALPHA, BETA, PREMORTEM)}, memory=[])


PROFILE = Profile.model_validate(
    {
        "intent": "choose_between_options",
        "structuredness": "ill_structured",
        "reversibility": "one_way_door",
        "stakes": "high",
        "data": "qualitative_only",
        "options": "binary_dilemma",
        "emotion": "anxious",
        "social": "individual_personal",
    }
)


def d_choose(turn: int, cid: str) -> Decision:
    return Decision(
        turn=turn,
        rev=REV,
        kind="choose",
        profile=PROFILE,
        candidates=[],
        card_id=cid,
        end=None,
        why="людина обрала перше",
    )


ROUTED = (d_choose(1, "alpha"),)
HISTORY = [
    Turn(role="user", text="Хочу відкрити кав'ярню."),
    Turn(role="model", text="Що для вас тут найважливіше?"),
]
ITEM = MapItem(id="i1", type="goal", text="відкрити кав'ярню", turn="t1")


def context(
    routing: tuple[Decision, ...] | None = ROUTED,
    text: str = "Не знаю, скільки коштує оренда.",
    turn_no: int = 3,
) -> FacilitationContext:
    return FacilitationContext(
        card_id="alpha",
        history=list(HISTORY),
        problem_map=ProblemMap(items=[ITEM], phase_id="a_one", last_turn=2),
        turn_no=turn_no,
        text=text,
        language=None,
        routing=routing,
    )


# ------------------------------------------------------------------ raw answers


def answer(reply: str, phase: str | None = "a_one", updates: Sequence[dict[str, Any]] = ()) -> str:
    return json.dumps(
        {"reply": reply, "current_phase_id": phase, "phase_exit_met": False, "map_updates": list(updates)},
        ensure_ascii=False,
    )


def update_only(phase: str | None = "a_one") -> str:
    return json.dumps({"current_phase_id": phase, "phase_exit_met": False, "map_updates": []})


USAGE = pl.Usage(prompt_tokens=10, output_tokens=5, thought_tokens=0)


@dataclass
class Call:
    kind: str
    system: str
    contents: list[pl.Turn]
    schema: type[BaseModel]


@dataclass
class FoundLlm:
    """stream_json: planned deltas, then Done(raw, usage, found); generate_json: planned JSON, validated."""

    deltas: list[str]
    done_raw: str
    found: pl.Found | None = None
    generate: list[str] = field(default_factory=list)
    calls: list[Call] = field(default_factory=list)

    def stream_json(
        self, system: str, contents: Sequence[pl.Turn], schema: type[BaseModel], rev: pl.KnowledgeRev | None
    ) -> Iterator[pl.ReplyDelta | pl.Done]:
        self.calls.append(Call("stream", system, list(contents), schema))
        return self._stream()

    def _stream(self) -> Iterator[pl.ReplyDelta | pl.Done]:
        for d in self.deltas:
            yield pl.ReplyDelta(text=d)
        if self.found is None:
            yield pl.Done(self.done_raw, USAGE)  # positional, as the sealed fakes build it
        else:
            yield pl.Done(self.done_raw, USAGE, self.found)

    def generate_json(
        self, system: str, contents: Sequence[pl.Turn], schema: type[Any], rev: pl.KnowledgeRev | None
    ) -> Any:
        self.calls.append(Call("generate", system, list(contents), schema))
        if not self.generate:
            raise AssertionError("generate_json was called more times than the scenario planned")
        return schema.model_validate_json(self.generate.pop(0))


# ------------------------------------------------------------------ the genai fake with grounding metadata


def api_error(code: int) -> errors.APIError:
    body = {"error": {"code": code, "message": f"fake {code}", "status": "FAKE"}}
    if code >= 500:
        return errors.ServerError(code, body)
    return errors.ClientError(code, body)


GENAI_USAGE = types.GenerateContentResponseUsageMetadata(
    prompt_token_count=11, candidates_token_count=7, thoughts_token_count=5
)


def web(uri: str | None, title: str | None = None, domain: str | None = None) -> types.GroundingChunk:
    return types.GroundingChunk(web=types.GroundingChunkWeb(uri=uri, title=title, domain=domain))


def meta(
    queries: Sequence[str] | None = None,
    chunks: Sequence[types.GroundingChunk] | None = None,
    html: str | None = None,
) -> types.GroundingMetadata:
    return types.GroundingMetadata(
        web_search_queries=list(queries) if queries is not None else None,
        grounding_chunks=list(chunks) if chunks is not None else None,
        search_entry_point=types.SearchEntryPoint(rendered_content=html) if html is not None else None,
    )


@dataclass
class Piece:
    """One stream chunk: its text and, maybe, its grounding metadata."""

    text: str
    gm: types.GroundingMetadata | None = None


Step = Piece | str | BaseException


def response(text: str, gm: types.GroundingMetadata | None, usage: Any) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(role="model", parts=[types.Part(text=text)]), grounding_metadata=gm
            )
        ],
        usage_metadata=usage,
    )


class SearchModels:
    def __init__(self, plans: list[list[Step]]) -> None:
        self.plans = list(plans)
        self.calls: list[dict[str, Any]] = []
        self.kinds: list[str] = []

    def _next(self, kind: str, kwargs: dict[str, Any]) -> list[Step]:
        self.calls.append(kwargs)
        self.kinds.append(kind)
        if not self.plans:
            raise AssertionError("the fake client was called more times than the test planned")
        return self.plans.pop(0)

    def generate_content_stream(self, *args: Any, **kwargs: Any) -> Iterator[types.GenerateContentResponse]:
        return self._stream(self._next("stream", kwargs))

    def _stream(self, plan: list[Step]) -> Iterator[types.GenerateContentResponse]:
        pieces = [s for s in plan if not isinstance(s, BaseException)]
        sent = 0
        for step in plan:
            if isinstance(step, BaseException):
                raise step
            sent += 1
            last = sent == len(pieces) and not isinstance(plan[-1], BaseException)
            p = step if isinstance(step, Piece) else Piece(step)
            yield response(p.text, p.gm, GENAI_USAGE if last else None)

    def generate_content(self, *args: Any, **kwargs: Any) -> types.GenerateContentResponse:
        plan = self._next("generate", kwargs)
        texts: list[str] = []
        for step in plan:
            if isinstance(step, BaseException):
                raise step
            texts.append(step.text if isinstance(step, Piece) else step)
        return response("".join(texts), None, GENAI_USAGE)


class SearchClient:
    def __init__(self, plans: list[list[Step]]) -> None:
        self.models = SearchModels(plans)

    @property
    def calls(self) -> list[dict[str, Any]]:
        return self.models.calls


def cfg_get(config: Any, name: str) -> Any:
    if config is None:
        return None
    if isinstance(config, dict):
        return config.get(name)
    return getattr(config, name, None)


def has_search_tool(call: dict[str, Any]) -> bool:
    tools = cfg_get(call.get("config"), "tools") or []
    return any(cfg_get(t, "enterprise_web_search") is not None for t in tools)


def no_tools(call: dict[str, Any]) -> bool:
    return not (cfg_get(call.get("config"), "tools") or [])


class Sleeps:
    def __init__(self) -> None:
        self.delays: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


def vertex(plans: list[list[Step]], search: bool = True) -> tuple[pl.VertexLlm, SearchClient]:
    client = SearchClient(plans)
    llm = pl.VertexLlm(client, "gemini-4-argon", 300.0, 3, sleep=Sleeps(), clock=lambda: 10.0, search=search)
    return llm, client


def split_chunks(raw: str, n: int) -> list[str]:
    """`raw` cut into `n` pieces of (almost) equal length, none empty."""
    size = max(1, len(raw) // n)
    pieces = [raw[i * size : (i + 1) * size] for i in range(n - 1)]
    pieces.append(raw[(n - 1) * size :])
    assert "".join(pieces) == raw and all(pieces)
    return pieces


# ------------------------------------------------------------------ the journal


class LogCapture:
    def __init__(self, capsys: Any) -> None:
        self.buffer = io.StringIO()
        self.capsys = capsys
        self.printed = ""

    def events(self, event: str) -> list[dict[str, Any]]:
        self.printed += self.capsys.readouterr().out
        found = []
        for line in (self.buffer.getvalue() + self.printed).splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if isinstance(obj, dict) and obj.get("event") == event:
                found.append(obj)
        return found


def install_log_capture(monkeypatch: Any, capsys: Any) -> LogCapture:
    from thinkhow.platform import log

    cap = LogCapture(capsys)
    monkeypatch.setattr(log.log_event, "__defaults__", (cap.buffer,))
    return cap


# ------------------------------------------------------------------ the workspace side


def topic(store: LocalStorage) -> TopicRef:
    return TopicRef(ALICE.id, create_topic(store, ALICE, "Тема", T0))


def topic_path(ref: TopicRef, name: str) -> str:
    return f"{ref.uid}/{ref.topic_id}/{name}"


def raw_research(store: LocalStorage, ref: TopicRef) -> bytes | None:
    return store.read("users", topic_path(ref, "research.json"))


def read_research(store: LocalStorage, ref: TopicRef) -> list[dict[str, Any]] | None:
    data = raw_research(store, ref)
    if data is None:
        return None
    doc = json.loads(data)
    assert set(doc) == {"entries"}, doc
    entries: list[dict[str, Any]] = doc["entries"]
    return entries


def put_research(store: LocalStorage, ref: TopicRef, data: bytes) -> None:
    store.write("users", topic_path(ref, "research.json"), data, "application/json")


def put_routing(store: LocalStorage, ref: TopicRef, decisions: Sequence[Decision]) -> None:
    doc = {"decisions": [d.model_dump(mode="json") for d in decisions]}
    store.write(
        "users",
        topic_path(ref, "routing.json"),
        json.dumps(doc, ensure_ascii=False).encode(),
        "application/json",
    )


def read_map(store: LocalStorage, ref: TopicRef) -> dict[str, Any]:
    data = store.read("users", topic_path(ref, "map.json"))
    assert data is not None
    doc: dict[str, Any] = json.loads(data)
    return doc


@dataclass
class ScenarioFacilitate:
    scripts: list[list[Any]] = field(default_factory=list)
    contexts: list[FacilitationContext] = field(default_factory=list)

    def __call__(self, ctx: FacilitationContext) -> Iterator[Any]:
        self.contexts.append(ctx)
        if not self.scripts:
            raise AssertionError("facilitate was called more times than the scenario planned")
        return self._run(self.scripts.pop(0))

    def _run(self, script: list[Any]) -> Iterator[Any]:
        for step in script:
            if isinstance(step, BaseException):
                raise step
            yield step


class Down(Exception):
    """A model failure inside the stream (workspace answers it with Failed)."""


def upd(reply: str, phase: str | None = None) -> FacilitatorUpdate:
    return FacilitatorUpdate(reply=reply, current_phase_id=phase, phase_exit_met=False, map_updates=[])
