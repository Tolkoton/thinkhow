"""Block tests of thinking-models-router (F7 + F5): one per line of «Inter-slice contracts»,
one per acceptance criterion (the feature closes with S3 router-eval).

Slice tester, mode `block`; from `.engine/architecture/feature/thinking-models-router.md`, the slice
contracts it names and the public signatures, not the bodies. Every test drives two or more slices
together: the real cards of `cards/` (S1; 18 in task 302, more since task 307) through the router
and the facilitator (S2) and the scripts and the set of situations (S3).
Expected values are written by hand from the artifact and the slice contracts.
"""

from __future__ import annotations

import functools
import json
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml
from tmr_fakes import (
    ALICE,
    ARTIFACTS,
    ASK_REPLY,
    CARD_IDS,
    CARDS,
    CASES,
    OFFER_REPLY,
    PROFILE,
    ROOT,
    ROUTER_WHY,
    Model,
    Person,
    at,
    choose_raw,
    fac_raw,
    offer_raw,
    router_raw,
    script,
    seeded_knowledge,
    why_of,
)

from thinkhow import knowledge, workspace
from thinkhow.facilitation import respond
from thinkhow.facilitation.types import (
    Candidate,
    Decision,
    FacilitationContext,
    FacilitatorUpdate,
    ProblemMap,
    Profile,
    ReplyDelta,
    Rev,
    RoutingEvent,
)
from thinkhow.knowledge import CurrentKnowledge
from thinkhow.learning import job
from thinkhow.platform.storage import LocalStorage, Storage
from thinkhow.web.app import build_deps

UKRAINIAN = "Українська (uk-UA)"


def drain(events: Iterator[Any]) -> list[Any]:
    return list(events)


def ctx(
    text: str, turn_no: int = 1, routing: tuple[Decision, ...] | None = (), card_id: str = "pre-mortem"
) -> FacilitationContext:
    return FacilitationContext(
        card_id=card_id,
        history=[],
        problem_map=ProblemMap(),
        turn_no=turn_no,
        text=text,
        language=UKRAINIAN,
        routing=routing,
    )


def phases(k: CurrentKnowledge, cid: str) -> list[str]:
    return [p.id for p in k.cards[cid].facilitator.phases]


def new_topic(store: Storage) -> workspace.TopicRef:
    workspace.ensure_profile(store, ALICE)
    workspace.set_language(store, ALICE, "uk-UA")
    return workspace.TopicRef(ALICE.id, workspace.create_topic(store, ALICE, "Тема", at(0)))


def routing_file(root: Path, ref: workspace.TopicRef) -> dict[str, Any] | None:
    path = root / "users" / ref.uid / ref.topic_id / "routing.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def saved_no(events: list[workspace.ReplyEvent]) -> int:
    saved = [e for e in events if isinstance(e, workspace.Saved)]
    assert len(saved) == 1, events
    return saved[0].turn_no


def norm(text: str) -> str:
    return " ".join(text.split())


def choose_decision(cid: str, k: CurrentKnowledge, turn: int = 1) -> Decision:
    return Decision(
        turn=turn,
        rev=Rev(rev=k.rev, n=k.n),
        kind="choose",
        profile=Profile.model_validate(PROFILE),
        candidates=[],
        card_id=cid,
        end=None,
        why=ROUTER_WHY,
    )


def local_environ(tmp: Path) -> dict[str, str]:
    return {
        "THINKHOW_LOCAL": "true",
        "THINKHOW_LOCAL_DIR": str(tmp),
        "THINKHOW_OWNER_EMAIL": "owner@localhost",
    }


# The 18 cards of task 302 (feature thinking-models-router). Task 307 adds cards to `cards/`;
# the same checks for its cards belong to feature product-thinking-pack, not here.
TASK_302_IDS = frozenset(
    {
        "complexity-sensemaking",
        "consider-opposite",
        "evaporating-cloud",
        "first-principles",
        "five-whys",
        "goal-to-plan",
        "is-is-not",
        "issue-tree",
        "jobs-to-be-done",
        "mental-contrasting",
        "opportunity-tree",
        "pre-mortem",
        "reflective-cycle",
        "reversible-doors",
        "scamper",
        "socratic-questioning",
        "weighted-matrix",
        "wrap-decision",
    }
)


# ------------------------------------------------------------------ Inter-slice contracts


# S1 → S2: the router reads only the router half and the title; the facilitator reads card_prompt(card)
def test_s1_to_s2_router_sees_router_halves_of_the_18_cards_and_the_facilitator_its_card_prompt(
    tmp_path: Path,
) -> None:
    _, k = seeded_knowledge(tmp_path)
    assert sorted(k.cards) == CARD_IDS and TASK_302_IDS <= set(CARD_IDS)
    model = Model(
        router=lambda no, text: choose_raw("five-whys"),
        facilitator=lambda no, text: fac_raw(phases(k, "five-whys")[0]),
    )
    drain(respond(ctx("Хочу розібратися, чому клієнти йдуть."), k, model))
    [router_call] = model.router_calls
    system = norm(router_call.system)
    for card in k.cards.values():
        assert f"### {card.id} — {card.title}" in router_call.system
        for item in [card.router.needs, *card.router.when_yes, *card.router.when_no, *card.router.signals]:
            assert norm(item) in system, (card.id, item)
        assert norm(card.facilitator.purpose) not in system, card.id
        assert norm(card.facilitator.phases[0].goal) not in system, card.id
    [lead_call] = model.stream_calls
    assert knowledge.card_prompt(k.cards["five-whys"]) in lead_call.system


# S1 → S3: the ids of the 18 cards are the ids of cases.yaml; S3 edits only card texts
def test_s1_to_s3_the_cards_of_cases_yaml_are_exactly_the_18_cards_and_each_file_is_its_id(
    tmp_path: Path,
) -> None:
    cases = yaml.safe_load(CASES.read_text(encoding="utf-8"))["cases"]
    expected = {c["expect"] for c in cases if c.get("kind") == "positive"}
    assert expected == set(CARD_IDS)
    for path in CARDS.glob("*.yaml"):
        card = knowledge.Card.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        assert card.id == path.stem
    _, k = seeded_knowledge(tmp_path)
    assert set(k.cards) == expected


# S2 → S3: route called directly on the situations; «перша» = candidates[0]
def test_s2_to_s3_route_on_every_situation_of_the_set_gives_the_outcome_with_candidates_0_first(
    tmp_path: Path,
) -> None:
    rev = script("router_eval")
    _, k = seeded_knowledge(tmp_path)
    cases = rev.load_cases(CASES)
    by_text: dict[str, tuple[str, str]] = {}
    for case in cases:
        first = case.get("expect") or case["also_ok"][0]
        banned = {first, *case.get("absent", []), *case.get("not_first", [])}
        other = next(cid for cid in CARD_IDS if cid not in banned)
        by_text[case["text"].strip()] = (first, other)

    def router(no: int, text: str) -> str:
        first, other = by_text[text.strip()]
        return offer_raw(first, other)

    model = Model(router=router)
    outcomes = rev.run(cases, k, model, workers=2)
    assert len(outcomes) == len(cases) == len(model.router_calls)
    for outcome in outcomes:
        case = next(c for c in cases if c["id"] == outcome.case_id)
        first, other = by_text[case["text"].strip()]
        assert (outcome.action, outcome.first, outcome.offered) == ("offer", first, [first, other]), outcome
        assert outcome.first_ok, outcome
    for call in model.router_calls:
        case = next(c for c in cases if c["text"].strip() == call.text.strip())
        assert call.turn_no == len(case.get("history", [])) + 1


