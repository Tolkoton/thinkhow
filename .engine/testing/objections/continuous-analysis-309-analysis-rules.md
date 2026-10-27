# Objection package — continuous-analysis, for task 309 (feature learning-loop, slice S2 analysis-rules)

These sealed tests pin the analyzer's old output: one observation per file and per call, the answer schema
`finding, worked, cause, anchor`, three causes, the local script's single answer. The sealed contract
`.engine/slices/analysis-rules.md` (S2 of feature learning-loop, task 309 — the owner asked for «кілька спостережень
на тему за ніч» and the cause «роутер») replaces exactly that:
- «**Схема відповіді** `answer_schema(turn_nos)` → `{observations: list[{kind: "progress"|"stuck"|"method_fit",
  finding: str ≥1, worked: bool, cause: "router"|"method"|"facilitation"|"circumstances", anchor: enum "t<n>" нових
  реплік}]}`, `min_length=1`»;
- «**Файл** `learning/observations/<uid>/<topic>/t<a>-t<b>.json` (ім'я, `_seen`, діапазон — як зараз) =
  `ObservationSet(uid, topic_id, first_turn, last_turn, analyzed_at, observations: list[Observation])`»;
- «`learning/local.py` — сценарна відповідь у новій схемі (одне спостереження `progress`, якір — перший з `enum`)»;
- the instruction `ANALYZER` now carries the rules of analysis and the state lines of the method (`[Метод: …]`).
S2's Q6: «Запечатані тести, що закріплюють старий вигляд … — objection-пакет `test_wrong` …; решта їхніх перевірок
(якір у межах нових реплік, `_seen`, контекст, лог невдачі, лише `system/learning/`) — не слабшає.»

Asked: carry each test over to the new shape — the answer `{"observations": [...]}` with `kind`, the file as a set
(`observations[k]` with `id`, `turn`, `link`, `card_id`, `analyzed_at`), four causes — keeping every other check
as strong as it is (cursor from the names, context, legacy `s<n>.json`, range, anchors in range, failure writes
nothing, the log line, write scope). Where a test pinned a sentence of the old instruction, pin what the contract
still says (new turns, the context line) rather than the old wording.

Failing now (`uv run pytest -q <test>`):
- `tests/contract/continuous_analysis/test_ca_analyze.py::test_seam1_the_cursor_comes_from_file_names_across_runs`
- `tests/contract/continuous_analysis/test_ca_analyze.py::test_seam1_turns_after_24h_of_silence_open_a_session_and_go_without_context`
- `tests/contract/continuous_analysis/test_ca_analyze.py::test_seam2_legacy_s_files_move_the_cursor_and_stay_untouched`
- `tests/contract/continuous_analysis/test_ca_analyze.py::test_seam3_a_failure_writes_nothing_and_the_turns_come_again`
- `tests/contract/continuous_analysis/test_ca_analyze.py::test_seam5_an_open_conversation_is_analyzed_at_once`
- `tests/contract/continuous_analysis/test_ca_analyze.py::test_one_generate_json_call_with_analyzer_one_user_turn_and_no_rev`
- `tests/contract/continuous_analysis/test_ca_analyze.py::test_new_turns_of_two_sessions_go_in_one_call_with_context_of_the_first_ones_session`
- `tests/contract/continuous_analysis/test_ca_analyze.py::test_an_unanswered_last_turn_of_the_person_is_analyzed_and_its_answer_goes_next_run`
- `tests/contract/continuous_analysis/test_ca_analyze.py::test_observation_file_has_the_range_the_anchor_and_link_and_no_session_fields`
- `tests/contract/continuous_analysis/test_ca_analyze.py::test_report_counts_written_skipped_failed_per_topic`
- `tests/contract/continuous_analysis/test_ca_analyze.py::test_analyze_failed_line_has_first_and_last_turn_and_no_session_no`
- `tests/contract/continuous_analysis/test_ca_analyze.py::test_any_other_file_name_does_not_move_the_cursor`
- `tests/contract/continuous_analysis/test_ca_analyze.py::test_analyzer_instructions_speak_of_new_turns_and_the_context`
- `tests/contract/continuous_analysis/test_ca_invariants.py::test_I1_every_turn_is_analyzed_exactly_once_across_runs_appends_and_failures`
- `tests/contract/continuous_analysis/test_ca_invariants.py::test_I2_a_run_with_nothing_new_calls_no_model_and_writes_nothing_in_system`
- `tests/contract/continuous_analysis/test_ca_invariants.py::test_I4_the_anchor_lies_in_its_range_and_the_link_opens_that_turn_on_the_page`
- `tests/contract/continuous_analysis/test_ca_invariants.py::test_I5_legacy_s_files_set_the_starting_cursor_and_new_ranges_cover_the_rest`
