"""Block tests of walking-skeleton: one per line of «Inter-slice contracts», one for AC4.

Slice tester, mode `block`; from `.engine/architecture/feature/walking-skeleton.md` and the public signatures,
not the bodies. Every test drives two or more blocks together through the seam the line names.
"""

from __future__ import annotations

import ast
import dataclasses
import functools
import inspect
import json
import os
import subprocess
import sys
from collections.abc import Iterable, Mapping
from datetime import timedelta
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from wsblock_fakes import (
    CARDS,
    NOW,
    REPO,
    FakeFacilitate,
    RecordingLlm,
    RecordingStorage,
    local_environ,
    sse_events,
)

import thinkhow.learning.local as learning_local
import thinkhow.web.local as web_local
from thinkhow import knowledge, workspace
from thinkhow.access import CurrentUser
from thinkhow.facilitation import respond
from thinkhow.facilitation.types import (
    Facilitate,
    FacilitationContext,
    FacilitatorUpdate,
    ProblemMap,
    ReplyDelta,
)
from thinkhow.facilitation.types import Turn as FTurn
from thinkhow.learning import job
from thinkhow.learning.analyze import analyze
from thinkhow.platform.identity import FixedIdentity, IapIdentity, Identity
from thinkhow.platform.llm import KnowledgeRev, ScriptedLlm
from thinkhow.platform.llm import Turn as LlmTurn
from thinkhow.web.app import build_deps
from thinkhow.web.server import create_app

ALICE = CurrentUser(id="alice-1", email="alice@example.com", is_owner=False)
BOB = CurrentUser(id="bob_2", email="bob@example.com", is_owner=False)


def drain[T](events: Iterable[T]) -> list[T]:
    return list(events)


def chain_facilitate(storage: RecordingStorage, llm: RecordingLlm) -> Facilitate:
    return functools.partial(respond, knowledge=knowledge.current(storage), llm=llm)


def client_as(environ: dict[str, str], identity: Identity | None = None, **replace: Any) -> TestClient:
    deps = build_deps(environ, CARDS)
    if identity is not None:
        replace["identity"] = FixedIdentity(identity)
    if replace:
        deps = dataclasses.replace(deps, **replace)
    client = TestClient(create_app(deps), follow_redirects=False, raise_server_exceptions=False)
    client.post("/language", data={"code": "uk-UA"})  # F13: the person has chosen a language before the pages
    return client


# S1 → S2/S4/S6 — Storage
def test_s1_storage_protocol_is_the_one_door_of_knowledge_workspace_and_learning(tmp_path: Path) -> None:
    store = RecordingStorage(tmp_path)
    assert knowledge.seed(store, CARDS) is True
    seed_writes = store.writes()
    assert seed_writes and all(b == "system" and p.startswith("knowledge/") for _, b, p in seed_writes)

    llm = RecordingLlm(ScriptedLlm(web_local.local_script))
    before = len(store.calls)
    workspace.ensure_profile(store, ALICE)
    topic = workspace.create_topic(store, ALICE, "Кав'ярня", NOW)
    ref = workspace.TopicRef(ALICE.id, topic)
    drain(workspace.reply(store, chain_facilitate(store, llm), ALICE, ref, "Хочу кав'ярню.", NOW))
    ws_writes = [c for c in store.calls[before:] if c[0] in ("write", "create_if_absent")]
    assert ws_writes and all(b == "users" and p.startswith("alice-1/") for _, b, p in ws_writes)

    before = len(store.calls)
    report = analyze(store, ScriptedLlm(learning_local.local_script), NOW + timedelta(minutes=2))
    assert report.written == 1
    learn_writes = [c for c in store.calls[before:] if c[0] in ("write", "create_if_absent")]
    assert learn_writes == [("write", "system", f"learning/observations/alice-1/{topic}/t1-t2.json")]
    assert {b for _, b, _ in store.calls} <= {"users", "system"}
    assert (tmp_path / "system" / "learning" / "observations" / "alice-1" / topic / "t1-t2.json").is_file()
    assert (tmp_path / "users" / "alice-1" / topic / "conversation.md").is_file()


# S1 → S3/S6 — Llm
def test_s1_llm_protocol_serves_facilitation_and_learning_and_unavailable_reaches_workspace_as_failed(
    tmp_path: Path,
) -> None:
    store = RecordingStorage(tmp_path)
    knowledge.seed(store, CARDS)
    llm = RecordingLlm(ScriptedLlm(web_local.local_script), fail_streams=1)
    facilitate = chain_facilitate(store, llm)
    topic = workspace.create_topic(store, ALICE, "Тема", NOW)
    ref = workspace.TopicRef(ALICE.id, topic)

    failed = drain(workspace.reply(store, facilitate, ALICE, ref, "Перша репліка.", NOW))
    assert failed[0] == workspace.Saved(1)
    assert failed[-1] == workspace.Failed("LlmUnavailable")

    answered = drain(workspace.retry(store, facilitate, ALICE, ref, NOW + timedelta(seconds=5)))
    assert answered[-1] == workspace.Answered(2)
    shown = "".join(e.text for e in answered if isinstance(e, workspace.Delta))
    assert shown
    assert len(llm.stream_calls) == 2
    for call in llm.stream_calls:
        assert all(isinstance(t, LlmTurn) for t in call["contents"])
        assert issubclass(call["schema"], FacilitatorUpdate)

    learn = RecordingLlm(ScriptedLlm(learning_local.local_script))
    report = analyze(store, learn, NOW + timedelta(minutes=2))
    assert (report.written, report.failed) == (1, 0)
    assert len(learn.generate_calls) == 1 and learn.stream_calls == []
    assert all(isinstance(t, LlmTurn) for t in learn.generate_calls[0]["contents"])


# S1 → S5 — identity
def test_s1_identity_is_the_only_source_of_the_person_in_web(tmp_path: Path) -> None:
    environ = local_environ(tmp_path)
    client = client_as(environ)
    location = client.post("/topics", data={"title": "Своя"}).headers["location"]
    assert location.startswith("/topics/local-owner/t-")
    profile = json.loads((tmp_path / "users" / "local-owner" / "profile.json").read_text(encoding="utf-8"))
    assert profile["email"] == "owner@localhost"

    def never(token: str, audience: str) -> Mapping[str, object]:
        raise AssertionError("verify must not be reached without the IAP header")

    iap = IapIdentity("/projects/1/locations/europe-west3/services/thinkhow", never)
    deps = dataclasses.replace(build_deps(environ, CARDS), identity=iap)
    guarded = TestClient(create_app(deps), follow_redirects=False, raise_server_exceptions=False)
    users_before = sorted(p.name for p in (tmp_path / "users").iterdir())
    response = guarded.post(
        "/topics", data={"title": "Чужа"}, headers={"x-goog-authenticated-user-id": "x:evil"}
    )
    assert response.status_code == 401
    assert sorted(p.name for p in (tmp_path / "users").iterdir()) == users_before


# S2 → S1 (by value) — rev_pair
def test_s2_rev_pair_is_the_platform_knowledge_rev_the_model_call_carries(tmp_path: Path) -> None:
    store = RecordingStorage(tmp_path)
    knowledge.seed(store, CARDS)
    current = knowledge.current(store)
    assert current.rev == 1
    pair = current.rev_pair()
    assert type(pair) is KnowledgeRev
    assert (pair.rev, pair.n) == (current.rev, current.n)
    llm = RecordingLlm(ScriptedLlm(web_local.local_script))
    list(respond(FacilitationContext("pre-mortem", [], ProblemMap(), 1, "План."), current, llm))
    assert [c["rev"] for c in llm.stream_calls] == [KnowledgeRev(current.rev, current.n)]


