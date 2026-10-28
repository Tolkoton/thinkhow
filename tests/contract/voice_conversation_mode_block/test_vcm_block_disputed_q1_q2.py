"""Block tests of voice-conversation-mode that depend on a question of this hand-in (disputed; not
sealed before the answer). Slice tester, mode `block`; from the feature artifact
`.engine/architecture/feature/voice-conversation-mode.md`.

Q1: what the page does on /speak not 200 changes when S2b lands (stop with the error today, skip the
sentence after S2b). These tests take the reading that binds neither: they check the server's exact
answer, that nothing plays, that the turn ends listening or off (off: the error shown) and that the
answer stays on the page.
Q2: the stopped state is `off` in the artifact and `""` in the S2a contract: either is taken.
"""

from __future__ import annotations

from vcm_fakes import (
    LISTENING_OR_OFF,
    NO_VOICE,
    UKRAINIAN,
    FailingTts,
    deduped,
    of_kind,
    one_turn,
    page_prefix,
    run_page,
    serve,
)

# English for every language: the feature artifact, S1 -> S2a (owner, task 208, 2026-10-27).
NO_VOICE_FRAGMENT = '<p class="error">There is no voice for your language.</p>'
NO_VOICE_TEXT = "There is no voice for your language."


def test_s1_to_s2a_speak_409_fragment_for_a_language_without_voice_reaches_the_page_and_nothing_plays() -> (
    None
):
    with serve() as server:
        server.choose(UKRAINIAN)
        form = server.reply_form(server.new_topic())  # opened while the language had a voice
        server.choose(NO_VOICE)  # then changed elsewhere
        page = run_page(server, page_prefix(form), form["data-voice"], tap=True, turn=True)
    speak = of_kind(page, "speak")
    assert len(speak) >= 1, page["forwarded"]
    for f in speak:
        assert f["status"] == 409, f
        assert f["body"].strip() == NO_VOICE_FRAGMENT, f
    assert page["started"] == 0, "a sound played without audio from /speak"
    assert page["state_after_turn"] in LISTENING_OR_OFF, page["stateLog"]
    if page["state_after_turn"] in ("", "off"):
        assert page["error"] == NO_VOICE_TEXT, page["error"]
    assert any("model" in x["cls"] and x["text"] for x in page["live"]), page["live"]


def test_s1_to_s2a_speak_502_when_synthesis_fails_reaches_the_page_and_nothing_plays() -> None:
    failing = FailingTts()
    with serve(tts=failing) as server:
        server.choose(UKRAINIAN)
        form = server.reply_form(server.new_topic())
        page = run_page(server, page_prefix(form), form["data-voice"], tap=True, turn=True)
    speak = of_kind(page, "speak")
    assert len(speak) >= 1, page["forwarded"]
    assert [f["status"] for f in speak] == [502] * len(speak), speak
    assert failing.calls == [(f["sent"]["text"], UKRAINIAN) for f in speak]
    assert page["started"] == 0, "a sound played without audio from /speak"
    assert page["state_after_turn"] in LISTENING_OR_OFF, page["stateLog"]
    if page["state_after_turn"] in ("", "off"):
        assert page["error"], "the mode stopped with no error shown"
    assert any("model" in x["cls"] and x["text"] for x in page["live"]), page["live"]


def test_s2a_to_s2b_talk_data_state_goes_listening_hearing_thinking_speaking_listening_then_off() -> None:
    turn = one_turn()
    log = turn.page["stateLog"]
    assert deduped(log[:-1]) == ["listening", "hearing", "thinking", "speaking", "listening"], log
    assert turn.page["state_after_turn"] == "listening"
    assert log[-1] in ("", "off") and turn.page["state"] in ("", "off"), log
    assert turn.page["error"] == "", turn.page["error"]
