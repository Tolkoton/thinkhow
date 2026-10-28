# Objection package — one line of the round-1 rewrite contradicts a later sealed contract (board task 720)

Filed under `synthesizer` for the same reason as round 1 (`.engine/testing/objections/skel-learning-720-owner-A.md`:
skel-learning and analysis-rules have no rounds left; the owner's answer A, task 720).

Disputed: `tests/contract/skel_learning/test_skell_schema.py::test_answer_schema_accepts_a_valid_answer_and_refuses_bad_ones`,
the last line `assert set(props["kind"]["enum"]) == {"progress", "stuck", "method_fit"}`.

Why the test is wrong, not the code: analysis-rules is S2 of feature learning-loop, and its Deferred line says
«схема моделі — без `step`, його додає S6». S6 is `.engine/slices/step-results.md` (line 3: «Feature:
`.engine/architecture/feature/learning-loop.md`, slice **S6**»), sealed and built after S2; its line 13: «Аналізатор
отримує результати кроків … і пише спостереження `kind: step`». Its sealed test
`tests/contract/step_results/test_stp_analyze.py:61` asserts `"step" in kinds_of(answer_schema([1, 2, 3]))`. The two
sealed tests cannot both pass; the later contract decides. The code (`src/thinkhow/learning/analyze.py:56`,
`KIND = Literal["progress", "stuck", "method_fit", "step"]`) follows S6.

Asked: the kind check reads the four kinds `{"progress", "stuck", "method_fit", "step"}` (the bad-kind case
`kind="other"` stays, its comment says «outside the four»). Nothing else in the file changes.

Failing now: `uv run pytest -q tests/contract/skel_learning/test_skell_schema.py::test_answer_schema_accepts_a_valid_answer_and_refuses_bad_ones`
