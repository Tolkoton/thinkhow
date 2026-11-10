# Звіт: помилка `/reply` з фрагментом у режимі розмови — тепер тест перевіряє і #mic, і #send

## Що змінилось для власника
Для вас нічого не змінилося: код режиму розмови (`src/thinkhow/web/static/conversation.js`) лишився тим самим, додано
лише тест. Тест — `tests/contract/conversation_loop/cl_gap_reply_error.test.mjs`, для pytest його запускає
`tests/contract/conversation_loop/test_cl_gap_reply_error.py`. Сценарій такий: режим увімкнено, `/voice` розпізнав
«Привіт», а `/reply` відповідає 409 з фрагментом `<p class="error">Спершу дочекайтеся відповіді.</p>`. Тест вимагає:
- `/retry` не викликано жодного разу;
- у `#error` стоїть саме текст фрагмента;
- режим вимкнено (`data-state=""`), сторінка не перезавантажилась;
- `#mic` і `#send` знову доступні (до помилки режим їх вимикав, і тест перевіряє це теж).

Справжньої вади тест не знайшов: на коді як він є він зелений.

Що з'ясувалось про сам брак тесту. Overseer знайшов його 2026-10-27. Відтоді sealed tests цього slice-а переписав
tester (commit `f8e999f`, правило S2b), і тест «an error with a fragment (3 /voice not 200 in a row, /reply 409)»
у `tests/contract/conversation_loop/cl_talk.test.mjs` уже ловить дві з трьох вад, які назвав overseer: загублений
текст і перехід у page ui з reload. Не ловив він третю: після помилки `/reply` `#mic` і `#send` лишаються вимкненими.
Тест `cl_disputed_q4_enable.test.mjs` перевіряє це лише для помилки `/voice`. Новий тест закриває саме цю прогалину.

## Демонстрація на хвилину
Червоні прогони. Код тричі тимчасово ламав, після кожного зламу відновлював із копії. Щоразу запускав новий тест, а
також `cl_talk.test.mjs` разом із `cl_disputed_q4_enable.test.mjs` (`node --test …`):

1. Текст губиться: `showError: (text, status) => talk.failed(undefined, status)` у `modeUi`.
   Новий тест: `fail 1`, `actual: 'Режим розмови зупинено — спробуйте ще раз.'`, `expected: 'Спершу дочекайтеся відповіді.'`.
   Sealed: `pass 15, fail 1`.
2. Помилка йде в page ui з reload: `showError: (text) => { ui.showError(text); ui.reload(); }`.
   Новий тест: `fail 1`, `actual: 'thinking'`, `expected: ''`. Sealed: `pass 15, fail 1`.
3. Після 409 `#mic` і `#send` лишаються вимкненими: у `failed()` замість `return halt();` стоїть `halt();`,
   за ним `for (const id of ["mic", "send"]) doc.getElementById(id).disabled = true;`.
   Новий тест: `fail 1`, `AssertionError: #mic`, `actual: true`, `expected: false`. Sealed: `pass 16, fail 0`,
   тобто без нового тесту цю ваду не ловив жоден тест.

Зелений прогін на коді як він є:
```
node --test tests/contract/conversation_loop/cl_gap_reply_error.test.mjs   → pass 1, fail 0
uv run pytest -q tests/contract/conversation_loop/                          → 57 passed in 324.51s
```
`uv run ruff check tests/contract/conversation_loop/` → `All checks passed!`; `uv run mypy
tests/contract/conversation_loop/test_cl_gap_reply_error.py` → `Success: no issues found in 1 source file`.

Повний набір: `uv run pytest -q -p no:cacheprovider` → `1635 passed, 36 deselected in 1218.79s`; після прогону робоче дерево не змінилось (`git status`).

## Витрати
Одна сесія runner-а. Додаткових сесій Claude не було.

## Діапазон commit-ів
Від `be86d83` (задача в `doing/`) до commit-а, що переносить задачу в `done/`.

## Відкладене
- `python3 .claude/hooks/testing.py check conversation-loop` відповідає `CHANGED` для `cl_talk.test.mjs` і
  `cl_disputed_q4_enable.test.mjs`. На початку задачі робоче дерево було чисте, і цих файлів я не чіпав, тож це
  стан, що був до задачі. Найімовірніше, після переписування в `f8e999f` їх не запечатали знову. Повторну
  печатку робить лише власник (`testing.py reseal … --owner-answer <card>`). Окремої задачі я не відкривав.

## Рішення, які я ухвалив сам
- Тест лежить в окремому файлі, а не в `cl_talk.test.mjs`. Той файл sealed для slice-а `conversation-loop`, а builder
  не редагує файлів tester-а. Так само зроблено в задачі 713.
- Третій злам штучний, але реалістичніші не підійшли. Варіант `modeUi.showError` → `ui.disable()` не дає червоного:
  controller після `showError` сам викликає `ui.enable()`, а `halt()` через `ui.state("")` вмикає `#mic` і `#send`.
  Тому злам стоїть там, де саме цей шлях (`failed()` для 409) вирішує, що буде з елементами керування.
