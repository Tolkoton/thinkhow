# Звіт: smoke learning loop тепер перевірено й на тому, що питання про крок, поставлене знову перед блоком «Кроки», — це провал

## Що змінилось для власника
Код не змінився. Додано один тест:
`tests/contract/synthesizer/test_syn_gap_question_before_steps.py`, функція
`test_smoke_fails_when_the_question_comes_again_before_the_steps_block`.

Тест запускає smoke-скрипт `scripts/smoke_test_learning_loop.py` через sealed bootstrap
`syn_catchup_smoke_run.BOOT` і ставить перед ним одну поломку з двох частин:
- `open_topic` запам'ятовує питання про крок, яке раз показав, і повертає його знову на кожному пізнішому перегляді
  теми, де вже є результати кроків (тобто питає вдруге);
- `topic.html` малює секцію `step-question` перед блоком «Кроки», а не після нього.

Тест перевіряє, що поломка справді та, яку описав overseer: на останній сторінці теми є і «Кроки», і «Як він вийшов»,
але в тексті після «Кроки» питання немає. Тоді smoke мусить завершитися з ненульовим кодом, і єдиний рядок `FAIL` у
ньому — `no question about it again`.

Справжньої вади тест не знайшов: на скрипті, як він є, тест зелений.

Як стоїть брак, який назвав overseer:
- Скрипт виправили ще 2026-10-28 у commit-і `c0e30a6`. Відтоді smoke шукає секцію на всій сторінці:
  `check('class="turn model step-question"' not in client.get(topic).text, "no question about it again")`
  (`scripts/smoke_test_learning_loop.py:109`). Тест на цю перевірку тоді не дописали.
- Новий тест закриває саме це: стара перевірка (лише текст після «Кроки») і схожа на неї (клас `step-question` лише
  після «Кроки») пропускають поломку, sealed suite їх теж пропускає, а новий тест — ні.

## Демонстрація на хвилину
Червоні прогони. Рядок 109 скрипта я тимчасово замінював, а після кожної заміни повертав файл командою
`git checkout scripts/smoke_test_learning_loop.py` (наприкінці `git status` показує лише новий тест). Щоразу запускав
`uv run pytest -q -p no:cacheprovider tests/contract/synthesizer tests/contract/step_results tests/contract/learning_loop_block`:

1. Рядок до виправлення (як до `c0e30a6`):
   `check("Як він вийшов" not in client.get(topic).text.split("Кроки", 1)[-1], "no question about it again")`.
   Результат: `1 failed, 120 passed`. Червоний лише новий тест: smoke надрукував `RESULT: PASS` і вийшов з кодом 0
   (`assert result.returncode != 0`, рядок 85 тесту).
2. Те саме, але за класом: `check('step-question' not in client.get(topic).text.split("Кроки", 1)[-1], ...)`.
   Результат: `1 failed, 120 passed`, червоний лише новий тест.

Зелений прогін на коді, як він є:
```
uv run pytest -q tests/contract/synthesizer/test_syn_gap_question_before_steps.py  → 1 passed
uv run pytest -q -p no:cacheprovider tests/contract/synthesizer tests/contract/step_results tests/contract/learning_loop_block  → 121 passed
```
Перевірки нового файлу: `uv run ruff check` → `All checks passed!`; `uv run ruff format --check` → `1 file already
formatted`; `uv run mypy` → `Success: no issues found in 1 source file`.

Повний набір: `uv run pytest -q -p no:cacheprovider` → `1643 passed, 36 deselected in 1237.91s` (1642 у задачі 726 плюс новий тест); після прогону `git status` показує лише новий тест і теку звіту.

## Витрати
Одна сесія runner-а. Додаткових сесій Claude не було, live-прогонів моделі теж: модель у smoke — локальний скрипт Job-а.

## Діапазон commit-ів
Від `5e9b4de` (задача в `doing/`) до commit-а, що переносить задачу в `done/`.

## Відкладене
Нічого.

## Рішення, які я ухвалив сам
- Тест лежить в окремому файлі в `tests/contract/synthesizer/`, поруч із helper-ом `syn_catchup_smoke_run.py`, який
  запускає цей самий smoke. Поломку я поставив перед sealed `BOOT` через `monkeypatch.setattr`, як у задачі 723, і
  sealed файлів не міняв.
- Поломка двоскладова, бо одне лише перенесення секції в шаблоні нічого не показало б: на справжньому коді питання
  після відповіді не ставиться, тож секції на сторінці немає взагалі. Щоб стара перевірка пропустила поломку, треба,
  щоб питання і з'явилося вдруге, і стояло перед «Кроки».
- Шаблон поломки береться з самого `topic.html` (секція `step-question` переноситься перед `{% if view.steps %}`), а
  не переписаний руками. Так тест стежитиме за справжнім шаблоном; якщо секцію в ньому перейменують, bootstrap упаде
  на своєму `assert`, і тест стане червоним, а не тихо зеленим.
