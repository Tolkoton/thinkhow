"""Catch-up contract test of product-cards: the smoke on the real model (`-m live`; slice tester).

Written from the contract («Hardest seams» Seam 5, «Exit criterion» — the smoke line), not the code. The
script is run as the exit criterion names it — `PYTHONPATH=src`, from the repository root — and judged by
its exit code and the output file it writes; the file this run wrote is left in place (it is the evidence).
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "smoke_test_product_cards.py"
SPIKES = REPO / ".engine" / "artifacts" / "spikes"


@pytest.mark.live
def test_smoke_on_gemini_4_argon_in_eu_exits_0_with_the_ports_llm_call_line_in_its_output_file() -> None:
    before = set(SPIKES.glob("product-cards-router-live-*.txt"))
    env = dict(os.environ, PYTHONPATH=str(REPO / "src"))
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=600,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    written = sorted(set(SPIKES.glob("product-cards-router-live-*.txt")) - before)
    assert written, "no output file .engine/artifacts/spikes/product-cards-router-live-<час>.txt"
    text = "\n".join(p.read_text(encoding="utf-8") for p in written)
    calls = [line for line in text.splitlines() if "llm_call" in line]
    assert calls, "no llm_call line in the output file"
    assert any("gemini-4-argon" in line for line in calls), calls
    assert any(re.search(r"\beu\b", line) for line in text.splitlines()), "no line with the region eu"
    assert "offer" in text
