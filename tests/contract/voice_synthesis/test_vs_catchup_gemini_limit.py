"""Catch-up contract test of voice-synthesis: the record of the spike `gemini_limit.py` (slice tester).

Written from the contract («Premise verified»: «Межа тексту: Gemini-TTS на `eu` — 4000 байт (400 понад це),
~3900 байт грузинської — 502 від Google (`gemini_limit.out`, та сама проба)»), not from the code. The record
the contract cites must hold what the contract reads from it; lines are `<n> bytes: <status> <answer…>`.
"""

from __future__ import annotations

from vs_catchup_gemini_limit import RECORD, sizes_and_answers


def test_gemini_limit_record_shows_400_over_4000_bytes_and_502_near_3900() -> None:
    found = sizes_and_answers(RECORD.read_text(encoding="utf-8"))
    over = {size: answer for size, answer in found.items() if size > 4000}
    assert over, f"the record holds no size over 4000 bytes: {sorted(found)}"
    for size, (status, text) in over.items():
        assert status == 400, f"{size} bytes: {status}"
        assert "4000 bytes" in text, f"{size} bytes: the answer does not name the 4000-byte limit"
    near = {size: answer for size, answer in found.items() if 3800 <= size <= 4000}
    assert any(status == 502 for status, _ in near.values()), f"no 502 for a size of ~3900 bytes: {near}"
