# 737 — Повний прогін тестів переписує step-results/smoke.txt на RESULT: FAIL, і жоден тест не падає

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: full-run-step-results-smoke-fail

## Що сталося
У задачі 721 повний uv run pytest (2 failed — обидва skel-facilitation, 1523 passed) переписав .engine/artifacts/step-results/smoke.txt (його пише scripts/smoke_test_learning_loop.py, STEPS_OUT): рядок «FAIL the card files are byte-for-byte the same» і «RESULT: FAIL». Окремий запуск uv run python scripts/smoke_test_learning_loop.py дає RESULT: PASS. Отже, якийсь тест запускає smoke в умовах, де картки змінюються між двома synthesize, і не перевіряє RESULT. Артефакт відновлено з git (як у задачі 308, commit b7c1d04).

- Записано: 2026-10-29T00:15:54Z, агент задачі 721
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Знайти тест, що під час повного прогону пише step-results/smoke.txt (кандидати: tests/contract/learning_loop_block/test_ll_block_acceptance.py, tests/contract/synthesizer/syn_catchup_smoke_run.py, tests/contract/notes_readers/nr_catchup_smoke_run.py); з'ясувати, чому картки змінюються; тест має писати в tmp, а не в .engine/artifacts/, і падати на RESULT: FAIL.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника
