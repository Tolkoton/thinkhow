# Objection package — voice-synthesis, round 2 (task 208): the no-voice message is English now

Disputed: `tests/contract/voice_synthesis/test_vs_web.py::test_seam5_language_without_voice_is_409_fragment`.

Round 1 (2026-10-27T13:57:28Z) ruled `contract_ambiguous`: the contract's line 85 fixed the Ukrainian text, while the
interface rule of task 208 put error messages in the person's language. The owner answered that question
(`tasks/doing/208-interface-language.md`, question 1, 2026-10-27: «Так, ну інтерфейс для вашої мови нема голосу, краще хай
це буде англійською.»), and the contract was changed and resealed by the owner:
- `.engine/slices/voice-synthesis.md` line 85 now reads: «`NoVoice` → 409 фрагмент «There is no voice for your language.»
  англійською для будь-якої мови (окремий обробник, не `MESSAGES`; власник, задача 208, 2026-10-27)».
- `python3 .claude/hooks/contract_fingerprint.py check .engine/slices/voice-synthesis.md` → `Match` (exit 0).

The test still asserts the old Ukrainian words (`vs_fakes.NO_VOICE_TEXT = "Для вашої мови немає голосу."`, line 54), so it
contradicts the sealed contract as it is now. The server answers `<p class="error">There is no voice for your language.</p>`
with 409 for kk-KZ (`src/thinkhow/web/server.py`, `NO_VOICE_MESSAGE`). Checked: `uv run pytest tests/contract/voice_synthesis -q`
→ this one test fails, every other passes.

Asked: rule `test_wrong` and rewrite the expected text to the contract's line 85 — «There is no voice for your language.»
for a language without a voice (keep kk-KZ, the 409 status, the fragment and «no synthesis call»). Optionally the test may
also check a second language without a voice gets the same English text, since the line says «для будь-якої мови».
