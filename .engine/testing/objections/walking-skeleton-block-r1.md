# Objection package — walking-skeleton block tests (skel-guards-deploy), round 1

No behaviour is disputed: all 12 block tests pass. Hygiene findings of the gate: mypy strict runs on test files, and the bypass guard refuses an added `# type: ignore`. The builder may not edit sealed files. Asked: correct the files so mypy is clean and no ignore remains; behaviour and expected values unchanged.

1. `# type: ignore[no-untyped-def]` at tests/contract/walking_skeleton_block/test_wsblock_connections.py lines 56, 60, 64, 141 — annotate the helpers instead.
2. mypy output now:
```
tests/contract/walking_skeleton_block/wsblock_fakes.py:72: error: Function "wsblock_fakes.RecordingStorage.list" is not valid as a type  [valid-type]
tests/contract/walking_skeleton_block/wsblock_fakes.py:72: note: Perhaps you need "Callable[...]" or a callback protocol?
tests/contract/walking_skeleton_block/test_wsblock_connections.py:78: error: "list?[tuple[str, str, str]]" has no attribute "__iter__" (not iterable)  [attr-defined]
tests/contract/walking_skeleton_block/test_wsblock_connections.py:85: error: Call to untyped function "drain" in typed context  [no-untyped-call]
tests/contract/walking_skeleton_block/test_wsblock_connections.py:111: error: Call to untyped function "drain" in typed context  [no-untyped-call]
tests/contract/walking_skeleton_block/test_wsblock_connections.py:115: error: Call to untyped function "drain" in typed context  [no-untyped-call]
tests/contract/walking_skeleton_block/test_wsblock_connections.py:209: error: Call to untyped function "drain" in typed context  [no-untyped-call]
tests/contract/walking_skeleton_block/test_wsblock_connections.py:216: error: Call to untyped function "drain" in typed context  [no-untyped-call]
tests/contract/walking_skeleton_block/test_wsblock_connections.py:285: error: Call to untyped function "drain" in typed context  [no-untyped-call]
tests/contract/walking_skeleton_block/test_wsblock_connections.py:287: error: Call to untyped function "drain" in typed context  [no-untyped-call]
tests/contract/walking_skeleton_block/test_wsblock_connections.py:289: error: Call to untyped function "drain" in typed context  [no-untyped-call]
tests/contract/walking_skeleton_block/test_wsblock_connections.py:304: error: Value of type "list?[tuple[str, str, str]]" is not indexable  [index]
tests/contract/walking_skeleton_block/test_wsblock_connections.py:397: error: "list?[tuple[str, str, str]]" has no attribute "__iter__" (not iterable)  [attr-defined]
tests/contract/walking_skeleton_block/test_wsblock_connections.py:400: error: "list?[tuple[str, str, str]]" has no attribute "__iter__" (not iterable)  [attr-defined]
```

Reproduce: `.venv/bin/mypy tests/contract/walking_skeleton_block/*.py`; `grep -n 'type: ignore' tests/contract/walking_skeleton_block/*.py`.
