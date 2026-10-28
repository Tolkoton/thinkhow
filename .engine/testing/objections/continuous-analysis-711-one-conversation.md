# Objection package — continuous-analysis, for task 711 (slice one-conversation)

The sealed contract `.engine/slices/one-conversation.md` (task 711) removes the session boundary from the
facilitator's history and the analyzer's context:
- **I1**: «Історія, яку фасилітатор отримує на відповідь репліці `n`, — це рівно всі репліки теми з номерами менше
  `n`, у порядку номерів, незалежно від сесій»;
- **I2**: «Контекст аналізатора — рівно всі репліки теми з номерами менше першої нової, у порядку номерів; висновок і
  якір — лише серед нових»;
- Q5: «Запечатані тести інших slice-ів, що закріплюють межу сесії в історії чи контексті … — objection-пакет
  `test_wrong` їхнім tester-ам з рядками цього контракту; решта їхніх перевірок не слабшає.»

The test(s) below pinned the session boundary (I2). A tester of one-conversation already ruled them `test_wrong`
and corrected them in the working tree (`.engine/testing/ledger.md`, «one-conversation — dispute, round 1 of 2»,
2026-10-28T11:29:29Z), but a ruling under another slice does not reseal this slice's files: `testing.py check continuous-analysis`
says CHANGED. Asked: read the corrected test(s) against this slice's own contract and the one-conversation contract;
if only the history/context expectation changed and every other check is as strong as before, rule `test_wrong`
(the correction stands, the file is sealed anew); otherwise correct it so.

Tests (`uv run pytest -q <test>`; they pass on the current tree):
- `tests/contract/continuous_analysis/test_ca_analyze.py::test_seam1_turns_after_24h_of_silence_open_a_session_and_go_with_the_whole_topic_as_context (was …_go_without_context)`
- `tests/contract/continuous_analysis/test_ca_analyze.py::test_seam2_legacy_s_files_move_the_cursor_and_stay_untouched`
- `tests/contract/continuous_analysis/test_ca_invariants.py::test_I5_legacy_s_files_set_the_starting_cursor_and_new_ranges_cover_the_rest`
