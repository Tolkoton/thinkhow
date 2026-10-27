# Objection package — skel-guards-deploy, for task 309 (feature learning-loop, slice S2 analysis-rules)

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
- `tests/contract/walking_skeleton_block/test_wsblock_connections.py::test_s4_learning_reads_every_topic_and_topic_sessions_numbered_across_the_topic`
- `tests/contract/walking_skeleton_block/test_wsblock_connections.py::test_s6_observation_link_of_a_persons_topic_opens_the_turn_for_the_owner`
