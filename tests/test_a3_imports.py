"""A3.1 guard: import-linter keeps the M3 arrows (no cycles, layers point down, forbidden arrows absent)."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_lint_imports_keeps_every_contract() -> None:
    command = shutil.which("lint-imports") or str(Path(sys.executable).parent / "lint-imports")
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    result = subprocess.run([command, "--no-cache"], cwd=ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
