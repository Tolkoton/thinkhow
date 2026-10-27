# Objection package — spoken-replies sealed block test vs. the interface language rule (task 208)

Why: the owner's decision in task 208 (`tasks/doing/208-interface-language.md`, «Рішення власника», 2026-10-27:
«Інтерфейс мовою людини точно так.» — to the proposal «усі написи, підказки, повідомлення про помилки … мовою, яку обрала
людина») changes one behaviour a sealed test was written against: an error fragment is now in the language the person
chose, not always in Ukrainian. The voice-synthesis contract (`.engine/slices/voice-synthesis.md`, line 85: «`NoVoice` →
409 фрагмент «Для вашої мови немає голосу.»») stays true for a Ukrainian-speaking person; for any other person the same
message comes from that language's catalog (`src/thinkhow/web/locales/<name>.json`, key `err_no_voice`; `uk.json` holds
exactly «Для вашої мови немає голосу.»). The page shows the fragment's text as before (`conversation.js` is unchanged there).

Everything else the test checks — 409, nothing plays, the state after the turn, the answer stays on the page — is unchanged.
Checked: `uv run pytest tests/contract/voice_conversation_mode_block -q` → the one test below fails, the rest pass.

Items (test — contract line — why it fails now):
1. tests/contract/voice_conversation_mode_block/test_vcm_block_disputed_q1_q2.py::test_s1_to_s2a_speak_409_fragment_for_a_language_without_voice_reaches_the_page_and_nothing_plays
   — the S1 → S2a connection (409 fragment of /speak reaches the page). The person's language at /speak is mt-MT
   (`vcm_fakes.NO_VOICE`), so the fragment is now Maltese: `<p class="error">M'hemmx vuċi għall-lingwa tiegħek.</p>`; the test expects the Ukrainian
   `NO_VOICE_FRAGMENT` / `NO_VOICE_TEXT`.

Asked: keep every check and take the expected message in the language chosen at /speak: e.g. `err_no_voice` read from
`src/thinkhow/web/locales/mt.json` (or `thinkhow.web.ui_text.texts("mt")`), for both the fragment and the page's error.
