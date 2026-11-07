# 737 — Повний прогін тестів переписує step-results/smoke.txt на RESULT: FAIL, і жоден тест не падає

Залежить від: —
Потрібна присутність власника: ні
Режим: соло
Аудит потрібен: так
Додаткові сесії: ні
Відкритий пункт: full-run-step-results-smoke-fail

## Рішення власника
Слова власника (2026-11-06, сесія Thinkhow; записано Claude зі слів власника) — на питання Claude «Ставити в роботу
пункти 1–4 (тести автоматичного розгортання, хибне «FAIL» після повного прогону, спрощення `_answer`, перевірка
застарілих залежностей)?»: «Бери все». Пункт 1 — пропозиції 738–741, пункт 2 — пропозиція 737.

## Що сталося
У задачі 721 повний uv run pytest (2 failed — обидва skel-facilitation, 1523 passed) переписав .engine/artifacts/step-results/smoke.txt (його пише scripts/smoke_test_learning_loop.py, STEPS_OUT): рядок «FAIL the card files are byte-for-byte the same» і «RESULT: FAIL». Окремий запуск uv run python scripts/smoke_test_learning_loop.py дає RESULT: PASS. Отже, якийсь тест запускає smoke в умовах, де картки змінюються між двома synthesize, і не перевіряє RESULT. Артефакт відновлено з git (як у задачі 308, commit b7c1d04).

- Записано: 2026-10-29T00:15:54Z, агент задачі 721
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Знайти тест, що під час повного прогону пише step-results/smoke.txt (кандидати: tests/contract/learning_loop_block/test_ll_block_acceptance.py, tests/contract/synthesizer/syn_catchup_smoke_run.py, tests/contract/notes_readers/nr_catchup_smoke_run.py); з'ясувати, чому картки змінюються; тест має писати в tmp, а не в .engine/artifacts/, і падати на RESULT: FAIL.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Чому зупинилась
- 2026-11-07T01:12:12Z — 3 спроб(и) поспіль не дали жодного commit-а; runner переніс задачу в `blocked/` і взяв наступну. Незакомічену роботу агента runner зберіг у гілці `wip/737-open-item-full-run-step-results-smoke-fail/20261107T011210Z` в origin (повернути в робоче дерево: `git fetch origin wip/737-open-item-full-run-step-results-smoke-fail/20261107T011210Z && git cherry-pick -n FETCH_HEAD`) і у сховку git на сервері runner-а (`git stash apply 762c51a2001f5189ad39aca43b3c80e3ff20db31`).

## Питання до власника
1. Задача застрягла: агент кілька спроб поспіль нічого не закомітив. Що робити далі? Будь-яка відповідь поверне задачу в чергу з новим лічильником спроб; вказівку агентові напишіть тут же.
   Відповідь:
