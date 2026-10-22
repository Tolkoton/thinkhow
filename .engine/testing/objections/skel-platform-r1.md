# Objection package — skel-platform, round 1

None of these disputes a behaviour: every test is right about the code's behaviour and passes. They are
hygiene findings of the project's gate (`.claude/hooks/verify-on-stop.sh`), which runs `mypy` (strict, as
`pyproject.toml` `[tool.mypy]` sets it) on every changed test file, and a bypass guard that refuses an
added `# noqa` or `# type: ignore` without a `gate-allow` reason. The builder may not edit sealed files.
Asked: correct the tests so that the gate passes, behaviour unchanged.

1. `tests/contract/skel_platform/test_skelp_llm.py:78` — `except Exception as exc:  # noqa: BLE001`.
   The project's ruff does not select `BLE` (`[tool.ruff.lint] select = E,F,W,I,B,UP`), so the noqa
   silences nothing; the guard refuses it. Drop the comment.
2. `tests/contract/skel_platform/test_skelp_log.py:15` — `fn()  # type: ignore[operator]`. Give `fn`
   a callable type instead (e.g. `Callable[[], None]`), so no ignore is needed.
3. mypy errors on the sealed files (contract line: `pyproject.toml` `[tool.mypy]` strict; the gate runs it
   on tests too):
   - `skelp_fakes.py:135` `Call to untyped function "PreconditionFailed"`, `:141`, `:154` the same for
     `NotFound` (google.api_core exceptions are untyped constructors) — e.g. build them through a typed
     helper, or `cast`.
   - `skelp_fakes.py:211` `Returning Any from function declared to return "str"` — e.g. `str(...)`.
   - `test_skelp_storage.py:19` `Argument 2 to "GcsStorage" has incompatible type "dict[str, str]";
     expected "Mapping[Literal['users', 'system'], str]"` — annotate the dict `dict[Bucket, str]`.
   - `test_skelp_llm.py:97`, `:152`, `:175` `Cannot infer type of lambda` — a named function or an
     annotated variable.

Reproduce: `uv run mypy tests/contract/skel_platform/*.py` and `uv run ruff check tests`.
