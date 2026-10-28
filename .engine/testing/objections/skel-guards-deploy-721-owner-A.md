# Objection package — skel-guards-deploy (walking-skeleton-block), carried out for the owner's answer A (board task 721)

**Why this package is filed under `notes-readers`.** skel-guards-deploy is parked after its two rounds, and
analysis-rules — the sealed contract that changes these tests — and synthesizer (used by task 720 for the same change in
skel-learning) have used their two rounds too: a request under any of them parks or refuses (`.claude/hooks/testing.py`,
`request_tester`, the `objection` branch). The owner answered the parked question (task 721,
`tasks/doing/721-open-item-testing-parked-skel-guards-deploy.md`): «Відповідь: А» — «тести застаріли: свіжий tester
переносить два тести на набір (посилання кожного спостереження відкриває репліку для власника), решту перевірок лишає».
notes-readers is S4 of the same feature (learning-loop, `.engine/architecture/feature/learning-loop.md`) and has both
rounds free. The contract lines that decide are those of `.engine/slices/analysis-rules.md`, quoted below; the file to
change is `tests/contract/walking_skeleton_block/test_wsblock_connections.py` (only the two tests named below). The
Exit criterion of analysis-rules names this package: «objection-пакет до запечатаних тестів skel-learning,
continuous-analysis, walking-skeleton-block розглянуто тестувальником (`test_wrong` → змінено)». Same precedent:
tasks 718 and 720.

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

For these two tests concretely: the file `t<a>-t<b>.json` keeps `uid`, `topic_id`, `first_turn`, `last_turn` at the
top level; `turn` and `link` are per observation (`observations[k]`), and `link` is
«"/topics/<uid>/<topic_id>#t<turn>"» (analysis-rules, Seam «Файл»; I1 «для кожного спостереження файлу
`first_turn ≤ turn ≤ last_turn` і `link` закінчується `#t<turn>`»). Keep every other check as it is (topics for
learning, session numbering across the topic, the written paths, the range, `written`/`failed`, the owner's page opens
with the anchor) and apply the per-turn checks to each observation of the set, with at least one observation in it. These two tests
need not check `kind`; if one does, the enum is four kinds — step-results (S6) lines 74–75 add `"step"` (task 720, round 2).

Failing now (`uv run pytest -q <test>`, both `KeyError: 'turn'`):
- `tests/contract/walking_skeleton_block/test_wsblock_connections.py::test_s4_learning_reads_every_topic_and_topic_sessions_numbered_across_the_topic`
- `tests/contract/walking_skeleton_block/test_wsblock_connections.py::test_s6_observation_link_of_a_persons_topic_opens_the_turn_for_the_owner`