# S2 → S3: facilitation.converse through workspace.reply (the live conversations)
def test_s2_to_s3_a_card_conversation_runs_the_real_card_through_the_router_and_the_facilitator(
    tmp_path: Path,
) -> None:
    cc = script("card_conversations")
    _, k = seeded_knowledge(tmp_path)
    target = "five-whys"
    ids = phases(k, target)
    led: list[int] = []

    def router(no: int, text: str) -> str:
        return choose_raw(target) if text.startswith("Давай") else offer_raw(target, "issue-tree")

    def facilitator(no: int, text: str) -> str:
        led.append(no)
        i = min(len(led), len(ids)) - 1
        return fac_raw(ids[i], exit_met=i == len(ids) - 1)

    model = Model(router=router, facilitator=facilitator)
    opener = "Уже втретє за квартал зриваємо реліз, і щоразу кажемо, що це випадковість."
    conv = cc.converse_card(k, model, Person(), target, opener)
    assert (conv.target, conv.led, conv.offered, conv.done) == (target, target, True, True)
    assert conv.phases == ids
    assert [c.text for c in model.router_calls] == [opener, "Давай перше."]
    for call in model.stream_calls:
        assert knowledge.card_prompt(k.cards[target]) in call.system


# Facilitate stream (converse): on offer — the event, the router's text as one delta, a phase-less update
def test_stream_on_offer_is_the_routing_event_one_delta_and_a_phase_less_update(tmp_path: Path) -> None:
    _, k = seeded_knowledge(tmp_path)
    model = Model(router=lambda no, text: offer_raw("issue-tree", "five-whys"))
    out = drain(respond(ctx("Не розумію, чому студія в мінусі."), k, model))
    profile = Profile.model_validate(PROFILE)
    assert out == [
        RoutingEvent(
            Decision(
                turn=1,
                rev=Rev(rev=1, n=k.n),
                kind="offer",
                profile=profile,
                candidates=[
                    Candidate(card_id="issue-tree", why=why_of("issue-tree")),
                    Candidate(card_id="five-whys", why=why_of("five-whys")),
                ],
                card_id=None,
                end=None,
                why=ROUTER_WHY,
            )
        ),
        ReplyDelta(OFFER_REPLY),
        FacilitatorUpdate(reply=OFFER_REPLY, current_phase_id=None, phase_exit_met=False, map_updates=[]),
    ]
    assert model.stream_calls == []
    ask = Model(router=lambda no, text: router_raw("ask", (), None, ASK_REPLY))
    out = drain(respond(ctx("Щось не так."), k, ask))
    assert [type(e) for e in out] == [RoutingEvent, ReplyDelta, FacilitatorUpdate]
    assert out[0].decision.kind == "ask" and out[1] == ReplyDelta(ASK_REPLY)
    assert out[2] == FacilitatorUpdate(
        reply=ASK_REPLY, current_phase_id=None, phase_exit_met=False, map_updates=[]
    )


# Facilitate stream (converse): on choose — the event, then the respond stream with the chosen card
def test_stream_on_choose_is_the_routing_event_then_the_chosen_cards_lead(tmp_path: Path) -> None:
    _, k = seeded_knowledge(tmp_path)
    first = phases(k, "weighted-matrix")[0]
    model = Model(
        router=lambda no, text: choose_raw("weighted-matrix"),
        facilitator=lambda no, text: fac_raw(first, reply="Які варіанти у вас є?"),
    )
    out = drain(respond(ctx("Давай зважимо обидва варіанти."), k, model))
    assert out[0] == RoutingEvent(choose_decision("weighted-matrix", k))
    assert all(isinstance(e, ReplyDelta) for e in out[1:-1]) and out[1:-1]
    assert "".join(e.text for e in out[1:-1]) == "Які варіанти у вас є?"
    assert out[-1] == FacilitatorUpdate(
        reply="Які варіанти у вас є?", current_phase_id=first, phase_exit_met=False, map_updates=[]
    )
    [lead_call] = model.stream_calls
    assert knowledge.card_prompt(k.cards["weighted-matrix"]) in lead_call.system


