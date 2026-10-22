# Objection package — skel-facilitation, round 1

No behaviour is disputed: all 21 tests pass against the code. These are hygiene findings of the project's
gate (`.claude/hooks/verify-on-stop.sh`): mypy strict runs on test files, and a bypass guard refuses an
added `# noqa`, `# ruff: noqa` or `# type: ignore` without a `gate-allow` reason. The builder may not edit
sealed files. Asked: correct the tests so the gate passes, behaviour and expected values unchanged.

1. `tests/contract/skel_facilitation/test_skelf_disputed_q2_itemtype_export.py:13` —
   `# type: ignore[attr-defined]` is now unused (`ItemType` is exported), and mypy reports
   `Unused "type: ignore" comment [unused-ignore]`. Drop it.
2. `tests/contract/skel_facilitation/test_skelf_respond.py:1` — `# ruff: noqa: E501`. The guard refuses it.
   Keep `RULES` verbatim but write its long lines without exceeding 110 characters, e.g. adjacent string
   literals in parentheses (`("…першу частину " "…другу\n")`), so the joined value is byte-identical.
3. `tests/contract/skel_facilitation/skelf_fakes.py:194` — `# noqa: BLE001`. The project's ruff does not
   select `BLE` (`[tool.ruff.lint] select = E,F,W,I,B,UP`), so it silences nothing; drop it.

Reproduce: `uv run mypy tests/contract/skel_facilitation/*.py`, `uv run ruff check tests`,
`grep -n "noqa\|type: ignore" tests/contract/skel_facilitation/*.py`.
