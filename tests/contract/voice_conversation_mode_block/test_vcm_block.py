"""Block tests of voice-conversation-mode: the lines of «Inter-slice contracts» and the acceptance criteria
that can be checked offline (the testing manager's point (b): the block closes the feature, O5).

Slice tester, mode `block`; from `.engine/architecture/feature/voice-conversation-mode.md` and the public
signatures, not the bodies. The REAL `conversation.js` (S2a) runs in page fakes; its requests go unchanged to
the REAL app under uvicorn in local mode (S1's `/speak` and `data-voice`, S3's `spoken` on `/reply`).
Expected values are written by hand. The tests that depend on a question are in
`test_vcm_block_disputed_q1_q2.py`; what only a live run or the report can show is a question (Q3–Q5).
"""

from __future__ import annotations

import base64
from typing import Any

import httpx
import pytest
from vcm_fakes import (
    NO_VOICE,
    POLISH,
    UKRAINIAN,
    answering,
    deduped,
    of_kind,
    one_turn,
    page_prefix,
    run_page,
    serve,
    words,
)

import thinkhow.platform.tts as tts_module
from thinkhow.platform.config import load_settings

LISTENING_SECTION = "# Людина слухає"

# ------------------------------------------------------------------ S1 → S2a: data-voice on #reply-form


def test_s1_to_s2a_reply_form_data_voice_from_the_server_decides_whether_the_page_offers_the_mode() -> None:
    with serve() as server:
        server.choose(UKRAINIAN)
        topic = server.new_topic()
        with_voice = server.reply_form(topic)
        server.choose(NO_VOICE)
        without_voice = server.reply_form(topic)
        assert with_voice.get("data-voice") == "yes", with_voice
        assert without_voice.get("data-voice") == "no", without_voice
        shown = run_page(server, page_prefix(with_voice), with_voice["data-voice"])
        hidden = run_page(server, page_prefix(without_voice), without_voice["data-voice"])
    assert shown["hidden"] is False, "the page hid the mode's button on data-voice=yes from the server"
    assert hidden["hidden"] is True, "the page offered the mode on data-voice=no from the server"


# ------------------------------------------------------------------ S1 → S2a: POST /speak → 200 audio/mpeg


def test_s1_to_s2a_every_sentence_the_page_posts_to_speak_comes_back_200_audio_mpeg_and_is_played() -> None:
    turn = one_turn()
    speak = of_kind(turn.page, "speak")
    assert len(speak) >= 1, turn.page["forwarded"]
    for f in speak:
        assert f["method"] == "POST", f
        assert f["status"] == 200, f
        assert f["type"].split(";")[0].strip() == "audio/mpeg", f
        assert f["sent"]["text"], f
        assert len(f["sent"]["text"].encode()) <= 1000, f
    # the server synthesized exactly the texts the page sent, in the person's language
    assert turn.tts_calls == [(f["sent"]["text"], UKRAINIAN) for f in speak]
    # the page decoded the very bytes the server gave and played one sound per sentence
    assert turn.page["decoded"] == [len(b) for b in turn.tts_returned]
    assert [f["bytes"] for f in speak] == [len(b) for b in turn.tts_returned]
    assert turn.page["started"] == len(speak)
    # nothing of the answer was left unspoken
    model = [x["text"] for x in turn.page["live"] if "model" in x["cls"]]
    assert len(model) == 1, turn.page["live"]
    assert words(" ".join(t for t, _ in turn.tts_calls)) == words(model[0])


# ------------------------------------------------------------------ S1 → S2a: the text limits of /speak


LONG_ANSWER = (
    "Перше коротке речення. "
    + ", ".join(["Друге речення має багато частин через коми"] * 40)
    + ". "
    + " ".join(["третєдовжелезнереченнябезжоднихком"] * 80)
    + "."
)


