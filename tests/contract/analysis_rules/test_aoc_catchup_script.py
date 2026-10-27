"""Catch-up contract tests of `scripts/analyze_owner_conversation.py` (slice analysis-rules, Seam 4 and the
Seam line of the script). Slice tester: from the contract and the script's public names, not its bodies.

The script is run through its `main` with a fake model in place of Vertex (`make_llm`): the live call is the
builder's measurement; these tests fix what the script does around it — the input it rebuilds from «До», the
two analyzers on the same input, the artifact and the exit code. The owner's artifact is restored after each
test (`guard_artifact`).
"""

import ast
import os
import re
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from aoc_fakes import (
    OLD_COMMIT,
    OPP_TITLE,
    PASSING,
    REPO,
    Call,
    PlanLlm,
    finding_of,
    guard_artifact,
    run_main,
)

__all__ = ["guard_artifact"]  # the fixture is used by name

SKIP_DIRS = {".git", ".venv", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", "node_modules"}


def new_call(llm: PlanLlm) -> Call:
    calls = [c for c in llm.calls if c.new]
    assert len(calls) == 1, f"the new analyzer is called once on the topic: {len(calls)} calls"
    return calls[0]


def old_call(llm: PlanLlm) -> Call:
    calls = [c for c in llm.calls if not c.new]
    assert len(calls) == 1, f"the old analyzer is called once on the topic: {len(calls)} calls"
    return calls[0]


def line_before(lines: list[str], prefix: str) -> str:
    at = next(i for i, line in enumerate(lines) if line.startswith(prefix))
    assert at > 0, f"nothing before {prefix!r}"
    return lines[at - 1]


def table_rows(text: str) -> list[list[str]]:
    rows = []
    for line in text.splitlines():
        if line.strip().startswith("|"):
            rows.append([c.strip().strip("`*").strip() for c in line.strip().strip("|").split("|")])
    return rows


def traces_in_repo() -> set[Path]:
    found: set[Path] = set()
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        here = Path(root)
        for name in files:
            if name in {"conversation.md", "routing.json"} and ".engine" not in here.parts:
                found.add(here / name)
            elif "observations" in here.parts:
                found.add(here / name)
    return found


@pytest.mark.usefixtures("guard_artifact")
def test_exits_0_when_stuck_on_t5_t11_t15_and_none_on_t9_t13(monkeypatch: pytest.MonkeyPatch) -> None:
    code, _ = run_main(monkeypatch, PlanLlm())
    assert code == 0


@pytest.mark.usefixtures("guard_artifact")
def test_exits_1_when_stuck_is_missing_on_t5_t11_or_t15(monkeypatch: pytest.MonkeyPatch) -> None:
    for missing in (5, 11, 15):
        plan = [
            (n, "progress" if n == missing else kind, cause, worked) for n, kind, cause, worked in PASSING
        ]
        code, _ = run_main(monkeypatch, PlanLlm(plan=plan))
        assert code == 1, f"no stuck on t{missing}, exit {code}"


@pytest.mark.usefixtures("guard_artifact")
def test_exits_1_when_stuck_is_on_t9_or_t13(monkeypatch: pytest.MonkeyPatch) -> None:
    for extra in (9, 13):
        plan = [*PASSING, (extra, "stuck", "facilitation", False)]
        code, _ = run_main(monkeypatch, PlanLlm(plan=plan))
        assert code == 1, f"stuck on t{extra}, exit {code}"


@pytest.mark.usefixtures("guard_artifact")
def test_new_analyzer_input_is_the_18_turns_of_the_before_section(monkeypatch: pytest.MonkeyPatch) -> None:
    llm = PlanLlm()
    run_main(monkeypatch, llm)
    turns = new_call(llm).turn_lines()
    numbers = [int(re.match(r"#(\d+) ", line).group(1)) for line in turns]  # type: ignore[union-attr]
    assert numbers == list(range(1, 19))
    roles = [re.match(r"#\d+ (\S+):", line).group(1) for line in turns]  # type: ignore[union-attr]
    assert roles == ["людина", "фасилітатор"] * 9
    # texts of «До», not of «Після»
    assert "персонального асистента" in turns[0]
    assert turns[4] == "#5 людина: Ну, а звідки я знаю? Я не знаю. То якраз треба вияснити."
    assert turns[8] == "#9 людина: в межах місяця, наприклад"
    assert turns[14] == "#15 людина: Звідки я це можу знати?"
    assert "За опитуваннями малого бізнесу" in turns[17]


@pytest.mark.usefixtures("guard_artifact")
def test_routing_is_rebuilt_offer_of_three_on_1_and_choose_opportunity_tree_on_3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm = PlanLlm()
    run_main(monkeypatch, llm)
    lines = new_call(llm).lines()
    offer = line_before(lines, "#2 ")
    assert re.fullmatch(
        r"\[Роутер: запропоновано jobs-to-be-done, opportunity-tree, goal-to-plan\]", offer
    ), offer
    method = line_before(lines, "#4 ")
    assert re.fullmatch(r"\[Метод: .*\(opportunity-tree\)\]", method), method
    status = [line for line in lines if line.startswith("[Метод") or line.startswith("[Роутер")]
    assert len(status) == 2, status


@pytest.mark.usefixtures("guard_artifact")
def test_cards_are_seeded_so_the_method_line_carries_the_title(monkeypatch: pytest.MonkeyPatch) -> None:
    llm = PlanLlm()
    run_main(monkeypatch, llm)
    assert line_before(new_call(llm).lines(), "#4 ") == f"[Метод: {OPP_TITLE} (opportunity-tree)]"


@pytest.mark.usefixtures("guard_artifact")
def test_old_analyzer_of_c14fd9b_runs_on_the_same_turns(monkeypatch: pytest.MonkeyPatch) -> None:
    llm = PlanLlm()
    run_main(monkeypatch, llm)
    new, old = new_call(llm), old_call(llm)
    assert set(old.schema.model_json_schema()["properties"]) == {"finding", "worked", "cause", "anchor"}
    assert old.turn_lines() == new.turn_lines()
    source = subprocess.run(
        ["git", "show", f"{OLD_COMMIT}:src/thinkhow/learning/analyze.py"],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout
    tree = ast.parse(source)
    analyzer = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "ANALYZER" for t in node.targets)
    )
    assert old.system == analyzer
    assert new.system != analyzer


@pytest.mark.usefixtures("guard_artifact")
def test_artifact_names_old_commit_model_region_and_date(monkeypatch: pytest.MonkeyPatch) -> None:
    started = datetime.now(UTC)
    _, text = run_main(monkeypatch, PlanLlm())
    assert text, "the artifact is written"
    assert OLD_COMMIT in text
    assert "gemini-4-argon" in text
    assert re.search(r"(?<![A-Za-z0-9-])eu(?![A-Za-z0-9-])", text)
    days = {started.date().isoformat(), (started + timedelta(minutes=5)).date().isoformat()}
    assert any(day in text for day in days), days


@pytest.mark.usefixtures("guard_artifact")
def test_artifact_holds_the_raw_json_of_both_analyzers(monkeypatch: pytest.MonkeyPatch) -> None:
    llm = PlanLlm(marker="СИРИЙ-НОВИЙ", old_marker="СИРИЙ-СТАРИЙ")
    _, text = run_main(monkeypatch, llm)
    for n, kind, _, _ in PASSING:
        assert f'"{finding_of("СИРИЙ-НОВИЙ", n, kind)}"' in text, (n, kind)
    assert '"СИРИЙ-СТАРИЙ-одне"' in text


@pytest.mark.usefixtures("guard_artifact")
def test_artifact_table_has_kind_anchor_card_id_cause_of_every_observation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, text = run_main(monkeypatch, PlanLlm())
    rows = table_rows(text)
    for n, kind, cause, _ in PASSING:
        assert any({kind, f"t{n}", "opportunity-tree", cause} <= set(row) for row in rows), (
            f"no row with {kind}, t{n}, opportunity-tree, {cause}"
        )


@pytest.mark.usefixtures("guard_artifact")
def test_artifact_carries_the_attempt_number(monkeypatch: pytest.MonkeyPatch) -> None:
    _, text = run_main(monkeypatch, PlanLlm(), attempt=3)
    assert re.search(r"(?i)(спроб\w*|attempt)[^\n\d]{0,40}3(?!\d)", text), text[:600]


@pytest.mark.usefixtures("guard_artifact")
def test_topic_lives_in_a_temporary_folder_not_in_the_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    before = traces_in_repo()
    run_main(monkeypatch, PlanLlm())
    assert traces_in_repo() == before
