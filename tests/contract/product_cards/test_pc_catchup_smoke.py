"""Catch-up contract tests of product-cards: the smoke script, offline (slice tester).

Written from the contract (.engine/slices/product-cards.md, «Seam (contract)» — the smoke line, «Hardest
seams» — Seam 5, «Exit criterion» — the smoke line), not the code. `route` is replaced by a scripted
double and the model refuses every call (`pc_smoke_fakes.py`); the real-model run is in
`test_pc_catchup_smoke_live.py`. What the smoke «друкує» is looked for in its stdout or in its output
file — either is accepted (question Q1 of the hand-in).
"""

import json
import os
import re
from pathlib import Path

import pytest
from pc_smoke_fakes import (
    ARTIFACT_PREFIX,
    ASK_REPLY,
    NEW_IDS,
    OFFER_REPLY,
    OWNER_TURN_1,
    REPO,
    WHY_DT,
    WHY_JTBD,
    Recorder,
    ask,
    choose,
    good_offer,
    offer,
    run_smoke,
)

SKIP_DIRS = {".git", ".venv", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", "node_modules"}
ARTIFACT_NAME = re.compile(re.escape(ARTIFACT_PREFIX) + r".+\.txt")


def llm_call_records(text: str) -> list[str]:
    found = []
    for line in text.splitlines():
        start = line.find("{")
        if start < 0:
            continue
        try:
            obj = json.loads(line[start:])
        except ValueError:
            continue
        if isinstance(obj, dict) and obj.get("event") == "llm_call":
            found.append(line)
    return found


def knowledge_changes_in_repo() -> set[Path]:
    found: set[Path] = set()
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        here = Path(root)
        if here.name == "changes" and here.parent.name == "knowledge":
            found.update(here / f for f in files)
    return found


def test_smoke_routes_on_knowledge_of_25_cards_with_the_7_new(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = Recorder([good_offer()])
    run = run_smoke(monkeypatch, tmp_path, fake)
    assert fake.calls, f"route was never called:\n{run.everything}"
    _, knowledge = fake.calls[0]
    assert len(knowledge.cards) == 25, sorted(knowledge.cards)
    assert [c for c in NEW_IDS if c not in knowledge.cards] == []


def test_smoke_seeds_a_temporary_local_storage_not_the_repository(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    before = knowledge_changes_in_repo()
    run = run_smoke(monkeypatch, tmp_path, Recorder([good_offer()]))
    assert run.code == 0, run.everything
    assert knowledge_changes_in_repo() == before, "the smoke seeded Knowledge into the repository"


def test_smoke_passes_turn_1_of_the_owner_verbatim(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake = Recorder([good_offer()])
    run = run_smoke(monkeypatch, tmp_path, fake)
    assert fake.calls, run.everything
    ctx, _ = fake.calls[0]
    assert ctx.text == OWNER_TURN_1


def test_smoke_exits_0_on_an_offer_of_2_known_cards(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run = run_smoke(monkeypatch, tmp_path, Recorder([good_offer()]))
    assert run.code == 0, run.everything


def test_smoke_exits_0_on_an_offer_of_3_known_cards(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    three = offer(("demand-test", WHY_DT), ("jobs-to-be-done", WHY_JTBD), ("pre-mortem", "що може зламатися"))
    run = run_smoke(monkeypatch, tmp_path, Recorder([three]))
    assert run.code == 0, run.everything


def test_smoke_exits_1_when_the_action_is_never_offer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = run_smoke(monkeypatch, tmp_path, Recorder([choose()]))
    assert run.code == 1, run.everything


def test_smoke_exits_1_on_an_offer_with_an_id_not_in_cards(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bad = offer(("demand-test", WHY_DT), ("sales-funnel", "вигадана картка"))
    run = run_smoke(monkeypatch, tmp_path, Recorder([bad]))
    assert run.code == 1, run.everything


def test_smoke_repeats_at_most_once_after_a_non_offer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = Recorder([ask(), ask("Друге уточнення?"), good_offer()])
    run = run_smoke(monkeypatch, tmp_path, fake)
    assert len(fake.calls) <= 2, f"route was asked {len(fake.calls)} times"
    assert run.code == 1, run.everything


def test_smoke_that_repeats_records_the_first_answer_in_the_artifact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = Recorder([ask(), good_offer()])
    run = run_smoke(monkeypatch, tmp_path, fake)
    assert run.code in (0, 1), run.everything
    if run.code == 0:
        assert len(fake.calls) == 2
        assert ASK_REPLY in run.artifact, "the first (non-offer) answer is not in the artifact"


def test_smoke_prints_action_candidates_with_why_text_and_new_cards_line(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = run_smoke(monkeypatch, tmp_path, Recorder([good_offer()]))
    assert run.code == 0, run.everything
    text = run.out + "\n" + run.artifact
    assert "offer" in text
    for cid, why in (("demand-test", WHY_DT), ("jobs-to-be-done", WHY_JTBD)):
        assert cid in text and why in text, f"candidate {cid} with its why is not printed"
    assert OFFER_REPLY in text
    lines = [line for line in text.splitlines() if "нові картки серед кандидатів" in line]
    assert lines, "no line «нові картки серед кандидатів: […]»"
    assert any("demand-test" in line and "jobs-to-be-done" not in line for line in lines), lines


def test_smoke_writes_its_output_to_a_product_cards_router_live_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = run_smoke(monkeypatch, tmp_path, Recorder([good_offer()]))
    assert run.code == 0, run.everything
    names = [n for n in run.artifacts if ARTIFACT_NAME.fullmatch(n)]
    assert names, f"no .engine/artifacts/spikes/{ARTIFACT_PREFIX}<час>.txt written: {sorted(run.artifacts)}"


def test_smoke_output_file_has_the_region_line_25_cards_the_7_new_ids_offer_and_candidates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = run_smoke(monkeypatch, tmp_path, Recorder([good_offer()]))
    assert run.code == 0, run.everything
    file = run.artifact
    assert any(re.search(r"\beu\b", line) for line in file.splitlines()), "no line with the region eu"
    assert re.search(r"\b25\b", file), "the number of cards of current (25) is not in the output file"
    assert [c for c in NEW_IDS if c not in file] == [], "not every new id is listed in the output file"
    assert "offer" in file
    assert "demand-test" in file and "jobs-to-be-done" in file


def test_smoke_does_not_write_an_llm_call_line_itself(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = run_smoke(monkeypatch, tmp_path, Recorder([good_offer()]))
    assert run.code == 0, run.everything
    # Prose or a heading that names llm_call is not a record; the port's log record is a JSON line with
    # "event": "llm_call" — with route replaced and the model refusing, none may appear.
    assert llm_call_records(run.everything) == [], "the script wrote an llm_call record itself"
