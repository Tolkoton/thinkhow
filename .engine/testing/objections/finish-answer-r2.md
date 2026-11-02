# Objection package — finish-answer contract tests, round 2

No behaviour is disputed and nothing in the tests is asked to change. Round 1 (2026-10-28T12:14:40Z, ledger) was the
tester's own mechanical rename — `test_fa_*` / `fa_fakes.py` collided by basename with `tests/contract/fact_answer/`,
so the full `uv run pytest` failed at collection — to `test_fin_*` / `fin_fakes.py`, bodies and test names unchanged.
The engine of that day had no way to carry a seal to a new path: the seal still names the three old paths, which are
gone, so `testing.py check finish-answer` says `CHANGED` and the audit cannot start. The engine now installed (v0.14.3)
has `renamed` in an objection answer.

Asked: confirm the rename and answer with `renamed`, nothing else:

- `tests/contract/finish_answer/test_fa_behaviour.py` → `tests/contract/finish_answer/test_fin_behaviour.py`
- `tests/contract/finish_answer/test_fa_invariants.py` → `tests/contract/finish_answer/test_fin_invariants.py`
- `tests/contract/finish_answer/test_fa_disputed_q1_superseded_turn.py` →
  `tests/contract/finish_answer/test_fin_disputed_q1_superseded_turn.py`

Check it yourself: the old paths are absent from the tree and from git (never committed); the new files are in commit
`9ba9ac4`, untouched since (`git log -- tests/contract/finish_answer/`); `uv run pytest tests/contract/finish_answer -q`
— 10 passed. No later sealed contract touches these files.