# Facilitate stream (converse): the end of the card goes as a RoutingEvent before the closing update
def test_stream_end_of_the_card_is_a_routing_event_just_before_the_update(tmp_path: Path) -> None:
    _, k = seeded_knowledge(tmp_path)
    chosen = (choose_decision("five-whys", k, turn=1),)
    ids = phases(k, "five-whys")
    not_fit = Model(facilitator=lambda no, text: fac_raw(None, reply="Що для вас зараз найважливіше?"))
    out = drain(respond(ctx("Це не про причини.", turn_no=3, routing=chosen), k, not_fit))
    assert not_fit.router_calls == []
    assert isinstance(out[-2], RoutingEvent) and isinstance(out[-1], FacilitatorUpdate)
    end = out[-2].decision
    assert (end.turn, end.kind, end.card_id, end.end, end.profile, end.candidates) == (
        3,
        "end",
        "five-whys",
        "not_fit",
        None,
        [],
    )
    assert [type(e) for e in out[:-2]] == [ReplyDelta] * len(out[:-2])
    done = Model(facilitator=lambda no, text: fac_raw(ids[-1], exit_met=True, reply="Що хочете робити далі?"))
    out = drain(respond(ctx("Так, це і є зміна.", turn_no=9, routing=chosen), k, done))
    end = out[-2].decision
    assert (end.turn, end.kind, end.card_id, end.end) == (9, "end", "five-whys", "done")
    assert out[-1].current_phase_id == ids[-1]
    middle = Model(facilitator=lambda no, text: fac_raw(ids[-1], exit_met=False))
    out = drain(respond(ctx("Ще думаю.", turn_no=7, routing=chosen), k, middle))
    assert not any(isinstance(e, RoutingEvent) for e in out)


# FacilitationContext.routing: () from workspace without routing.json, the decisions when it exists
def test_workspace_hands_an_empty_tuple_without_routing_json_and_the_decisions_with_it(
    tmp_path: Path,
) -> None:
    store, k = seeded_knowledge(tmp_path)
    ref = new_topic(store)
    seen: list[FacilitationContext] = []
    choose = choose_decision("scamper", k, turn=1)

    def facilitate(c: FacilitationContext) -> Iterator[Any]:
        seen.append(c)
        if len(seen) == 1:
            yield RoutingEvent(choose)
        yield ReplyDelta("Добре.")
        yield FacilitatorUpdate(reply="Добре.", current_phase_id=None, phase_exit_met=False, map_updates=[])

    drain(workspace.reply(store, facilitate, ALICE, ref, "Перша репліка.", at(1)))
    drain(workspace.reply(store, facilitate, ALICE, ref, "Друга репліка.", at(2)))
    assert seen[0].routing == ()
    assert seen[1].routing == (choose,)


# FacilitationContext.card_id: the card of the last choose, otherwise CARD_ID
def test_card_id_in_the_context_is_the_last_choose_otherwise_pre_mortem(tmp_path: Path) -> None:
    store, k = seeded_knowledge(tmp_path)
    ref = new_topic(store)
    seen: list[FacilitationContext] = []
    plan = [[RoutingEvent(choose_decision("scamper", k, turn=1))], [], []]

    def facilitate(c: FacilitationContext) -> Iterator[Any]:
        seen.append(c)
        yield from plan[len(seen) - 1]
        if len(seen) == 2:
            yield RoutingEvent(
                Decision(
                    turn=3,
                    rev=Rev(rev=k.rev, n=k.n),
                    kind="end",
                    profile=None,
                    candidates=[],
                    card_id="scamper",
                    end="not_fit",
                    why="картка не підходить",
                )
            )
        yield ReplyDelta("Добре.")
        yield FacilitatorUpdate(reply="Добре.", current_phase_id=None, phase_exit_met=False, map_updates=[])

    for i in range(3):
        drain(workspace.reply(store, facilitate, ALICE, ref, f"Репліка {i}.", at(i + 1)))
    assert [c.card_id for c in seen] == [workspace.CARD_ID, "scamper", workspace.CARD_ID]
    assert workspace.CARD_ID == "pre-mortem"


# workspace._answer gives RoutingEvent a branch of its own (not a Delta)
def test_workspace_does_not_show_a_routing_event_as_text(tmp_path: Path) -> None:
    store, k = seeded_knowledge(tmp_path)
    ref = new_topic(store)
    model = Model(router=lambda no, text: offer_raw("issue-tree", "five-whys"))
    facilitate = functools.partial(respond, knowledge=k, llm=model)
    events = drain(workspace.reply(store, facilitate, ALICE, ref, "Не розумію, де губляться гроші.", at(1)))
    deltas = [e for e in events if isinstance(e, workspace.Delta)]
    assert "".join(d.text for d in deltas) == OFFER_REPLY
    assert isinstance(events[0], workspace.Saved) and isinstance(events[-1], workspace.Answered)


