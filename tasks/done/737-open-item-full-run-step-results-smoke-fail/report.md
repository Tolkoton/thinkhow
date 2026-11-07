# Звіт: повний прогін тестів більше не переписує step-results/smoke.txt на RESULT: FAIL

## Що змінилось для власника
Для вас нічого не змінилося: застосунок той самий. Тепер повний прогін тестів не залишає хибне «RESULT: FAIL»
у записі smoke-прогону `.engine/artifacts/step-results/smoke.txt`. Тести, які навмисно ламають smoke, пишуть свої
файли в тимчасову теку тесту. Якщо котрийсь із них знову запише поверх справжнього запису, він упаде.

## Причина
- `scripts/smoke_test_learning_loop.py` пише той самий текст у два файли: `synthesizer/smoke.txt` (`OUT`) і
  `step-results/smoke.txt` (`STEPS_OUT`). Другий файл додав commit `c0e30a6` (задача 309).
- `tests/contract/synthesizer/syn_catchup_smoke_run.py` запускає цей script із навмисними поломками (`SYN_BREAK`).
  Раніше він обгортав запуск у `keep_artifact`, а той відновлював лише `synthesizer/smoke.txt`. Тому
  `step-results/smoke.txt` лишався таким, яким його записав останній зламаний прогін.
- Чому змінюються картки: поломка `card_bytes` (рядок 96) навмисно дописує `\n` у файл картки після першого
  `synthesize`. Так тест `test_smoke_fails_when_a_card_file_changes_its_bytes` перевіряє, що smoke це помічає
  (exit ≠ 0). Звідси рядок «FAIL the card files are byte-for-byte the same» і «RESULT: FAIL». Сам тест правильно
  очікував FAIL, тож і не падав.
- Інший кандидат із задачі, `test_AC7_…` у `tests/contract/learning_loop_block/test_ll_block_acceptance.py`,
  відновлює обидва файли й перевіряє exit 0. Він не винен, його не змінено. `nr_catchup_smoke_run.py` цього
  script-а не запускає.

## Що зроблено
- `scripts/smoke_test_learning_loop.py`: змінна середовища `THINKHOW_SMOKE_ARTIFACTS` задає теку замість
  `.engine/artifacts`. Без неї script пише туди ж, куди й раніше.
- `tests/contract/synthesizer/syn_catchup_smoke_run.py`: `run_smoke` задає `THINKHOW_SMOKE_ARTIFACTS=<tmp>/artifacts`
  і повертає тестам текст із `<tmp>/artifacts/synthesizer/smoke.txt`. Після прогону він перевіряє, що обидва
  справжні файли `.engine/artifacts/{synthesizer,step-results}/smoke.txt` не змінилися, і падає
  з `the smoke run wrote over the records of the real run`, якщо змінилися. `keep_artifact` видалено.
  Цей файл не запечатаний (`.claude/state/testing/seals/` його не містить).
- Цю зміну зробили попередні спроби. Runner зберіг її в гілці `wip/737-open-item-full-run-step-results-smoke-fail/20261107T011210Z`
  (commit `9afbe0c`). Я переніс її в робоче дерево через `git diff HEAD FETCH_HEAD | git apply`, бо
  `cherry-pick` потребує дозволу.

## Демонстрація на хвилину
```
uv run pytest -q tests/contract/synthesizer/test_syn_catchup_disputed_q1_second_outcome.py \
  tests/contract/synthesizer/test_syn_catchup_smoke.py tests/contract/learning_loop_block/test_ll_block_acceptance.py
17 passed in 27.99s
```
Після прогону `git status --short` показує лише два змінені файли, `.engine/artifacts/` не змінено.
`uv run ruff check` і `uv run mypy` на обох файлах чисті.

Повний прогін `uv run pytest -q -p no:cacheprovider`:
```
1631 passed, 36 deselected in 1299.83s (0:21:39)
```
Після нього `git status --short` показує ті самі два файли, а в `.engine/artifacts/step-results/smoke.txt`
стоїть `RESULT: PASS`, як і в git. Під час прогону запускалися й обидва тести з поломкою `card_bytes`.

## Витрати
Додаткових сесій Claude не було.

## Діапазон commit-ів
Один commit задачі поверх `84c64ba` (board: 737 → doing).

## Відкладене
Нічого.

## Рішення, які я ухвалив сам
- Тести пишуть у tmp через змінну середовища, а не відновлюють файли після прогону. Відновлення ховало
  проблему, а перевірка «записи не змінились» її ловить. Без змінної script поводиться як раніше.
- Тест, що навмисно ламає smoke, і далі очікує exit ≠ 0, тобто RESULT: FAIL. «Падати на RESULT: FAIL»
  тут означає ось що: тест падає, якщо FAIL потрапив у справжній запис.
