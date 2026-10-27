"""Disputed catch-up test of notes-readers (slice tester), question Q1: does the smoke print the instructions
in full? «Goal» (2): «друкує інструкцію роутера … і фасилітатора для `five-whys` … і для `pre-mortem` … →
`.engine/artifacts/notes-readers/smoke.txt`». The reading taken: the whole text of each instruction is in the
artifact, not an excerpt or a summary of the check.
"""

from pathlib import Path

from nr_catchup_smoke_run import run_smoke


def _two_notes(memory: list[dict[str, object]]) -> bool:
    shape = sorted((str(r["audience"]), tuple(r["cards"])) for r in memory)  # type: ignore[call-overload]
    return shape == [("facilitator", ("five-whys",)), ("router", ("pre-mortem",))]


def test_smoke_artifact_holds_the_router_and_both_facilitator_instructions_in_full(tmp_path: Path) -> None:
    result, seen, artifact = run_smoke(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert artifact is not None
    router = [c["text"] for c in seen["router_calls"] if _two_notes(c["memory"])]
    assert router and any(t.strip() in artifact for t in router), "the router instruction is not in full"
    for cid in ("five-whys", "pre-mortem"):
        texts = [c["text"] for c in seen["system_calls"] if c["card"] == cid and _two_notes(c["memory"])]
        assert texts and any(t.strip() in artifact for t in texts), f"the facilitator of {cid} is not in full"
