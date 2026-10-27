"""Disputed catch-up test of knowledge-versions (question Q1).

Does the smoke script itself write its output to `.engine/artifacts/knowledge-versions/smoke.txt`?
The reading taken: yes — a run writes the file, and it holds every line the script printed.
The repository's file is put back after the test.
"""

from pathlib import Path

from kv_catchup_smoke_run import ARTIFACT, keep_artifact, run_smoke


def test_smoke_writes_what_it_prints_to_the_artifact(tmp_path: Path) -> None:
    with keep_artifact():
        ARTIFACT.unlink(missing_ok=True)
        result, _ = run_smoke(tmp_path)
        assert result.returncode == 0, result.stdout + result.stderr
        assert ARTIFACT.exists(), "the run did not write the artifact"
        written = ARTIFACT.read_text(encoding="utf-8")
    for line in result.stdout.splitlines():
        if line.strip():
            assert line.strip() in written, line
