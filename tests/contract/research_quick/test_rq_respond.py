"""Contract tests of research-quick, `facilitation`: `sources_line`, `lead` with «found», the section
«# Факти про світ» under the router and `converse` passing `ResearchEvent` on
(slice tester; from the contract)."""

from typing import Any

from rq_fakes import (
    ALPHA,
    RESEARCH_SECTION,
    ROUTED,
    ROUTED_HEAD,
    FoundLlm,
    answer,
    context,
    knowledge,
    update_only,
)

from thinkhow.facilitation import FacilitatorUpdate, ReplyDelta, ResearchEvent, respond
from thinkhow.facilitation.respond import lead, sources_line, system_instruction
from thinkhow.facilitation.types import MapUpdate, Source
from thinkhow.platform import llm as pl

REPLY = "Оренда офісу в Лейпцигу коштує від 15 євро за метр. Скільки метрів вам треба?"
DELTAS = ["Оренда офісу в Лейпцигу коштує від 15 євро за метр. ", "Скільки метрів вам треба?"]
FACT = {"op": "add", "id": "i2", "type": "fact", "text": "Оренда в Лейпцигу — від 15 €/м².", "turn": "t3"}
FOUND = pl.Found(
    ("оренда офісу Лейпциг ціна",),
    (pl.Source("Ціни оренди", "https://a.example/rent"), pl.Source("Ринок", "https://b.example/m")),
    "<div>підказки</div>",
)
LINE = "\n\nДжерела: [Ціни оренди](https://a.example/rent), [Ринок](https://b.example/m)"
SOURCES = (Source("Ціни оренди", "https://a.example/rent"), Source("Ринок", "https://b.example/m"))


def kinds(items: list[Any]) -> list[str]:
    return [type(i).__name__ for i in items]


def research(items: list[Any]) -> list[ResearchEvent]:
    return [i for i in items if isinstance(i, ResearchEvent)]


def test_sources_line_is_markdown_links_after_a_blank_line_with_brackets_and_parens_made_safe() -> None:
    assert sources_line([]) == ""
    assert sources_line([Source("Ціни оренди", "https://a.example/rent")]) == (
        "\n\nДжерела: [Ціни оренди](https://a.example/rent)"
    )
    got = sources_line(
        [
            Source("[Звіт] ринку [2026]", "https://a.example/rent(2026)"),
            Source("Ринок (офіси)", "https://b.example/m"),
        ]
    )
    assert got == (
        "\n\nДжерела: [Звіт ринку 2026](https://a.example/rent%282026%29), [Ринок (офіси)](https://b.example/m)"
    )


def test_lead_with_sources_gives_the_answer_then_the_sources_line_then_research_then_the_update() -> None:
    llm = FoundLlm(deltas=list(DELTAS), done_raw=answer(REPLY, "a_one", [FACT]), found=FOUND)
    items = list(lead(context(), knowledge(), llm))
    assert kinds(items) == ["ReplyDelta", "ReplyDelta", "ReplyDelta", "ResearchEvent", "FacilitatorUpdate"]
    assert items[:3] == [ReplyDelta(DELTAS[0]), ReplyDelta(DELTAS[1]), ReplyDelta(LINE)]
    (ev,) = research(items)
    assert ev.depth == "quick"
    assert ev.queries == ("оренда офісу Лейпциг ціна",)
    assert ev.sources == SOURCES
    assert all(type(s) is Source for s in ev.sources)
    assert ev.suggestions_html == "<div>підказки</div>"
    assert items[-1] == FacilitatorUpdate(
        reply=REPLY + LINE,
        current_phase_id="a_one",
        phase_exit_met=False,
        map_updates=[MapUpdate.model_validate(FACT)],
    )


def test_lead_after_the_settle_retry_gives_the_sources_line_then_research_then_the_update() -> None:
    llm = FoundLlm(
        deltas=list(DELTAS), done_raw=answer(REPLY, "b_one"), found=FOUND, generate=[update_only("a_two")]
    )
    items = list(lead(context(), knowledge(), llm))
    assert kinds(items) == ["ReplyDelta", "ReplyDelta", "ReplyDelta", "ResearchEvent", "FacilitatorUpdate"]
    assert items[2] == ReplyDelta(LINE)
    assert research(items)[0].sources == SOURCES
    last = items[-1]
    assert isinstance(last, FacilitatorUpdate)
    assert last.reply == REPLY + LINE
    assert last.current_phase_id == "a_two"
    assert [c.kind for c in llm.calls] == ["stream", "generate"]


def test_lead_with_queries_but_no_sources_gives_research_without_a_sources_line() -> None:
    found = pl.Found(("оренда офісу Лейпциг ціна", "оренда Лейпциг 2026"), (), None)
    llm = FoundLlm(deltas=list(DELTAS), done_raw=answer(REPLY, "a_one"), found=found)
    items = list(lead(context(), knowledge(), llm))
    assert kinds(items) == ["ReplyDelta", "ReplyDelta", "ResearchEvent", "FacilitatorUpdate"]
    assert items[:2] == [ReplyDelta(DELTAS[0]), ReplyDelta(DELTAS[1])]
    (ev,) = research(items)
    assert ev.depth == "quick"
    assert ev.queries == ("оренда офісу Лейпциг ціна", "оренда Лейпциг 2026")
    assert ev.sources == ()
    assert ev.suggestions_html is None
    last = items[-1]
    assert isinstance(last, FacilitatorUpdate) and last.reply == REPLY


def test_under_the_router_the_facts_section_stands_after_the_routed_section_and_before_the_card() -> None:
    routed = system_instruction(ALPHA, [], None, routed=True)
    assert RESEARCH_SECTION in routed
    lines = routed.split("\n")
    lang = lines.index("# Мова відповіді")
    head = lines.index(ROUTED_HEAD)
    facts = lines.index("# Факти про світ")
    card = lines.index("# Картка")
    memory = lines.index("# Пам'ять досвіду")
    assert lang < head < facts < card < memory
    assert lines.count("# Факти про світ") == 1
    assert "# Факти про світ" not in system_instruction(ALPHA, [], None, routed=False)
    assert "# Факти про світ" not in system_instruction(ALPHA, [], "Polski (pl-PL)")


def test_respond_under_the_router_passes_research_on_before_the_update() -> None:
    llm = FoundLlm(deltas=list(DELTAS), done_raw=answer(REPLY, "a_one"), found=FOUND)
    items: list[Any] = list(respond(context(routing=ROUTED), knowledge(), llm))
    assert [c.kind for c in llm.calls] == ["stream"]
    assert "# Факти про світ" in llm.calls[0].system
    evs = research(items)
    assert len(evs) == 1 and evs[0].sources == SOURCES
    updates = [i for i in items if isinstance(i, FacilitatorUpdate)]
    assert len(updates) == 1
    assert items.index(evs[0]) < items.index(updates[0])
    assert "".join(i.text for i in items if isinstance(i, ReplyDelta)) == REPLY + LINE
    assert updates[0].reply == REPLY + LINE
