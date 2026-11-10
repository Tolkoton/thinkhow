# Objection package — research-display, one typing defect in a sealed test (board task 733)

Disputed: `tests/contract/research_display/test_rd_llm.py`, the helper `only_done` (line 62–65), used by
`test_seam*` tests of this file at lines 79 and 98 (and any other caller of `only_done`).

Why the test is wrong, not the code: the contract's «Exit criterion» (`.engine/slices/research-display.md:167–168`)
reads «`uv run pytest -q` зелений … `ruff check`, `mypy` чисті». The project runs mypy strict on `src tests`
(`pyproject.toml` `[tool.mypy] strict = true`). On this file `uv run mypy src tests` prints:

    tests/contract/research_display/test_rd_llm.py:65: error: Returning Any from function declared to return "Done"  [no-any-return]

`items: list[Any]`, so `done = [i for i in items if isinstance(i, pl.Done)]` is `list[Any]` and `return done[0]` is
`Any`. The Stop gate runs mypy on every changed test file, so this file blocks any later slice that touches it.

Asked: make `only_done` type-check without changing what it asserts — e.g. `done: list[pl.Done] = [...]`. No test's
assertion changes. Verdict expected: `test_wrong` for `tests/contract/research_display/test_rd_llm.py`.

Check after: `uv run mypy src tests 2>&1 | grep test_rd_llm` prints nothing;
`uv run pytest -q tests/contract/research_display` stays green.
