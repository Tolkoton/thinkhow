# Objection package — skel-web, round 1

No behaviour is disputed: all 50 tests pass. Hygiene findings of the project's gate: its bypass guard refuses an
added `# type: ignore` without a `gate-allow` reason, and the builder may not edit sealed files. Asked: correct the
tests so the gate passes, behaviour and expected values unchanged.

1. `tests/contract/skel_web/skelweb_fakes.py:170` — `exchanges: list[tuple[str, str]] = (),  # type: ignore[assignment]`.
   Use a tuple type (`Sequence[tuple[str, str]] = ()`) or `None` with a default inside, so no ignore is needed.
2. `tests/contract/skel_web/test_skelweb_routes.py:34` — `def url(ref, tail: str = "") -> str:  # type: ignore[no-untyped-def]`.
   Annotate `ref: TopicRef`.

Reproduce: `grep -n "type: ignore" tests/contract/skel_web/*.py`; `uv run mypy tests/contract/skel_web/*.py`.
