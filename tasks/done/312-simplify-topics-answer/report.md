# 312 — Спростити `_answer` у `workspace/topics.py`: звіт

## Що змінилось для власника
- Для людини, що розмовляє з ThinkHow, не змінилось нічого: відповідь фасилітатора записується так само (`conversation.md`,
  мапа, routing, research, крок, `reply_superseded`). Змінилась лише будова коду.
- `_answer` у `src/thinkhow/workspace/topics.py` — функцію, через яку йде кожна відповідь, — розкладено на flow-метод і
  три помічники. Її cyclomatic complexity — 8 замість 19 (межа 10), nesting — 1 замість 3.

| Функція | complexity, nesting до | після |
|---|---|---|
| `_answer` | 19, 3 | 8, 1 |
| `_history` (нова: розмова до цього turn-а, як її бачить модель) | — | 5, 0 |
| `_stream` (нова: текст як `Delta`, решту збирає до update) | — | 5, 2 |
| `_write_after_answer` (нова: мапа, рішення router-а, research після запису відповіді) | — | 4, 1 |

Виміряно функцією `function_metrics` з `.claude/hooks/complexity_budget.py` — тією самою, якою рахує звіт догляду
`.engine/maintain/2026-11-03.md` (там `_answer` — 19).

## Демонстрація на хвилину
- Увесь набір до зміни (commit `771eeb9`): `uv run pytest -q` → `1628 passed, 36 deselected` (22 хв).
- Увесь набір після зміни: `uv run pytest -q` → `1628 passed, 36 deselected` (22 хв).
- `uv run pytest -q tests/contract/finish_answer` → `13 passed`; `git diff --stat -- tests` порожній: жоден тест не змінено.
- `uv run mypy` → `Success: no issues found in 59 source files`; `uv run ruff check src` → `All checks passed!`.
- overseer: PASS `20261106T235233Z-0f9336`.

## Витрати
Одна сесія board runner-а; додаткових сесій не було.

## Діапазон commit-ів
Від `771eeb9` (задача → doing) до commit-а, яким задача переходить у `done/`.

## Відкладене
- `_recognize` у тому самому файлі має complexity 13 при межі 10 — тепер найскладніша функція файлу. Це поза задачею
  (вона про `_answer`); покладено пропозицію `tasks/proposed/742-open-item-simplify-topics-recognize.md`.

## Рішення, які я ухвалив сам
- `_stream` — generator, що повертає зібране (`update`, рішення router-а, research) як свій return value через
  `yield from`, у маленькому frozen dataclass `_Facilitated`. Так `try/except` лишився в `_answer` навколо того самого
  коду: виняток фасилітатора, як і раніше, дає `reply_failed` з тією самою причиною.
- Читання потоку, як і раніше, зупиняється на update; те, що фасилітатор дав би після нього, не читається.
- Запис відповіді в `conversation.md` лишився в `_answer` (це головний крок flow), а записи після нього (мапа, routing,
  research) — у `_write_after_answer`, у тому самому порядку.
- Мертвого коду в файлі немає: vulture бачить лише `model_config` у pydantic-моделях — це налаштування pydantic, не
  невживана змінна.