# S2 → S3 — CurrentKnowledge, Card, card_prompt
def test_s2_current_knowledge_reaches_facilitation_as_the_card_prompt(tmp_path: Path) -> None:
    store = RecordingStorage(tmp_path)
    knowledge.seed(store, CARDS)
    current = knowledge.current(store)
    card = current.cards["pre-mortem"]
    assert isinstance(card, knowledge.Card)
    assert current.memory == []
    for phase in card.facilitator.phases:
        assert phase.id and phase.goal and phase.exit
    llm = RecordingLlm(ScriptedLlm(web_local.local_script))
    ctx = FacilitationContext("pre-mortem", [], ProblemMap(), 1, "Хочу відкрити кав'ярню.")
    out = list(respond(ctx, current, llm))
    assert isinstance(out[-1], FacilitatorUpdate)
    assert len(llm.stream_calls) == 1
    assert knowledge.card_prompt(card) in llm.stream_calls[0]["system"]


# S3 → S5 — the binding in the composition root
def test_s3_web_binds_respond_into_a_facilitate(tmp_path: Path) -> None:
    deps = build_deps(local_environ(tmp_path), CARDS)
    assert isinstance(deps.facilitate, functools.partial) and deps.facilitate.func is respond
    assert set(deps.facilitate.keywords) == {"knowledge", "llm"}
    ctx = FacilitationContext("pre-mortem", [], ProblemMap(), 1, "Хочу відкрити кав'ярню.")
    out = list(deps.facilitate(ctx))
    deltas = [e for e in out[:-1]]
    assert all(isinstance(e, ReplyDelta) for e in deltas) and deltas
    update = out[-1]
    assert isinstance(update, FacilitatorUpdate)
    assert "".join(d.text for d in deltas) == update.reply
    phase_ids = [p.id for p in deps.facilitate.keywords["knowledge"].cards["pre-mortem"].facilitator.phases]
    assert update.current_phase_id in phase_ids


# S3 → S4 — the types of thinkhow.facilitation.types
def test_s3_workspace_hands_facilitate_a_context_and_applies_its_update(tmp_path: Path) -> None:
    store = RecordingStorage(tmp_path)
    fake = FakeFacilitate()
    topic = workspace.create_topic(store, ALICE, "Тема", NOW)
    ref = workspace.TopicRef(ALICE.id, topic)
    first = drain(workspace.reply(store, fake, ALICE, ref, "План один.", NOW))
    assert first == [
        workspace.Saved(1),
        workspace.Delta("Що "),
        workspace.Delta("далі?"),
        workspace.Answered(2),
    ]
    drain(workspace.reply(store, fake, ALICE, ref, "План два.", NOW + timedelta(minutes=1)))

    one, two = fake.contexts
    assert (one.card_id, one.turn_no, one.text, one.history) == ("pre-mortem", 1, "План один.", [])
    assert one.problem_map.items == []
    assert (two.card_id, two.turn_no, two.text) == ("pre-mortem", 3, "План два.")
    assert two.history == [FTurn("user", "План один."), FTurn("model", "Що далі?")]
    assert [i.id for i in two.problem_map.items] == ["i1"]
    saved = json.loads((tmp_path / "users" / "alice-1" / topic / "map.json").read_text(encoding="utf-8"))
    assert [(i["id"], i["turn"]) for i in saved["items"]] == [("i1", "t1"), ("i3", "t3")]

    imported: set[str] = set()
    for path in (REPO / "src" / "thinkhow" / "workspace").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            elif isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
    touched = {m for m in imported if m.startswith("thinkhow.facilitation")}
    assert touched == {"thinkhow.facilitation.types"}, touched


