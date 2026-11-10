# Звіт: smoke learning loop тепер перевірено й на тому, що другий synthesize, який знову віддав старі спостереження моделі й отримав відмову, — це провал

## Що змінилось для власника
Код не змінився. Додано один тест:
`tests/contract/synthesizer/test_syn_gap_second_synthesize_refused.py`, функція
`test_smoke_fails_when_the_second_synthesize_refeeds_and_is_refused`.

Тест запускає smoke-скрипт `scripts/smoke_test_learning_loop.py` через sealed bootstrap
`syn_catchup_smoke_run.BOOT` і додає перед ним одну поломку. Під час другого виклику справжнього `synthesize`:
- `_new` знову віддає всі спостереження, тобто старі (re-fed);
- модель справді викликається;
- `_apply` відмовляє (`rejected`) і нічого не пише;
- run record не пишеться.

Отже, ревізії немає і другого run record теж немає. Дві перевірки smoke («no second run record» і «and wrote no
revision») такий прогін пропускають. Саме цей випадок і описав overseer. Тест вимагає, щоб smoke завершився з
ненульовим кодом і надрукував `a second synthesize took nothing new: rejected`.

Справжньої вади тест не знайшов: на скрипті, як він є, тест зелений.

Як стоїть брак, який назвав overseer:
- Скрипт виправили ще 2026-10-27 у commit-і `885f1ab`. Відтоді smoke читає зі stdout рядок `synthesize_done` і
  вимагає `outcome == "nothing_new"` (`scripts/smoke_test_learning_loop.py:162`). Тим самим commit-ом додано catch-up
  тести, серед них `test_syn_catchup_disputed_q1_second_outcome.py` (sealed). Цей тест ловить лише випадок «другий
  прогін тихо впав» (`failed`, рядка `synthesize_done` немає).
- Випадок «знову віддав старі спостереження, отримав відмову» досі не перевіряв жоден тест. Новий тест закриває саме
  його: виклик моделі відбувся, outcome — `rejected`, нічого не записано.

## Демонстрація на хвилину
Червоні прогони. Рядок 162 скрипта я тимчасово замінював, а після кожної заміни повертав файл командою
`git checkout scripts/smoke_test_learning_loop.py` (наприкінці `git status` показує лише новий тест). Щоразу
запускав `uv run pytest -q tests/contract/synthesizer`:

1. Рядок, про який писав overseer: `check(code == 0 and runs(storage)[-1].considered != [], "a second synthesize ran")`.
   Результат: `2 failed, 64 passed`. Червоні новий тест і sealed `disputed_q1`.
2. Рядок до виправлення (як до `885f1ab`): `check(code == 0, "a second synthesize ran")`. Результат: `2 failed, 64 passed`,
   червоні ті самі два тести.
3. Прочитання «другий прогін нічого не застосував»: `check(code == 0 and bool(done) and outcome != "applied", ...)`.
   Результат: `1 failed, 65 passed`. Червоний лише новий тест, sealed suite зелений. Ось щілина, яку закриває новий тест.

Окремо пробував весь скрипт із commit-а `afbcee1`. Він червоний з іншої причини: він ще пише в справжній
`.engine/artifacts/synthesizer/smoke.txt`, і `run_smoke` це помічає. Тому цей прогін не враховую як доказ. Артефакт
відновив з git.

Зелений прогін на коді, як він є:
```
uv run pytest -q tests/contract/synthesizer/test_syn_gap_second_synthesize_refused.py  → 1 passed
uv run pytest -q tests/contract/synthesizer  → 66 passed
```
Перевірки нового файлу:
- `uv run ruff check` → `All checks passed!`;
- `uv run ruff format` переформатував файл: прибрав зайвий порожній рядок у кінці;
- `uv run mypy` → `Success: no issues found in 1 source file`.

Повний набір: `uv run pytest -q -p no:cacheprovider` → `1638 passed, 36 deselected in 1237.23s` (1637 у задачі 722 плюс новий
тест); після прогону дерево чисте, крім нових файлів задачі. Перший прогін я зупинив сам: він уперся б у межу часу
фонової команди. Його перерваний smoke прибрав `.engine/artifacts/conversation-resilience/smoke.txt`; файл відновив
з git, а другий прогін пройшов до кінця.

## Витрати
Одна сесія runner-а. Додаткових сесій Claude не було, live-прогонів моделі теж: модель у smoke — локальний скрипт Job-а.

## Діапазон commit-ів
Від `bc1a695` (задача в `doing/`) до commit-а, що переносить задачу в `done/`.

## Відкладене
- Seam 1 контракту (`.engine/slices/synthesizer.md:125`) вимагає ще й «жодного виклику моделі». Smoke не рахує виклики
  моделі окремо. Достатньо перевірки outcome: справжній `synthesize` кличе модель лише тоді, коли є нові спостереження,
  а тоді outcome уже не `nothing_new`. Окремий лічильник викликів не додавав.

## Рішення, які я ухвалив сам
- Тест лежить в окремому файлі. Файли `test_syn_catchup_smoke.py` і `test_syn_catchup_disputed_q1_second_outcome.py`
  sealed для slice-а `synthesizer` (`.claude/state/testing/seals/synthesizer.json`). Тому поломку я не дописував у
  sealed `BOOT`, а поставив перед ним через `monkeypatch.setattr` у самому тесті.
- Поломку зроблено через справжній `synthesize` (підмінено лише `_new`, `_apply` і `_write_run` на другому виклику), а
  не через готовий `SynthesisReport`. Так тест показує, що модель справді викликали, і перевіряє рядок `synthesize_done`,
  який друкує сам код.
- Із двох варіантів, які дозволяла задача («outcome `nothing_new`» або «нуль викликів моделі»), взяв перший: smoke уже
  перевіряє саме його.