# web.app: the application's Facilitate is respond bound to the Knowledge and the model; it goes to the router
def test_web_app_facilitate_carries_the_18_cards_and_goes_to_the_router_first(tmp_path: Path) -> None:
    deps = build_deps(local_environ(tmp_path), CARDS)
    assert isinstance(deps.facilitate, functools.partial)
    current = deps.facilitate.keywords["knowledge"]
    assert sorted(current.cards) == CARD_IDS
    out = drain(deps.facilitate(ctx("Хочу відкрити кав'ярню за три місяці.")))
    assert isinstance(out[0], RoutingEvent)
    assert (out[0].decision.kind, out[0].decision.card_id, out[0].decision.rev.rev) == (
        "choose",
        "pre-mortem",
        1,
    )
    assert isinstance(out[-1], FacilitatorUpdate)
    assert out[-1].current_phase_id in phases(current, "pre-mortem")


# routing.json: its shape after an offer and a choose through workspace
def test_routing_json_has_the_decisions_in_the_shape_of_the_artifact(tmp_path: Path) -> None:
    store, k = seeded_knowledge(tmp_path)
    ref = new_topic(store)
    first = phases(k, "issue-tree")[0]
    model = Model(
        router=lambda no, text: (
            choose_raw("issue-tree") if text == "Давай перше." else offer_raw("issue-tree", "is-is-not")
        ),
        facilitator=lambda no, text: fac_raw(first),
    )
    facilitate = functools.partial(respond, knowledge=k, llm=model)
    one = saved_no(
        drain(workspace.reply(store, facilitate, ALICE, ref, "Не розумію, де губляться гроші.", at(1)))
    )
    two = saved_no(drain(workspace.reply(store, facilitate, ALICE, ref, "Давай перше.", at(2))))
    rev = {"rev": 1, "n": k.n}
    assert routing_file(tmp_path, ref) == {
        "decisions": [
            {
                "turn": one,
                "rev": rev,
                "kind": "offer",
                "profile": PROFILE,
                "candidates": [
                    {"card_id": "issue-tree", "why": why_of("issue-tree")},
                    {"card_id": "is-is-not", "why": why_of("is-is-not")},
                ],
                "card_id": None,
                "end": None,
                "why": ROUTER_WHY,
            },
            {
                "turn": two,
                "rev": rev,
                "kind": "choose",
                "profile": PROFILE,
                "candidates": [],
                "card_id": "issue-tree",
                "end": None,
                "why": ROUTER_WHY,
            },
        ]
    }


