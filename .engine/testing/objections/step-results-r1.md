# Objection package — step-results contract tests, round 1

No behaviour is disputed: all 32 tests pass against the code. A hygiene finding of the gate: the bypass guard
refuses an added `# type: ignore`, and the builder may not edit a sealed file. Asked: annotate the helpers so mypy is
clean with no ignore; behaviour and expected values unchanged.

1. `tests/contract/step_results/test_stp_invariants.py:39` `_records(storage, ref, now, step_id)` and `:43`
   `_question_turns(storage, ref, now, question)` — `now` has no annotation (`# type: ignore[no-untyped-def]`).
2. `tests/contract/step_results/test_stp_web.py:34` `_page(tmp_path, storage, now, ref, headers)` — `now`, `ref`,
   `headers` have no annotation (`# type: ignore[no-untyped-def]`).

Reproduce: copy the two files without the ignores and run `uv run mypy` on them — three `[no-untyped-def]` errors.
