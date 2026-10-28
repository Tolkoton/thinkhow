# Objection package — one-conversation, task 711 (sealed tests of skel-workspace, continuous-analysis, analysis-rules)

These sealed tests pin the session boundary in the facilitator's history or in the analyzer's context. The sealed
contract `.engine/slices/one-conversation.md` removes exactly that boundary:
- «`workspace.topics._answer(...)` — `history = [FacilitationTurn(t.role, t.text) for s in conv.sessions for t in
  s.turns if t.no < turn_no]` (було: лише `conv.sessions[-1]`)» and **I1**: «Історія, яку фасилітатор отримує на
  відповідь репліці `n`, — це рівно всі репліки теми з номерами менше `n`, у порядку номерів, незалежно від сесій»;
- «`learning.analyze._topic(...)` — `context = [t for s in sessions for t in s.turns if t.no < new[0].no]` (було: лише
  сесія, де стоїть `new[0]`)» and **I2**: «Контекст аналізатора — рівно всі репліки теми з номерами менше першої
  нової, у порядку номерів; висновок і якір — лише серед нових»;
- Q5: «Запечатані тести інших slice-ів, що закріплюють межу сесії в історії чи контексті … — objection-пакет
  `test_wrong` їхнім tester-ам з рядками цього контракту; решта їхніх перевірок не слабшає.»

Asked: in each test below, carry over only the expectation about the history / the context to the whole topic (all
earlier turns, in number order, with the method's state lines that the analyzer already prints for context turns);
keep every other check as strong as it is — session numbers and `closed_at` on display, the cursor from file names,
legacy `s<n>.json` untouched and moving the cursor, anchors and observation ranges only among the new turns, the
state line that acts from a turn not yet shown stays unwritten. Where a test's name says «without context» or
«context of the first one's session», the name changes with the expectation.

Failing now (`uv run pytest -q <test>`), each on the context/history line only:
- `tests/contract/skel_workspace/test_skelw_sessions.py::test_reply_at_silence_opens_session_2_and_closes_session_1`
  — `fac.calls[1].context.history == []` and `fac.calls[2].context.history == [Turn("user", "повернувся"), …]`
  (session 1 is now in both).
- `tests/contract/continuous_analysis/test_ca_analyze.py::test_seam1_turns_after_24h_of_silence_open_a_session_and_go_without_context`
  — expects the call of `#5–#6` without `#1–#4` as context.
- `tests/contract/continuous_analysis/test_ca_analyze.py::test_seam2_legacy_s_files_move_the_cursor_and_stay_untouched`
  — expects the call after the legacy cursor without the earlier sessions as context.
- `tests/contract/continuous_analysis/test_ca_invariants.py::test_I5_legacy_s_files_set_the_starting_cursor_and_new_ranges_cover_the_rest`
  — asserts `'B-2' not in` the call text (session 2 is now context before the new `B-3` turns; it is still not new).
- `tests/contract/analysis_rules/test_ar_analyze.py::test_a_status_line_that_falls_outside_the_shown_turns_is_not_written`
  — expects the new session's call with no context; now `#1–#2` are context, and with them the offer's line before
  `#2`; the end on 3 that acts from `#5` (not yet existing) must still not be written.

Not in this package: 25 other contract tests (skel_learning, skel_facilitation, voice_synthesis,
voice_conversation_mode_block, walking_skeleton_block) fail identically on the code before this slice (`git stash`
of `src/`, same run) — not caused by one-conversation.
