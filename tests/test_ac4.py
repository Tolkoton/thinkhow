"""AC4 of the walking skeleton (task 105): the four A3 guards, one test each, run as they are (S7 Q2).

Each test runs an existing check in a subprocess of this same venv and needs it green, so a broken item shows
by the name of its AC4 point.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = Path(sys.executable).parent


def run(command: list[str]) -> None:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=600)
    assert result.returncode == 0, result.stdout + result.stderr


def pytest(*ids: str) -> None:
    run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *ids])


def test_ac4_no_cycles_between_the_parts() -> None:
    run([str(BIN / "lint-imports"), "--no-cache"])


def test_ac4_only_platform_imports_a_google_sdk() -> None:
    pytest("tests/test_a3_google_sdk.py")


def test_ac4_people_folders_written_only_by_workspace_foreign_topic_hidden_owner_sees_all() -> None:
    pytest(
        "tests/test_a3_guards.py::test_users_paths_are_built_only_by_workspace",
        "tests/contract/skel_workspace/test_skelw_invariants.py::test_I2_nobody_reads_or_writes_a_foreign_topic_owner_only_reads",
    )


def test_ac4_knowledge_changes_only_through_knowledge() -> None:
    pytest("tests/test_a3_guards.py::test_knowledge_files_are_written_only_by_knowledge")
