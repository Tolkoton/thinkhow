# Supersession package — spoken-replies' retry test under step-results' `recognize` (board task 733)

Old test: `tests/contract/spoken_replies/test_sr_workspace.py::test_retry_passes_spoken_into_the_context`
(line 36: `kw = {} if flag is None else {"spoken": flag}` then `retry(store, fac, ALICE, ref, T0, **kw)`).

The line of the new contract that changes it: `.engine/slices/step-results.md:55–56` — «`recognize(step, question,
text) -> StepOutcome | None` (ін'єкція в `workspace.reply` і `workspace.retry`, той самий keyword
`recognize: Recognize | None = None`…)». spoken-replies sealed `retry(storage, facilitate, user, ref, now,
spoken=False)` (`.engine/slices/spoken-replies.md:69`); step-results added a further keyword `recognize` of a callable
type. Since then `**kw` of type `dict[str, bool]` can, for mypy, land in `recognize`, and `uv run mypy src tests` prints:

    tests/contract/spoken_replies/test_sr_workspace.py:36: error: Argument 6 to "retry" has incompatible type "**dict[str, bool]"; expected "Callable[[str, str, str], StepOutcome | None] | None"  [arg-type]

spoken-replies' Exit criterion (`.engine/slices/spoken-replies.md:136–137`) asks for `uv run mypy` clean, and the
Stop gate runs mypy on every changed test file. spoken-replies has no objection rounds left (2 of 2).

Asked: the same three cases (spoken=True, spoken=False, no keyword at all) and the same assertions, written so the
call type-checks with `recognize` present — e.g. the no-keyword case as a plain `retry(store, fac, ALICE, ref, T0)`
and the other two as `retry(..., spoken=flag)`. Nothing else in the file changes.

Check after: `uv run mypy src tests 2>&1 | grep test_sr_workspace` prints nothing;
`uv run pytest -q tests/contract/spoken_replies` stays green.
