# Objection package — skel-learning, for task 309 (feature learning-loop, slice S2 analysis-rules)

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
- `tests/contract/skel_learning/test_skell_analyze.py::test_seam1_one_call_per_topic_with_new_turns_none_for_the_rest`
- `tests/contract/skel_learning/test_skell_analyze.py::test_observation_carries_the_range_the_answer_and_now`
- `tests/contract/skel_learning/test_skell_analyze.py::test_one_generate_json_call_with_analyzer_one_user_turn_of_numbered_lines_without_headers`
- `tests/contract/skel_learning/test_skell_analyze.py::test_new_turns_in_the_same_session_come_after_the_context_of_the_analyzed_ones`
- `tests/contract/skel_learning/test_skell_analyze.py::test_now_without_time_zone_is_value_error_at_once`
- `tests/contract/skel_learning/test_skell_analyze.py::test_analyze_done_line_at_the_end_carries_the_report`
- `tests/contract/skel_learning/test_skell_analyze.py::test_seam2_validation_error_and_llm_unavailable_are_logged_and_the_rest_is_written`
- `tests/contract/skel_learning/test_skell_analyze.py::test_a_failed_topic_is_tried_again_on_the_next_run`
- `tests/contract/skel_learning/test_skell_catchup_smoke.py::test_smoke_succeeds_and_prints_the_observation_file_with_a_link_to_a_turn_of_the_two_turn_topic`
- `tests/contract/skel_learning/test_skell_catchup_smoke.py::test_smoke_observation_is_the_local_scripted_answer`
- `tests/contract/skel_learning/test_skell_catchup_smoke.py::test_smoke_runs_in_a_temporary_folder_and_leaves_nothing_in_the_repository`
- `tests/contract/skel_learning/test_skell_chain.py::test_seam4_local_chain_ends_in_an_observation_whose_link_opens_an_existing_turn`
- `tests/contract/skel_learning/test_skell_invariants.py::test_I1_anchor_is_a_turn_of_its_new_range_and_link_leads_to_it`
- `tests/contract/skel_learning/test_skell_invariants.py::test_I2_analyze_writes_nothing_outside_system_learning_observations`
- `tests/contract/skel_learning/test_skell_invariants.py::test_I3_turns_with_an_observation_are_never_sent_to_the_model_as_new_again`
- `tests/contract/skel_learning/test_skell_job.py::test_run_analyze_in_local_mode_writes_the_scripted_observation_and_returns_0`
- `tests/contract/skel_learning/test_skell_schema.py::test_answer_schema_fields_in_order_and_anchor_is_a_string_enum_of_the_turns`
- `tests/contract/skel_learning/test_skell_schema.py::test_answer_schema_of_one_turn_is_still_an_enum_not_const`
- `tests/contract/skel_learning/test_skell_schema.py::test_answer_schema_accepts_a_valid_answer_and_refuses_bad_ones`
- `tests/contract/skel_learning/test_skell_schema.py::test_local_script_answers_the_fixed_observation_anchored_to_the_first_enum_value`
