# 733 — Tests type-check red: 208 mypy errors in sealed tests

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: tests-mypy-red

## Що сталося
On 5249680 (before task 711) `uv run mypy src tests` prints «Found 208 errors in 33 files»; `uv run mypy src` is clean. Almost all: test doubles (FakeLlm and others) lack the Llm protocol member `search_text`; skel_learning tests import `analyze.Observation`. The Stop gate runs mypy on every changed file, so any slice that has to touch one of these sealed tests (e.g. continuous-analysis) is blocked by errors it did not make. Also: 25 contract tests fail on the same commit (skel_learning, skel_facilitation, voice_synthesis, voice_conversation_mode_block, walking_skeleton_block).

- Записано: 2026-10-28T11:41:04Z, агент
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Through objection packages to each owning slice's tester: give the test doubles `search_text`, fix the skel_learning imports, and carry the 25 red tests over to the current contracts; then `uv run mypy src tests` and the full `uv run pytest` are green.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника
