# NNN — An objection round that renames a sealed test file leaves the seal stale and blocks the audit forever

Клас: дефект
Залежить від: —
Потрібна присутність власника: ні
Режим: соло
Аудит потрібен: ні
Додаткові сесії: ні

## Що сталося
ThinkHow, task 712, slice `finish-answer` (2026-10-28). The slice-tester named its files `test_fa_*.py` and `fa_fakes.py`. Those
basenames already belong to the sealed `tests/contract/fact_answer/` (contract directories have no `__init__.py`), so the full
`pytest` run stopped at collection («import file mismatch»). The builder sent an objection package (round 1). The tester
answered `test_wrong` and renamed the four files to `fin_*`.

`testing.py record_objection` reseals only `changed` files that still exist
(`seal_files(root, slug, [rel for rel in changed if (root / rel).is_file()], {})`). So:
- the three old paths stay in `.claude/state/testing/seals/finish-answer.json`, missing, and `check_seal` reports
  `CHANGED` for good;
- the new `fin_*` files are never sealed, so nothing guards them from the builder;
- `audit_block` returns the `CHANGED` note, so `overseer_stop.py` never makes an audit request for the slice.

The only way out is to write `.claude/state/` by hand. An agent may not do that, so the task parks for the owner.

## Що зробити
- Let an objection answer carry renames, for example an item field `renamed: {old: new}`, or a top-level `renamed` map.
  `record_objection` then drops the old paths from the seal and seals the new ones, only on a `test_wrong` verdict.
- Alternatively, or as well: `slice-tester` (contract mode) and `handin_errors` refuse a hand-in whose test or helper
  basename already exists in another directory under `tests/`. The clash is then caught before the seal.
  `dispute-rounds-are-scarce` in the ThinkHow memory shows this has happened before (task 308, `cl_fakes.py`).

## Готово, коли
- A rename by a `test_wrong` objection leaves `check_seal` at `match` with the new paths, and the audit is no longer blocked.
- A contract hand-in with a basename clash is refused with the clashing paths named.
