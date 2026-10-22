"""Seam 5 of skel-web: every `node --test` file of the page JS passes (node missing → failure, not skip)."""

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILES = sorted((ROOT / "tests" / "contract" / "skel_web").glob("*.test.mjs"))


def test_node_tests_of_conversation_js_pass() -> None:
    node = os.environ.get("THINKHOW_NODE") or shutil.which("node")
    assert node, "node not found on PATH nor in THINKHOW_NODE: the exit of skel-web depends on node --test"
    assert FILES, "no *.test.mjs file found"
    proc = subprocess.run(
        [node, "--test", *map(str, FILES)], capture_output=True, text=True, timeout=300, cwd=ROOT
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_conversation_js_puts_no_markup_into_the_page() -> None:
    source = (ROOT / "src" / "thinkhow" / "web" / "static" / "conversation.js").read_text(encoding="utf-8")
    assert "innerHTML" not in source and "insertAdjacentHTML" not in source
