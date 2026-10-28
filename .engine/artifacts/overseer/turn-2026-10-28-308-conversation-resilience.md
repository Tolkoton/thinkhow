Task 308-voice-conversation-mode, slice conversation-resilience (S2b of feature voice-conversation-mode) —
claim of the unit. Contract: `.engine/slices/conversation-resilience.md` (sealed, `contract_fingerprint.py check` →
match 8674cb031db6…).

The code is commit f2a9e46 (`src/thinkhow/web/static/conversation.js`, `templates/icons.html`, `templates/topic.html`,
`scripts/smoke_test_conversation_resilience.py`). It was not claimed then: three sealed conversation-loop (S2a) tests
encoded the S2a rule «any error stops the mode», which this contract replaces (I3 «Broken by: S2a-поведінка «будь-яка
помилка вимикає режим»…»), and conversation-loop's two dispute rounds were spent, so it was parked (board 718).

The owner answered «А» (task 308 question 1, 2026-10-27: «Режим розмови. Так, я згоден, що А хай буде.»): a fresh
tester rewrites those three tests to the new rule and keeps their other checks. Done now: objection package
`.engine/testing/objections/conversation-loop-308-conversation-resilience.md`, filed under conversation-resilience
(conversation-loop answers «parked already»); the fresh slice-tester ruled test_wrong ×3 and rewrote them
(`.engine/testing/ledger.md`, «conversation-resilience — dispute, round 1 of 2», 2026-10-28T02:21:59Z); commit f8e999f.
No code changed in this session; only test files of tests/contract/conversation_loop/.

Earlier evidence of the slice (commit f2a9e46, `.engine/PROGRESS.md` «Slice conversation-resilience»): 48 sealed tester
tests; point (b): catch-up tests of the smoke and invariants (sealed), block tests S2a→S2b (6, sealed); smoke
`.engine/artifacts/conversation-resilience/smoke.txt` — states cycle 3 times, `/speak statuses: [200, 502, 200, 200,
200, 200]`, `wake lock requests: ['screen']`, tones 880 Hz ×4, «OK: one /speak failed and was skipped; 3 cycles without
a touch». Live acceptance of the whole mode: `.engine/artifacts/conversation-mode/live-2026-10-27.md`.

Verification run now on HEAD f8e999f:
- `uv run pytest -q tests/contract/conversation_loop tests/contract/conversation_resilience
  tests/contract/voice_conversation_mode_block` → 1 failed, 135 passed in 722.13s. The one failure is
  `tests/contract/voice_conversation_mode_block/test_vcm_block_disputed_q1_q2.py::test_s1_to_s2a_speak_409_fragment_for_a_language_without_voice_reaches_the_page_and_nothing_plays`
  — it expects the Ukrainian no-voice text; task 208 (commit 9a76780, the owner's answer) made that text English and
  changed voice-synthesis contract line 85; the test waits for the owner's reseal of that contract (tasks/blocked/208,
  question 2). Not code of this slice.
- `uv run ruff check scripts tests src` → All checks passed!
- `uv run ruff format --check tests/contract/conversation_loop` → 12 files already formatted
- `uv run mypy` → Success: no issues found in 57 source files
- `PYTHONPATH=src uv run lint-imports` → Contracts: 7 kept, 0 broken.

=== UNIT 1 COMPLETE ===
