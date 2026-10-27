"""Block tests of voice-conversation-mode with S2b conversation-resilience in place: the connections of the
block that S2b now consumes (S1's /speak 502, S3's spoken on /retry, S2a's states) and the acceptance criteria
whose offline form S2b changes (AC1 without a touch through failures, AC3 sources heard by name).

Slice tester, mode `block`; from `.engine/architecture/feature/voice-conversation-mode.md` and the public
signatures, not the bodies. The REAL `conversation.js` runs in the S2b page fakes; its requests go unchanged
to the REAL app under uvicorn in local mode, whose ports are replaced only where a test needs a failure.
Expected values are written by hand.
"""

from __future__ import annotations

import re
from typing import Any

from vcm_fakes import UKRAINIAN, of_kind, page_prefix, words
from vcm_s2b_fakes import FAIL, FailingAt, PlannedSpeech, attempts, run_s2b_page, serve_s2b

from thinkhow.facilitation.settle import sources_line
from thinkhow.facilitation.types import Source

THREE = ["Перше речення. ", "Друге речення. ", "Третє речення."]
OFF = ("", "off")


def _page(turns: int, **serve: Any) -> tuple[dict[str, Any], Any]:
    with serve_s2b(**serve) as (server, _speech):
        server.choose(UKRAINIAN)
        form = server.reply_form(server.new_topic())
        page = run_s2b_page(server, page_prefix(form), turns)
        return page, server


def _model_paragraphs(page: dict[str, Any]) -> list[str]:
    return [x["text"] for x in page["live"] if "model" in x["cls"]]


# ------------------------------------------------------------------ S1 → S2b: /speak 502 from the server


def test_s1_to_s2b_speak_502_from_the_server_skips_that_sentence_the_others_play_and_the_page_listens() -> (
    None
):
    page, server = _page(
        1,
        speech=PlannedSpeech(["Розкажи щось"]),
        tts=lambda inner: FailingAt(inner, {1}),
        facilitate=attempts([THREE]),
    )
    speak = of_kind(page, "speak")
    assert [f["status"] for f in speak] == [200, 502, 200], [(f["status"], f["sent"]) for f in speak]
    assert words(" ".join(f["sent"]["text"] for f in speak)) == words("".join(THREE))
    assert server.tts.failed == [speak[1]["sent"]["text"]]
    assert "Друге" in server.tts.failed[0]
    assert page["started"] == 2, "the two synthesized sentences did not both play"
    assert page["turns"][0]["state"] == "listening", page["stateLog"]
    assert not any(s in OFF for s in page["stateLog"]), page["stateLog"]
    assert _model_paragraphs(page) == ["".join(THREE)], page["live"]  # the text stays on the screen


# ------------------------------------------------------------------ S3 → S2b: spoken on /retry


def test_s3_to_s2b_a_failed_reply_is_retried_once_on_retry_with_spoken_1_and_the_retry_is_spoken() -> None:
    page, server = _page(
        1,
        speech=PlannedSpeech(["Розкажи щось"]),
        facilitate=attempts([None, ["Привіт, ти знаєш."]]),
    )
    reply, retry = of_kind(page, "reply"), of_kind(page, "retry")
    assert [f["status"] for f in reply] == [200] and "event: failed" in reply[0]["body"], reply
    assert len(retry) == 1 and retry[0]["status"] == 200, retry
    assert retry[0]["sent"].get("spoken") == "1", retry[0]["sent"]
    assert "event: answered" in retry[0]["body"], retry[0]["body"]
    # both attempts reached facilitation as spoken, on the same reply of the person
    assert [c.spoken for c in server.facilitate.contexts] == [True, True]
    assert [c.text for c in server.facilitate.contexts] == ["Розкажи щось", "Розкажи щось"]
    # what is heard is the retry, with no glued piece of the broken first attempt
    heard = " ".join(f["sent"]["text"] for f in of_kind(page, "speak"))
    assert words(heard) == ["Привіт", "ти", "знаєш"], heard
    assert page["turns"][0]["state"] == "listening", page["stateLog"]
    assert not any(s in OFF for s in page["stateLog"]), page["stateLog"]


def test_s3_to_s2b_a_reply_that_fails_again_on_retry_turns_the_mode_off_with_the_error_and_a_signal() -> None:
    page, server = _page(1, speech=PlannedSpeech(["Розкажи щось"]), facilitate=attempts([None]))
    assert len(of_kind(page, "reply")) == 1, page["forwarded"]
    retry = of_kind(page, "retry")
    assert len(retry) == 1 and retry[0]["sent"].get("spoken") == "1", retry
    assert "event: failed" in retry[0]["body"], retry[0]["body"]
    assert len(server.facilitate.contexts) == 2, "more than one automatic retry reached the server"
    assert page["state"] in OFF, page["stateLog"]
    assert page["error"].strip(), "the mode stopped with no error on the page"
    assert page["error_tones"] >= 1, "no error signal"


# ------------------------------------------------------------------ S2a → S2b: rules on the same transitions


def test_s2a_to_s2b_empty_or_failed_recognition_from_voice_returns_to_listening_and_the_next_turn_runs() -> (
    None
):
    page, server = _page(3, speech=PlannedSpeech(["", FAIL, "Розкажи щось"]), facilitate=attempts([THREE]))
    voice = of_kind(page, "voice")
    assert [f["status"] for f in voice[:2]] == [200, 502], [(f["status"], f["body"]) for f in voice]
    assert voice[0]["body"] and '"text":""' in voice[0]["body"].replace(" ", ""), voice[0]["body"]
    assert voice[2]["status"] == 200, voice[2]
    assert [t["state"] for t in page["turns"]] == ["listening", "listening", "listening"], page["stateLog"]
    assert not any(s in OFF for s in page["stateLog"]), page["stateLog"]
    # neither failure sent a reply; the third turn did, and was spoken
    assert [f["sent"]["text"] for f in of_kind(page, "reply")] == ["Розкажи щось"], page["forwarded"]
    assert [c.spoken for c in server.facilitate.contexts] == [True]
    assert words(" ".join(f["sent"]["text"] for f in of_kind(page, "speak"))) == words("".join(THREE))


# ------------------------------------------------------------------ acceptance criteria


def test_ac1_one_tap_then_turns_through_an_empty_recognition_and_a_failed_sentence_without_a_touch() -> None:
    page, server = _page(
        4,
        speech=PlannedSpeech(["Перша репліка", "", "Друга репліка", "Третя репліка"]),
        tts=lambda inner: FailingAt(inner, {1}),
        facilitate=attempts([THREE]),
    )
    assert page["state_after_tap"] == "listening", page["stateLog"]
    assert [t["state"] for t in page["turns"]] == ["listening"] * 4, page["stateLog"]
    assert not any(s in OFF for s in page["stateLog"]), page["stateLog"]
    reply = of_kind(page, "reply")
    assert [f["sent"]["text"] for f in reply] == ["Перша репліка", "Друга репліка", "Третя репліка"]
    assert [f["status"] for f in reply] == [200, 200, 200], reply
    assert [c.spoken for c in server.facilitate.contexts] == [True, True, True]
    speak = of_kind(page, "speak")
    assert len(speak) == 9 and [f["status"] for f in speak].count(502) == 1, [f["status"] for f in speak]
    assert page["started"] == 8, page["started"]
    assert [x["cls"] for x in page["live"]] == ["turn user", "turn model"] * 3, page["live"]


SOURCES = [
    Source("ADAC", "https://www.adac.de/rund-ums-fahrzeug/reifen/"),
    Source("Auto Bild", "https://autobild.de/x"),
]
ANSWER = "За даними [ADAC](https://www.adac.de/reifen) шини міняють восени. Перевірте протектор."


def test_ac3_the_sources_line_the_code_writes_is_not_heard_and_a_source_in_the_text_is_heard_by_name() -> (
    None
):
    line = sources_line(SOURCES)
    assert line.startswith("\n\nДжерела: ") and "https://" in line, line
    # the line arrives split inside its literal, as a stream may cut it
    deltas = [
        "За даними [ADAC](https://www.ad",
        "ac.de/reifen) шини міняють восени. ",
        "Перевірте протектор.",
        line[:4],
        line[4:],
    ]
    assert "".join(deltas) == ANSWER + line
    page, _server = _page(1, speech=PlannedSpeech(["Коли міняти шини?"]), facilitate=attempts([deltas]))
    speak = [f["sent"]["text"] for f in of_kind(page, "speak")]
    assert speak, page["forwarded"]
    heard = " ".join(speak)
    assert not re.search(r"Джерела|http|www\.|adac\.de|autobild", heard), heard
    assert words(heard) == ["За", "даними", "ADAC", "шини", "міняють", "восени", "Перевірте", "протектор"], (
        heard
    )
    # the screen keeps the whole answer with its sources line
    assert "Джерела" in _model_paragraphs(page)[0], page["live"]
    assert page["turns"][0]["state"] == "listening", page["stateLog"]