# S3 must not change pre-mortem.yaml (the sealed S1 test holds its blob)
def test_pre_mortem_card_is_the_sealed_blob(tmp_path: Path) -> None:
    blob = subprocess.run(
        ["git", "hash-object", str(CARDS / "pre-mortem.yaml")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert blob.startswith("8f52b66a")


# ------------------------------------------------------------------ Acceptance criteria


# AC1: 18 cards; the F6 schema takes them; seeding works — a new revision of the Knowledge
def test_ac1_eighteen_cards_seed_as_revision_1_and_publish_onto_a_one_card_store_as_revision_2(
    tmp_path: Path,
) -> None:
    _, k = seeded_knowledge(tmp_path / "fresh")
    assert (k.rev, sorted(k.cards)) == (1, CARD_IDS)
    old_cards = tmp_path / "old-cards"
    old_cards.mkdir()
    shutil.copy(CARDS / "pre-mortem.yaml", old_cards / "pre-mortem.yaml")
    store = LocalStorage(tmp_path / "server")
    assert knowledge.seed(store, old_cards)
    assert sorted(knowledge.current(store).cards) == ["pre-mortem"]
    assert knowledge.publish(store, CARDS) == 2
    after = knowledge.current(store)
    assert (after.rev, sorted(after.cards)) == (2, CARD_IDS)
    assert after.cards["pre-mortem"] == k.cards["pre-mortem"]
    assert knowledge.publish(store, CARDS) is None
    assert knowledge.current(store).rev == 2


# AC2: profile, 2–3 ways with an explanation, the person's choice, «another way»,
# routing.json with the revision
def test_ac2_offer_another_way_then_choice_through_workspace_with_the_real_cards(tmp_path: Path) -> None:
    store, k = seeded_knowledge(tmp_path)
    ref = new_topic(store)
    lead = phases(k, "is-is-not")[0]

    def router(no: int, text: str) -> str:
        if text == "Інакше, будь ласка.":
            return offer_raw("five-whys", "is-is-not")
        if text == "Давай друге.":
            return choose_raw("is-is-not")
        return offer_raw("issue-tree", "complexity-sensemaking")

    model = Model(router=router, facilitator=lambda no, text: fac_raw(lead, reply="Де саме це проявляється?"))
    facilitate = functools.partial(respond, knowledge=k, llm=model)
    first = drain(workspace.reply(store, facilitate, ALICE, ref, "Продажі впали, не знаю чому.", at(1)))
    assert "".join(e.text for e in first if isinstance(e, workspace.Delta)) == OFFER_REPLY
    drain(workspace.reply(store, facilitate, ALICE, ref, "Інакше, будь ласка.", at(2)))
    third = drain(workspace.reply(store, facilitate, ALICE, ref, "Давай друге.", at(3)))
    assert "".join(e.text for e in third if isinstance(e, workspace.Delta)) == "Де саме це проявляється?"
    other_call = model.router_calls[1]
    assert "issue-tree" in other_call.frame and "complexity-sensemaking" in other_call.frame
    [lead_call] = model.stream_calls
    assert knowledge.card_prompt(k.cards["is-is-not"]) in lead_call.system
    decisions = routing_file(tmp_path, ref)["decisions"]  # type: ignore[index]
    assert [(d["kind"], d["card_id"]) for d in decisions] == [
        ("offer", None),
        ("offer", None),
        ("choose", "is-is-not"),
    ]
    assert [[c["card_id"] for c in d["candidates"]] for d in decisions[:2]] == [
        ["issue-tree", "complexity-sensemaking"],
        ["five-whys", "is-is-not"],
    ]
    assert all(d["rev"] == {"rev": 1, "n": k.n} and d["profile"] == PROFILE for d in decisions)
    conversation = (tmp_path / "users" / ALICE.id / ref.topic_id / "conversation.md").read_text(
        encoding="utf-8"
    )
    assert OFFER_REPLY in conversation


# AC3: a topic that was mid Pre-mortem without routing.json (the owner's) reaches the router; a card that does
# not fit hands the turn back to the router on the next reply
def test_ac3_a_topic_without_routing_json_reaches_the_router_and_a_card_that_does_not_fit_goes_back_to_it(
    tmp_path: Path,
) -> None:
    store, k = seeded_knowledge(tmp_path)
    ref = new_topic(store)

    def old_facilitator(c: FacilitationContext) -> Iterator[Any]:
        yield ReplyDelta("Уявіть, що минув рік і план провалився.")
        yield FacilitatorUpdate(
            reply="Уявіть, що минув рік і план провалився.",
            current_phase_id=phases(k, "pre-mortem")[0],
            phase_exit_met=False,
            map_updates=[],
        )

    owner_turns = [
        "Мені треба заробити багато грошей, роботу не знайти.",
        "Давай почнемо з пошуку варіантів.",
    ]
    for i, text in enumerate(owner_turns):
        drain(workspace.reply(store, old_facilitator, ALICE, ref, text, at(i + 1)))
    assert routing_file(tmp_path, ref) is None

    def router(no: int, text: str) -> str:
        return (
            choose_raw("opportunity-tree")
            if text == "Давай шукати варіанти."
            else offer_raw("goal-to-plan", "wrap-decision")
        )

    model = Model(
        router=router, facilitator=lambda no, text: fac_raw(None, reply="Що для вас зараз найважливіше?")
    )
    facilitate = functools.partial(respond, knowledge=k, llm=model)
    drain(workspace.reply(store, facilitate, ALICE, ref, "Давай шукати варіанти.", at(3)))
    after_end = drain(
        workspace.reply(store, facilitate, ALICE, ref, "Мені важливо швидко отримати гроші.", at(4))
    )
    assert [c.text for c in model.router_calls] == [
        "Давай шукати варіанти.",
        "Мені важливо швидко отримати гроші.",
    ]
    decisions = routing_file(tmp_path, ref)["decisions"]  # type: ignore[index]
    assert [(d["kind"], d["card_id"], d["end"]) for d in decisions] == [
        ("choose", "opportunity-tree", None),
        ("end", "opportunity-tree", "not_fit"),
        ("offer", None, None),
    ]
    assert decisions[0]["turn"] == decisions[1]["turn"] < decisions[2]["turn"] == saved_no(after_end)


# AC3: the owner's conversation t-d824f508a729 — in the report, the ways offered and when they changed
def test_ac3_the_report_of_the_owner_topic_names_the_offered_ways_and_the_choice() -> None:
    reports = sorted((ARTIFACTS / "card-conversations").glob("*/owner-t-d824f508a729.md"))
    assert reports, "no report of the owner's topic t-d824f508a729"
    text = reports[-1].read_text(encoding="utf-8")
    named = {cid for cid in CARD_IDS if cid in text}
    assert len(named) >= 2, named
    assert "offer" in text and "choose" in text


# AC4: the set of situations was run; the report has a table by card and the most frequent confusions
def test_ac4_the_newest_router_eval_report_has_a_row_for_every_card_and_its_confusions() -> None:
    reports = sorted((ARTIFACTS / "router-eval").glob("*.md"))
    assert reports, "no router-eval report"
    text = reports[-1].read_text(encoding="utf-8")
    rows = [line for line in text.splitlines() if line.startswith("|")]
    for cid in sorted(TASK_302_IDS):
        assert any(f"`{cid}`" in row or f"| {cid} |" in row for row in rows), cid
    assert "плутанин" in text.lower()
    assert (reports[-1].with_suffix(".json")).is_file()


# AC5: every card — at least one live conversation; the links are in the report
def test_ac5_a_live_conversation_report_exists_for_every_card_with_its_index_row() -> None:
    runs = [d for d in sorted((ARTIFACTS / "card-conversations").iterdir()) if d.is_dir()]
    for cid in sorted(TASK_302_IDS):
        holding = [d for d in runs if (d / f"{cid}.md").is_file()]
        assert holding, f"no live conversation of {cid}"
        assert f"({cid}.md)" in (holding[-1] / "index.md").read_text(encoding="utf-8"), cid


# AC6 (closing step): first the Job `cards` (a new revision), then the service restarted reads it
def test_ac6_job_cards_then_a_restarted_service_routes_with_revision_2(tmp_path: Path) -> None:
    environ = local_environ(tmp_path / "data")
    old_cards = tmp_path / "old-cards"
    old_cards.mkdir()
    shutil.copy(CARDS / "pre-mortem.yaml", old_cards / "pre-mortem.yaml")
    assert job.run(["seed"], environ, old_cards, lambda: at(0)) == 0
    before = build_deps(environ, CARDS)
    assert job.run(["cards"], environ, CARDS, lambda: at(1)) == 0
    after = build_deps(environ, CARDS)
    for deps, rev, count in ((before, 1, 1), (after, 2, len(CARD_IDS))):
        bound: Any = deps.facilitate
        assert bound.keywords["knowledge"].rev == rev
        assert len(bound.keywords["knowledge"].cards) == count
        ref = new_topic(deps.storage)
        drain(workspace.reply(deps.storage, deps.facilitate, ALICE, ref, "Хочу відкрити кав'ярню.", at(2)))
        decisions = routing_file(tmp_path / "data", ref)["decisions"]  # type: ignore[index]
        assert [d["rev"]["rev"] for d in decisions] == [rev]
