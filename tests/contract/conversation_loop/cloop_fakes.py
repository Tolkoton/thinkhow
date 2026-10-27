"""Helpers for the conversation-loop contract tests (slice tester). Built from the contract, not the code.

- run_node_test: run ONE named test of a `node --test` file; node missing is a failure, never a skip.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def run_node_test(file: Path, name: str) -> None:
    node = os.environ.get("THINKHOW_NODE") or shutil.which("node")
    if not node:
        pytest.fail("node not found on PATH nor in THINKHOW_NODE: these tests need node --test")
    pattern = "^" + re.escape(name) + "$"
    proc = subprocess.run(
        [node, "--test", "--test-reporter=tap", f"--test-name-pattern={pattern}", str(file)],
        capture_output=True,
        text=True,
        timeout=180,
        cwd=REPO,
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0 and "# pass 1" in out and "# fail 0" in out, out