# S4 → S5 — workspace through the routes of web
def test_s4_workspace_signatures_and_its_flow_through_the_routes(tmp_path: Path) -> None:
    for name in (
        "list_topics",
        "create_topic",
        "open_topic",
        "ensure_profile",
        "all_topics_for_learning",
        "topic_sessions",
        "reply",
        "retry",
    ):
        params = list(inspect.signature(getattr(workspace, name)).parameters)
        assert params[0] == "storage", name
    for name in ("reply", "retry"):
        assert list(inspect.signature(getattr(workspace, name)).parameters)[1] == "facilitate", name

    environ = local_environ(tmp_path)
    base = build_deps(environ, CARDS)
    flaky = RecordingLlm(ScriptedLlm(web_local.local_script), fail_streams=1)
    facilitate = functools.partial(respond, knowledge=knowledge.current(base.storage), llm=flaky)
    client = TestClient(create_app(dataclasses.replace(base, facilitate=facilitate)), follow_redirects=False)
    client.post("/language", data={"code": "uk-UA"})  # F13: a language before the pages

    topic = client.post("/topics", data={"title": "Через маршрути"}).headers["location"]
    assert "Через маршрути" in client.get("/").text
    first = sse_events(client.post(f"{topic}/reply", data={"text": "Моя репліка."}).text)
    assert first[0] == ("saved", {"turn": 1})
    assert first[-1] == ("failed", {"reason": "LlmUnavailable"})
    again = sse_events(client.post(f"{topic}/retry").text)
    assert again[-1] == ("answered", {"turn": 2})
    conversation = (
        tmp_path / "users" / "local-owner" / topic.rsplit("/", 1)[-1] / "conversation.md"
    ).read_text(encoding="utf-8")
    assert conversation.count("<!-- thinkhow:turn 1 user") == 1
    assert conversation.count("<!-- thinkhow:turn 2 model") == 1
    assert conversation.count("Моя репліка.") == 1
    assert client.post(f"{topic}/close").status_code == 404  # task 202: the close route is gone
    assert client.post(f"{topic}/retry").status_code == 409


# S4 → S6 — read-only sessions for learning
def test_s4_learning_reads_every_topic_and_topic_sessions_numbered_across_the_topic(tmp_path: Path) -> None:
    store = RecordingStorage(tmp_path)
    fake = FakeFacilitate()
    a = workspace.TopicRef(ALICE.id, workspace.create_topic(store, ALICE, "Аліса", NOW))
    b = workspace.TopicRef(BOB.id, workspace.create_topic(store, BOB, "Боб", NOW))
    drain(workspace.reply(store, fake, ALICE, a, "Сесія один.", NOW))
    # task 202: no close; a new session begins after more than 24 h of silence
    drain(workspace.reply(store, fake, ALICE, a, "Сесія два.", NOW + timedelta(hours=25)))
    drain(workspace.reply(store, fake, BOB, b, "Ще відкрита.", NOW + timedelta(hours=25)))

    later = NOW + timedelta(hours=26)
    assert set(workspace.all_topics_for_learning(store)) == {a, b}
    sessions = workspace.topic_sessions(store, a, later)
    assert [s.no for s in sessions] == [1, 2]
    assert [[(t.no, t.role, t.text) for t in s.turns] for s in sessions] == [
        [(1, "user", "Сесія один."), (2, "model", "Що далі?")],
        [(3, "user", "Сесія два."), (4, "model", "Що далі?")],
    ]
    bob_sessions = workspace.topic_sessions(store, b, later)
    assert [[(t.no, t.role, t.text) for t in s.turns] for s in bob_sessions] == [
        [(1, "user", "Ще відкрита."), (2, "model", "Що далі?")],
    ]

    writes_before = len(store.writes())
    report = analyze(store, ScriptedLlm(learning_local.local_script), later)
    assert (report.written, report.failed) == (2, 0)
    assert sorted(p for _, _, p in store.writes()[writes_before:]) == sorted(
        [
            f"learning/observations/alice-1/{a.topic_id}/t1-t4.json",
            f"learning/observations/bob_2/{b.topic_id}/t1-t2.json",
        ]
    )
    for uid, topic_id, first, last in (("alice-1", a.topic_id, 1, 4), ("bob_2", b.topic_id, 1, 2)):
        obs = json.loads(
            (
                tmp_path / "system" / "learning" / "observations" / uid / topic_id / f"t{first}-t{last}.json"
            ).read_text()
        )
        assert (obs["first_turn"], obs["last_turn"]) == (first, last)
        assert first <= obs["turn"] <= last


