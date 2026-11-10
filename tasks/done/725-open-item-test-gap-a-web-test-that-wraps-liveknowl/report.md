# Звіт: одна відповідь у web app тепер перевірена на «один `latest_pair` і нуль читань, скільки б не було нотаток»

## Що змінилось для власника
Код не змінився. Додано один тест:
`tests/web/test_live_knowledge_gap_one_pair_a_reply.py`, функція
`test_one_full_reply_lists_once_and_reads_nothing_whatever_the_number_of_notes`. Вона запускається тричі: з 0, 1 і 40
нотатками.

Тест загортає `LiveKnowledge` (`src/thinkhow/web/app.py:52`). Storage — `LocalStorage` з лічильником кожного `list` і
кожного `read`. Тест проганяє одну повну відповідь `respond`: router обирає `pre-mortem`, далі відповідає facilitator
цієї картки. Тест перевіряє чотири речі:
- обидва виклики моделі справді були (два виклики, перший — зі схемою router-а; є `RoutingEvent` і `FacilitatorUpdate`);
- `knowledge.latest_pair` викликано рівно один раз;
- storage за відповідь зробив рівно 2 listings і 0 reads;
- нотатки router-а є в його system instruction.

Справжньої вади тест не знайшов: на коді, як він є, тест зелений.

Як стоїть брак, який назвав overseer (2026-10-27T21:45Z, запит `20261027T214157Z-023d21`):
- Ваду per-field refresh прибрав commit `043f651`. Він же додав тест
  `test_one_reply_lists_the_newest_revision_once_and_reads_one_revision` у `tests/web/test_live_knowledge.py`. Той тест
  рахує `latest_pair` на одній відповіді з 25 нотатками, тож саме цей випадок він уже ловить.
- Не ловив жоден тест варіант «читати Knowledge знову на кожній відповіді». Тоді `latest_pair` викликається один раз,
  а читань стільки ж, скільки нотаток. Новий тест закриває цей варіант: він рахує listings і reads самого storage.

## Демонстрація на хвилину
Червоні прогони. Я тимчасово міняв `src/thinkhow/web/app.py`, а після кожної заміни повертав файл з копії
(наприкінці `git status` показує лише нові файли задачі). Щоразу запускав `uv run pytest -q tests/web/ -k live_knowledge`:

1. Стара per-field refresh з `cd1d07e`: `LiveKnowledge` з `__getattribute__`, який робить refresh на кожному читанні
   поля, а `now()` повертає `self`. Результат: `5 failed, 2 passed`. Новий тест червоний на всіх трьох кількостях:
   `latest_pair` викликано 12, 12 і 32 рази на 0, 1 і 40 нотаток, тобто кількість росте з нотатками. Старий тест теж
   червоний: 37 замість 1.
2. Повторне читання на кожній відповіді: у `now()` після `latest_pair` додано `knowledge.current(...)` і заміну
   `memory`, коли вона інша. Результат: `3 failed, 4 passed`. Червоний лише новий тест: `(4, 26)`, `(4, 28)` і `(4, 67)`
   замість `(2, 0)`. Чотири старі тести `test_live_knowledge.py` зелені. Ось щілина, яку закриває новий тест.

Зелений прогін на коді, як він є:
```
uv run pytest -q tests/web/test_live_knowledge_gap_one_pair_a_reply.py  → 3 passed
uv run pytest -q tests/web  → 86 passed
```
Перевірки нового файлу: `uv run ruff check` → `All checks passed!`; `uv run ruff format` → `1 file left unchanged`;
`uv run mypy` → `Success: no issues found in 1 source file`.

Повний набір: `uv run pytest -q -p no:cacheprovider` → `1641 passed, 36 deselected in 1238.59s` (1638 у задачі 723 плюс три прогони нового тесту); після прогону дерево чисте, крім нових файлів задачі.

## Витрати
Одна сесія runner-а. Додаткових сесій Claude не було, live-прогонів моделі теж: модель у тесті —
`ScriptedLlm(local_script)`.

## Діапазон commit-ів
Від `230de7f` (задача в `doing/`) до commit-а, що переносить задачу в `done/`.

## Відкладене
Нічого.

## Рішення, які я ухвалив сам
- Тест лежить в окремому файлі, а не дописаний у `tests/web/test_live_knowledge.py`. Так його видно як закриття цього
  браку, а старий тест лишається, як є.
- Окрім `latest_pair`, тест рахує listings і reads самого storage. Задача просить лише «`latest_pair` рівно один раз»,
  але refresh, яка читає Knowledge повз `latest_pair`, ту перевірку проходить (прогін 2 вище).
- Кількість нотаток: 0, 1 і 40, щоб «скільки б не було нотаток» було видно як однакове число на всіх трьох. Нотатки
  навпіл для router-а і facilitator-а, щоб нотатки бачили обидва.
