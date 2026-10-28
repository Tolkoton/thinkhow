# Objection package — one-conversation, round 2 (task 711): the block test of `mypy src tests`

Disputed: `tests/contract/one_conversation_block/test_ocb_block.py::test_acceptance_4_ruff_mypy_and_lint_imports_are_green`.

The test asserts that `uv run mypy src tests` exits 0, from the Exit criterion line «Повний `uv run pytest -q`, `uv run ruff
check .`, `uv run mypy src tests`, `PYTHONPATH=src uv run lint-imports` — зелені.»

Evidence that this cannot be the slice's behaviour, only the state of other slices' sealed tests:
- On the commit before the slice (`5249680`, a clean `git worktree` of HEAD, no change of this slice in it) `uv run mypy
  src tests` prints `Found 208 errors in 33 files (checked 400 source files)`. On the current tree: `Found 208 errors in
  33 files (checked 404 source files)` — the same 208; the four new files of this slice add none.
- None of them is in `src` (`uv run mypy src` is clean) or in `tests/contract/one_conversation*` — your own hand-in says
  so: test doubles without the `Llm` member `search_text`, `skel_learning` importing `analyze.Observation`. They are
  sealed tests of other slices; the builder may not edit them, and the slice's Seam does not touch `Llm` or `Observation`.
- So the test is red on the base and on every possible implementation of this contract: it catches no wrong
  implementation of one-conversation («Broken by» of nothing in the contract), and it keeps every Stop gate of this
  slice red for a reason outside it.

The planner's reading of the line (the contract states the slice's goal in «Goal» item (4) as the same four commands):
the slice must not make any of the four worse and must leave its own files clean. Asked: rule `test_wrong` and narrow
the check to what this slice can make true — ruff and lint-imports as they are; mypy clean on `src`, on the slice's
own test folders and on `scripts/smoke_test_one_conversation.py`, and no mypy error in a file this slice changed
(`git diff --name-only 5249680` ∩ the mypy output) — or rule `contract_ambiguous` and the planner answers with this
reading. The 208 pre-existing errors go to the owner as a proposal (`tasks/proposed/`), not into this slice.
