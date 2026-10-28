# 407 — Регулярний догляд 2026-10-27: звіт

## Що змінилось для власника

- Написано звіт догляду `.engine/maintain/2026-10-28.md` (`python3 .claude/hooks/maintain.py report`; дата у назві —
  день запуску, задачу поклали 2026-10-27). Порівняння — з першим звітом від 2026-10-19, коли коду ще не було.
- **Оновлювати нічого не пропоную:** `python3 .claude/hooks/maintain.py question` завершився з кодом 3
  («nothing to update»), бо `DEPS_OUTDATED_CMD` порожня і `updates.json` не створено. Тому задача йде в `done/`, а не в `blocked/`.
- Головне зі звіту:
  - **Dependencies:** кроку немає — `DEPS_OUTDATED_CMD` і `DEPS_AUDIT_CMD` у `.claude/project.env` порожні.
    Але stack уже є (`pyproject.toml`, `uv.lock`), і ручна перевірка `uv pip list --outdated` 2026-10-28 показала
    16 застарілих пакетів у середовищі (наприклад, `fastapi` 0.159.1 → 0.162.0, `google-genai` 2.32.0 → 2.33.0,
    `pytest` 9.1.1 → 9.2.0). Звідси пропозиція 7.
  - **Complexity — різке зростання:** файлів робочого коду 54 (медіана останніх 5 вимірів — 35), рядків 5837 (2635),
    функцій 380 (185), функцій понад межу complexity 8 (1), понад межу nesting 3, знахідок dead code 30 (13),
    duplication 0, unused dependencies 4. Звіт за правилом пропонує покликати simplifier-а (пропозиція 6).
  - **Hot places:** `src/thinkhow/workspace/topics.py` (змін 11, complexity 15), `src/thinkhow/web/server.py` (13, 11),
    `src/thinkhow/facilitation/respond.py` (12, 11), `src/thinkhow/facilitation/route.py` (7, 17),
    `src/thinkhow/learning/analyze.py` (4, 14).
  - **Snapshot «як було»:** немає — gates вимагають чистого.
  - **Борги термінових виправлень (hotfix debt):** відкрито 0 з 3, прострочено 0.
  - **Lesson queue:** 8 кандидатів, найстаріший від 2026-10-28; пропозицій правил, що чекають відповіді, — 0;
    прибирання пам'яті — ще не час.
- **Пропозиції задач** (у звіті, розділ «Пропозиції задач»): 1–6 написав скрипт — спростити п'ять hot places і
  покликати simplifier-а на зростання. 7–9 додав я, кожна з числом під нею:
  7. заповнити `DEPS_OUTDATED_CMD` командою `uv pip list --outdated --format json` (лише читає; `maintain.py` розбирає її JSON);
  8. прибрати `google-cloud-speech` з `pyproject.toml` — єдина справжня з 4 знахідок unused dependency (решта три —
     хибні: інші назви модулів при імпорті, `jinja2` потрібен `fastapi.templating`);
  9. навчити simplifier-а pydantic: 14 із 30 знахідок dead code — `model_config`, ще кілька — validators, які pydantic
     викликає сам, тож число dead code завищене приблизно вдвічі.

## Демонстрація на хвилину

```bash
cat .engine/maintain/2026-10-28.md
python3 .claude/hooks/maintain.py question     # exit 3: оновлювати нічого
uv pip list --outdated --format json            # команда з пропозиції 7, лише читає
```

## Витрати

Додаткових сесій Claude не запускалось, крім агента `reader` для цього звіту.

## Діапазон commit-ів

Від `9c03169` (задача → `doing/`) до commit-а, що переносить задачу в `done/` разом зі звітом догляду.

## Відкладене

- 25 червоних тестів у повному `pytest` (commit `4b038d6`: 1458 passed, 25 failed) — не нова знахідка: вони вже
  описані з питаннями до вас у `tasks/blocked/308-voice-conversation-mode.md` (sealed tests, що чекають відповідей
  у задачах 720, 721, 724 і 208), тож окремої пропозиції не додав.
- Пропозиції 1–9 лишились у звіті догляду; у `todo/` задачі ставите лише ви.

## Рішення, які я ухвалив сам

- Додав три пропозиції (7–9) лише там, де їх підтримує число у звіті, і перевірив кожну: команду з пропозиції 7
  запустив (вона лише читає), знахідки unused dependency і dead code звірив із кодом через `grep`.
- `DEPS_OUTDATED_CMD` сам не заповнив: `/maintain` нічого не змінює, а що сканувати — рішення окремої задачі.
- Незакомічену зміну `.claude/unattended/board-runner.sh` у робочому дереві не чіпав і в commit не брав: це ваша
  правка, не робота догляду.
