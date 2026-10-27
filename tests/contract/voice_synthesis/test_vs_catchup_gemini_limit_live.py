"""Catch-up contract test of voice-synthesis: the spike `gemini_limit.py` on the real Gemini-TTS (`-m live`).

Written from the contract («Premise verified»: «Межа тексту: Gemini-TTS на `eu` — 4000 байт (400 понад це)»),
not from the code. The probe is run from the repository root; its output is what it prints and, if it
rewrites `gemini_limit.out`, that file — which is restored afterwards, so the builder's record stays as it
was. Only the 400 over 4000 bytes is required again: the 502 at ~3900 bytes is Google's passing answer, the
record keeps it (test_vs_catchup_gemini_limit.py).
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest
from vs_catchup_gemini_limit import RECORD, REPO, SCRIPT, sizes_and_answers


@pytest.mark.live
def test_gemini_limit_probe_on_eu_gets_400_naming_4000_bytes_for_every_size_over_4000() -> None:
    before = RECORD.read_bytes()
    mtime = RECORD.stat().st_mtime_ns
    try:
        done = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=REPO,
            env=dict(os.environ, PYTHONPATH=str(REPO / "src")),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=240,
        )
        rewritten = RECORD.read_text(encoding="utf-8") if RECORD.read_bytes() != before else ""
    finally:
        RECORD.write_bytes(before)
        os.utime(RECORD, ns=(mtime, mtime))
    assert done.returncode == 0, done.stdout + done.stderr
    found = sizes_and_answers(done.stdout + "\n" + rewritten)
    over = {size: answer for size, answer in found.items() if size > 4000}
    assert over, f"the probe gave no size over 4000 bytes: {done.stdout[-1500:]}"
    for size, (status, text) in over.items():
        assert status == 400, f"{size} bytes: {status}"
        assert "4000 bytes" in text, f"{size} bytes: the answer does not name the 4000-byte limit"
    print("\n".join(f"{size} bytes: {status}" for size, (status, _) in sorted(found.items())))
