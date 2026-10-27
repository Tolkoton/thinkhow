"""Invariant tests of voice-synthesis (I1, I2). The table is copied by hand from the spike's `voices.out` and
`gemini_langs.out` (.engine/artifacts/spikes/voice-conversation-2026-10-27/), not from the code's sets."""

from typing import Any

import httpx
import pytest
from vs_fakes import FakePost, Tokens, auth_error, cloud, install_log_capture, ok

from thinkhow.platform.tts import TtsUnavailable, Voice, voice_for
from thinkhow.workspace import LANGUAGES

# voices.out: the codes with Chirp3-HD in their own line (46).
CHIRP3_EXACT = (
    "cs-CZ da-DK de-DE et-EE en-AU en-IN en-GB en-US es-ES es-US fr-CA fr-FR hr-HR id-ID it-IT sw-KE "
    "lv-LV lt-LT hu-HU nl-NL nb-NO pl-PL pt-BR ro-RO sk-SK sl-SI fi-FI sv-SE vi-VN tr-TR el-GR bg-BG "
    "sr-RS uk-UA he-IL mr-IN hi-IN bn-IN pa-IN gu-IN te-IN kn-IN ml-IN th-TH ko-KR ja-JP"
).split()
# The contract's ALIASES: a profile code → the Google code that has Chirp3-HD (3).
ALIASED = {"cmn-Hans-CN": "cmn-CN", "yue-Hant-HK": "yue-HK", "pa-Guru-IN": "pa-IN"}
# gemini_langs.out: "gemini-tts accepts: 21".
GEMINI = (
    "af-ZA az-AZ ca-ES es-419 fil-PH gl-ES is-IS ms-MY pt-PT be-BY mk-MK mn-MN hy-AM ar-EG fa-IR ne-NP "
    "bn-BD or-IN my-MM ka-GE am-ET"
).split()
# Neither: gemini_langs.out "refused: 18" minus the three aliases (15).
NONE = (
    "rup-BG bs-BA ceb ha-NG jv-ID kea-CV ln-CD mt-MT uz-UZ ky-KG tg-TJ kk-KZ sd-Arab-IN as-IN km-KH"
).split()


def _expected(code: str) -> Voice | None:
    if code in CHIRP3_EXACT:
        return Voice(f"{code}-Chirp3-HD-Kore", code, None)
    if code in ALIASED:
        google = ALIASED[code]
        return Voice(f"{google}-Chirp3-HD-Kore", google, None)
    if code in GEMINI:
        return Voice("Kore", code, "gemini-2.5-flash-tts")
    assert code in NONE, code
    return None


def test_I1_voice_for_every_profile_code_matches_the_spike_table() -> None:
    assert (len(CHIRP3_EXACT), len(ALIASED), len(GEMINI), len(NONE)) == (46, 3, 21, 15)
    codes = [lang.code for lang in LANGUAGES]
    assert len(codes) == 85
    assert set(codes) == set(CHIRP3_EXACT) | set(ALIASED) | set(GEMINI) | set(NONE)
    wrong = {code: voice_for(code) for code in codes if voice_for(code) != _expected(code)}
    assert wrong == {}


TEXTS = [
    "Zebrafinch квітучий барвінок ранковий.",
    "Однослово",
    "  Пробіливкраях  ",
]


def test_I2_no_tts_call_line_carries_the_spoken_text(monkeypatch: Any, capsys: Any) -> None:
    cap = install_log_capture(monkeypatch, capsys)
    calls = 0
    for text in TEXTS:
        # ok on Chirp 3 HD and on Gemini-TTS, after a retry, and every kind of unavailable
        cloud(FakePost([ok()])).synthesize(text, "uk-UA")
        cloud(FakePost([ok()])).synthesize(text, "ka-GE")
        cloud(FakePost([503, ok()])).synthesize(text, "uk-UA")
        for plan, token in (
            ([503, 503, 503], None),
            ([400], None),
            ([(200, {"other": 1})], None),
            ([httpx.ConnectError("refused")], None),
            ([ok()], Tokens(fail=auth_error())),
        ):
            with pytest.raises(TtsUnavailable):
                cloud(FakePost(plan), token=token).synthesize(text, "uk-UA")
        calls += 8
    lines = cap.lines("tts_call")
    assert len(lines) == calls
    outcomes = sorted({e["outcome"] for e in cap.events("tts_call")})
    assert outcomes == ["ok", "unavailable"]
    words = {w for text in TEXTS for w in text.split() if len(w) >= 5}
    for line in lines:
        for text in TEXTS:
            assert text not in line and text.strip() not in line
        for w in words:
            assert w not in line, (w, line)