# S6 → owner (G6)
def test_s6_observation_link_of_a_persons_topic_opens_the_turn_for_the_owner(tmp_path: Path) -> None:
    environ = local_environ(tmp_path)
    alice = client_as(environ, Identity("alice-1", "alice@example.com"))
    topic = alice.post("/topics", data={"title": "Аліса"}).headers["location"]
    alice.post(f"{topic}/reply", data={"text": "Хочу відкрити кав'ярню."})
    topic_id = topic.rsplit("/", 1)[-1]

    assert job.run(["analyze"], environ, CARDS, lambda: NOW + timedelta(days=400)) == 0
    file = tmp_path / "system" / "learning" / "observations" / "alice-1" / topic_id / "t1-t2.json"
    obs = json.loads(file.read_text(encoding="utf-8"))
    assert (obs["uid"], obs["topic_id"], obs["first_turn"], obs["last_turn"]) == ("alice-1", topic_id, 1, 2)
    assert obs["turn"] in (1, 2)
    assert obs["link"] == f"/topics/alice-1/{topic_id}#t{obs['turn']}"

    owner = client_as(environ)
    path, anchor = obs["link"].split("#", 1)
    page = owner.get(path)
    assert page.status_code == 200
    assert f'id="{anchor}"' in page.text


# S5, S6 → S7 — packages and entry points
def test_s7_packages_and_both_entry_points_start_with_pythonpath_src(tmp_path: Path) -> None:
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("THINKHOW_") and k not in ("K_SERVICE", "CLOUD_RUN_JOB")
    }
    env.update(local_environ(tmp_path), PYTHONPATH=str(REPO / "src"))
    probe = (
        "import importlib\n"
        "for p in ('web','access','workspace','facilitation','knowledge','learning','platform'):\n"
        "    importlib.import_module('thinkhow.' + p)\n"
        "from uvicorn.importer import import_from_string\n"
        "from fastapi import FastAPI\n"
        "assert isinstance(import_from_string('thinkhow.web.app:app'), FastAPI)\n"
    )
    imported = subprocess.run(
        [sys.executable, "-c", probe], cwd=REPO, env=env, capture_output=True, text=True, timeout=120
    )
    assert imported.returncode == 0, imported.stderr
    seeded = subprocess.run(
        [sys.executable, "-m", "thinkhow.learning.job", "seed"],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert seeded.returncode == 0, seeded.stderr
    assert (tmp_path / "system" / "knowledge" / "changes" / "000001.json").is_file()


# AC4 — at run time, across the blocks
def test_ac4_foreign_topic_hidden_owner_sees_all_knowledge_untouched_by_the_chain(tmp_path: Path) -> None:
    environ = local_environ(tmp_path)
    store = RecordingStorage(tmp_path)
    alice = client_as(environ, Identity("alice-1", "alice@example.com"), storage=store)
    bob = client_as(environ, Identity("bob_2", "bob@example.com"), storage=store)
    owner = client_as(environ, storage=store)

    topic = alice.post("/topics", data={"title": "Таємна тема Аліси"}).headers["location"]
    alice.post(f"{topic}/reply", data={"text": "Особиста репліка Аліси."})
    conv = tmp_path / "users" / "alice-1" / topic.rsplit("/", 1)[-1] / "conversation.md"
    before = conv.read_bytes()

    assert bob.get(topic).status_code == 404
    assert bob.post(f"{topic}/reply", data={"text": "Втручання."}).status_code == 404
    assert bob.post(f"{topic}/retry").status_code == 404  # task 202: the close route is gone; retry keeps G4
    assert "Таємна тема Аліси" not in bob.get("/").text
    assert conv.read_bytes() == before

    assert "Таємна тема Аліси" in owner.get("/").text
    page = owner.get(topic)
    assert page.status_code == 200 and "Особиста репліка Аліси." in page.text

    analyze(store, ScriptedLlm(learning_local.local_script), NOW + timedelta(days=400))
    knowledge_writes = [c for c in store.writes() if c[1] == "system" and c[2].startswith("knowledge/")]
    assert knowledge_writes == []
    assert all(
        p.startswith(("alice-1/", "local-owner/", "bob_2/")) for _, b, p in store.writes() if b == "users"
    )
