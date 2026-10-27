# Objection package — knowledge-versions contract tests, round 1

No behaviour is disputed: all 47 tests pass against the code. One hygiene finding of the gate: the bypass guard
refuses an added `# type: ignore`, and the builder may not edit a sealed file. Asked: correct the file so mypy is
clean with no ignore; behaviour and expected values unchanged.

1. `tests/contract/knowledge_versions/test_kv_disputed_q1_rollback_retries.py` lines 41 and 49:
   `store.rival = rival  # type: ignore[assignment]`. Without the ignore mypy says
   `Incompatible types in assignment (expression has type "object", variable has type
   "Callable[[RecordingStorage, str], None] | None")` — the helper `rival_taking` returns its rival as `object`.
   Annotate `rival_taking`'s return as `tuple[list[str], Callable[[RecordingStorage, str], None]]` (or the like)
   and drop both ignores. Contract line (unchanged meaning): «`create_if_absent` не вдався → перелічити знову і
   спробувати наступний номер, до 3 разів, далі `KnowledgeConflict`.»

Reproduce: copy the file without the two ignores and run `uv run mypy` on it (two `[assignment]` errors);
`grep -n 'type: ignore' tests/contract/knowledge_versions/*.py`.
