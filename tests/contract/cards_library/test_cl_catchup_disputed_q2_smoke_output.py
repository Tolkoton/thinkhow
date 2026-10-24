"""Disputed catch-up test of cards-library (question Q2): does the output of the smoke («Вивід — …») show
the two Job log lines the exit criterion names — `cards_published` with `rev: 2`, then with `rev: null`?
This file takes that reading; the other reading is that the output need not carry the Job's log lines.
Slice tester; written from the contract, not the code. stdout and stderr are read together.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "smoke_test_cards_library.py"
REV_2 = re.compile(r"""rev["']?\s*[:=]\s*2\b""")
REV_NULL = re.compile(r"""rev["']?\s*[:=]\s*(null|None)\b""")


def test_q2_smoke_output_shows_cards_published_with_rev_2_then_rev_null(tmp_path: Path) -> None:
    env = dict(os.environ, TMPDIR=str(tmp_path), TEMP=str(tmp_path), TMP=str(tmp_path))
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
    )
    assert result.returncode == 0, result.stderr
    lines = [
        line for line in (result.stdout + "\n" + result.stderr).splitlines() if "cards_published" in line
    ]
    first_2 = next((i for i, line in enumerate(lines) if REV_2.search(line)), None)
    assert first_2 is not None, f"no cards_published line with rev 2 in the output: {lines}"
    assert any(REV_NULL.search(line) for line in lines[first_2 + 1 :]), (
        f"no cards_published line with rev null after the rev 2 line: {lines}"
    )
