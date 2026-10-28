# Objection package — spoken-replies, round 2 (task 208): the no-voice message reaching the page is English now

Disputed: `tests/contract/voice_conversation_mode_block/test_vcm_block_disputed_q1_q2.py::test_s1_to_s2a_speak_409_fragment_for_a_language_without_voice_reaches_the_page_and_nothing_plays`.

The test asserts the Ukrainian fragment `<p class="error">Для вашої мови немає голосу.</p>` (lines 27–28, 43, 47). The
owner decided the no-voice message is English for every language (`tasks/doing/208-interface-language.md`, question 1,
2026-10-27: «…краще хай це буде англійською.»). The connection this block test checks is written in the feature artifact
`.engine/architecture/feature/voice-conversation-mode.md` line 145: «`<p class="error">There is no voice for your
language.</p>` (англійською для будь-якої мови — власник, задача 208, 2026-10-27)», and the S1 contract it rests on,
`.engine/slices/voice-synthesis.md` line 85, says the same and is resealed by the owner (`contract_fingerprint.py check` →
`Match`).

So the test contradicts both documents as they are now. For mt-MT (`vcm_fakes.NO_VOICE`) the server answers 409
`<p class="error">There is no voice for your language.</p>` (`src/thinkhow/web/server.py`, `NO_VOICE_MESSAGE`). Checked:
`uv run pytest tests/contract/voice_conversation_mode_block -q` → this one test fails, the rest pass.

Asked: rule `test_wrong` and change only the expected text to «There is no voice for your language.» (fragment and the
page's error); keep every other check — 409, nothing plays, the state after the turn, the answer stays on the page.