def test_s1_to_s2a_a_long_answer_reaches_speak_in_pieces_the_server_accepts_none_400() -> None:
    assert len(LONG_ANSWER.encode()) > 8000  # longer than any one /speak may carry
    with serve(facilitate=answering(LONG_ANSWER)) as server:
        server.choose(UKRAINIAN)
        form = server.reply_form(server.new_topic())
        page = run_page(server, page_prefix(form), form["data-voice"], tap=True, turn=True)
        calls = list(server.tts.calls)
    speak = of_kind(page, "speak")
    assert len(speak) >= 10, [len(f["sent"]["text"].encode()) for f in speak]
    assert [f["status"] for f in speak] == [200] * len(speak), [(f["status"], f["body"]) for f in speak]
    assert all(0 < len(f["sent"]["text"].encode()) <= 1000 for f in speak)
    assert words(" ".join(t for t, _ in calls)) == words(LONG_ANSWER)
    assert page["state_after_turn"] == "listening", page["stateLog"]


def test_s1_to_s2a_speak_takes_up_to_4000_bytes_and_answers_400_on_empty_or_longer() -> None:
    with serve() as server:
        server.choose(UKRAINIAN)
        at_limit = server.http.post("/speak", data={"text": "я" * 2000})  # 4000 bytes of UTF-8
        over = server.http.post("/speak", data={"text": "я" * 2001})  # 4002 bytes
        empty = server.http.post("/speak", data={"text": ""})
    assert at_limit.status_code == 200, at_limit.text
    assert at_limit.headers["content-type"].split(";")[0] == "audio/mpeg"
    assert over.status_code == 400, over.status_code
    assert empty.status_code == 400, empty.status_code


# ------------------------------------------------------------------ S3 → S2a: spoken on /reply


def test_s3_to_s2a_a_reply_from_the_mode_reaches_facilitation_as_spoken_an_ordinary_one_does_not() -> None:
    turn = one_turn()
    reply = of_kind(turn.page, "reply")
    assert len(reply) == 1 and reply[0]["status"] == 200, reply
    voice_text = of_kind(turn.page, "voice")[0]["body"]
    assert turn.spoken == [True], turn.spoken
    assert turn.texts == [reply[0]["sent"]["text"]] and reply[0]["sent"]["text"] in voice_text
    with serve() as server:
        server.choose(UKRAINIAN)
        form = server.reply_form(server.new_topic())
        page = run_page(server, page_prefix(form), form["data-voice"], normal="Звичайна репліка")
        spoken = [c.spoken for c in server.facilitate.contexts]
        texts = [c.text for c in server.facilitate.contexts]
    assert [f["status"] for f in of_kind(page, "reply")] == [200], page["forwarded"]
    assert spoken == [False], spoken
    assert texts == ["Звичайна репліка"], texts


# ------------------------------------------------------------------ acceptance criteria


def test_ac1_one_tap_on_then_two_turns_listen_send_speak_listen_without_a_touch_one_tap_off() -> None:
    with serve() as server:
        server.choose(UKRAINIAN)
        form = server.reply_form(server.new_topic())
        page = run_page(server, page_prefix(form), form["data-voice"], tap=True, turns=2, secondTap=True)
        spoken = [c.spoken for c in server.facilitate.contexts]
    # one tap on; after each turn the page is listening again by itself
    assert page["states_after_each_turn"] == ["listening", "listening"], page["stateLog"]
    assert deduped(page["stateLog"][:-1]) == ["listening", "hearing", "thinking", "speaking"] * 2 + [
        "listening"
    ]
    # each turn: recognized by /voice, sent as a reply at once, answered in voice
    assert [f["status"] for f in of_kind(page, "voice")] == [200, 200], page["forwarded"]
    assert [f["status"] for f in of_kind(page, "reply")] == [200, 200], page["forwarded"]
    assert spoken == [True, True], spoken
    assert len(of_kind(page, "speak")) >= 2 and page["started"] == len(of_kind(page, "speak"))
    assert [x["cls"] for x in page["live"]] == ["turn user", "turn model"] * 2, page["live"]
    # the same tap turns it off
    assert page["state"] in ("", "off"), page["stateLog"]
    assert page["error"] == "", page["error"]


