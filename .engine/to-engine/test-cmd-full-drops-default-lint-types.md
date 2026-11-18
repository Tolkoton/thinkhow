# TEST_CMD_FULL, заданий сам, вимикає типові ruff і mypy у шарах pre_commit і ci

Клас: 3
Залежить від: —
Потрібна присутність власника: ні
Режим: соло
Аудит потрібен: ні
Додаткові сесії: ні

## Що сталося
ThinkHow, задача 756 (2026-11-18): повний набір тестів довший за межу кроку gate (900 s), і найпростіше
виправлення — окрема повна команда тестів (`TEST_CMD_FULL="uv run pytest -n auto"`). Але в
`.claude/hooks/gate.py` `check_steps` (рядки ~870–880) у повних шарах `TEST_CMD_FULL` підставляється замість
`TEST_CMD`, і `any(configured.values())` стає true: кроки беруться лише із заданих команд, а `LINT_CMD` і
`TYPECHECK_CMD` порожні. Тож ruff і mypy у `pre_commit` і `ci` тихо зникають. Задати `LINT_CMD`/`TYPECHECK_CMD`
теж не вихід: тоді й шар Stop перестає вибирати тести за зміненими файлами. ThinkHow через це
обійшов цей ключ і ввімкнув `-n auto` в `addopts` у `pyproject.toml`.

## Що зробити
- Коли задано лише `TEST_CMD_FULL`, у шарах pre_commit і ci залишати автовизначення lint і type-check
  (замінювати тільки крок тестів).
- Тест двигуна: проєкт із `[tool.ruff]`, `[tool.mypy]` і лише `TEST_CMD_FULL` — у `--layer ci` є всі три кроки.

## Готово, коли
Шар ci проєкту, де задано лише `TEST_CMD_FULL`, запускає ruff, mypy і цю команду.