def test_ac2_ordinary_mode_send_while_recording_only_gives_the_text_to_review() -> None:
    with serve() as server:
        server.choose(UKRAINIAN)
        form = server.reply_form(server.new_topic())
        page = run_page(server, page_prefix(form), form["data-voice"], dictate=True, sendAgain=True)
        spoken = [c.spoken for c in server.facilitate.contexts]
        texts = [c.text for c in server.facilitate.contexts]
    voice = of_kind(page, "voice")
    assert page["recording_after_mic"] == 1, "the microphone did not record in the ordinary mode"
    assert [f["status"] for f in voice] == [200], page["forwarded"]
    assert page["recording_after_send"] == 0, "«Надіслати» did not stop the recording"
    recognized = voice[0]["body"]
    assert page["field_after_dictation"] and page["field_after_dictation"] in recognized, page
    assert page["replies_after_dictation"] == 0, "«Надіслати» during recording sent the reply"
    # only the next «Надіслати» sends it, as an ordinary reply
    assert texts == [page["field_after_dictation"]] and spoken == [False], (texts, spoken)
    assert page["stateLog"] == [], page["stateLog"]


def test_ac3_in_the_mode_every_model_instruction_carries_the_listening_rules_and_all_is_spoken() -> None:
    turn = one_turn()
    assert turn.systems, "the model was not called"
    for system in turn.systems:
        assert system.count(LISTENING_SECTION) == 1, system
    model = [x["text"] for x in turn.page["live"] if "model" in x["cls"]]
    assert words(" ".join(t for t, _ in turn.tts_calls)) == words(model[0])
    with serve() as server:
        server.choose(UKRAINIAN)
        form = server.reply_form(server.new_topic())
        run_page(server, page_prefix(form), form["data-voice"], normal="Звичайна репліка")
        ordinary = list(server.llm.systems) if server.llm else []
    assert ordinary, "the model was not called"
    assert all(LISTENING_SECTION not in s for s in ordinary), (
        "the listening rules leaked into the ordinary mode"
    )


def test_ac4_the_voice_is_google_cloud_tts_on_eu_in_the_language_the_person_chose(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[tuple[str, Any]] = []

    def post(url: str, *args: Any, **kwargs: Any) -> httpx.Response:
        sent.append((url, kwargs.get("json")))
        content = {"audioContent": base64.b64encode(b"\xff\xf3 mp3 of google").decode()}
        return httpx.Response(200, json=content, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", post)
    monkeypatch.setattr(tts_module, "adc_token", lambda: lambda: "token")
    settings = load_settings(
        {"THINKHOW_USERS_BUCKET": "u", "THINKHOW_SYSTEM_BUCKET": "s", "THINKHOW_OWNER_EMAIL": "o@example.com"}
    )
    for code in (UKRAINIAN, POLISH):
        sent.clear()
        with serve(tts=tts_module.make_tts(settings)) as server:
            server.choose(code)
            form = server.reply_form(server.new_topic())
            page = run_page(server, page_prefix(form), form["data-voice"], tap=True, turn=True)
        speak = of_kind(page, "speak")
        assert speak and [f["status"] for f in speak] == [200] * len(speak), page["forwarded"]
        assert len(sent) == len(speak), sent
        for (url, body), f in zip(sent, speak, strict=True):
            assert httpx.URL(url).host == "eu-texttospeech.googleapis.com", url
            assert body["input"]["text"] == f["sent"]["text"], body
            assert body["voice"]["languageCode"] == code, body
        assert page["started"] == len(speak)


def test_ac5_five_turns_in_ukrainian_and_in_polish_without_a_touch_each_with_its_latency_marks() -> None:
    for code in (UKRAINIAN, POLISH):
        with serve() as server:
            server.choose(code)
            form = server.reply_form(server.new_topic())
            page = run_page(server, page_prefix(form), form["data-voice"], tap=True, turns=5)
            languages = {language for _, language in server.tts.calls}
        assert page["states_after_each_turn"] == ["listening"] * 5, (code, page["stateLog"])
        assert len(of_kind(page, "reply")) == 5 and len(of_kind(page, "voice")) == 5, page["forwarded"]
        assert languages == {code}, languages
        marks = [m for m in page["marks"] if m in ("talk:speech-end", "talk:voice-start")]
        assert marks == ["talk:speech-end", "talk:voice-start"] * 5, (code, page["marks"])
