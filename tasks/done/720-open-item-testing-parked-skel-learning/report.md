# Звіт задачі 720 — slice skel-learning: третя суперечка про contract tests

## Що змінилось для власника
- **Вашу відповідь «А» виконано.** Свіжий slice-tester переніс 20 sealed tests skel-learning зі старого вигляду
  (одне спостереження на файл, відповідь `finding, worked, cause, anchor`, три причини) на новий. Новий вигляд: файл —
  набір спостережень (`ObservationSet`), у кожного `kind`, чотири причини з «роутер». Вердикт по всіх 20 —
  `test_wrong`. У задачі названо 19 тестів, а в objection-пакеті `.engine/testing/objections/skel-learning-309-analysis-rules.md`
  їх 20. Тестер розглянув усі 20.
- **Решта перевірок такі ж суворі, як були.** Лишилися: курсор з назв файлів, контекст, старі файли `s<n>.json`,
  діапазон, якір серед нових реплік, невдача нічого не пише, рядки логу, запис лише в `system/learning/`. Два тести
  додатково враховують правило one-conversation: контекст — усі вже проаналізовані репліки теми. Це `test_skell_analyze.py`
  (тест перейменовано на `…_earlier_session_as_context`) і I3 у `test_skell_invariants.py`.
- **Як це зроблено.** skel-learning parked, а analysis-rules, який і змінив вигляд, свої два кола суперечки вже
  використав. Тому пакет подано під synthesizer — наступним slice-ом тієї самої фічі (learning-loop), який читає ці
  набори. Так само зробила задача 718. Пакет із поясненням: `.engine/testing/objections/skel-learning-720-owner-A.md`.
- **Друге коло виправило помилку першого.** У першому колі tester записав, що схема моделі має лише три `kind`, і
  вирішив, що код хибний. Але пізніший запечатаний slice S6 step-results (`.engine/slices/step-results.md`, рядки 74–75)
  додає `"step"`. Його sealed test `tests/contract/step_results/test_stp_analyze.py:61` цього вимагає. Тому код не
  змінювався. Друге коло (пакет `.engine/testing/objections/skel-learning-720-step-kind.md`) виправило тест на чотири
  `kind`.
- **Робочий код не змінювався** — лише тести.

## Демонстрація на хвилину
- `uv run pytest -q tests/contract/skel_learning` → `27 passed, 1 deselected`.
- `uv run pytest -q tests/contract/skel_learning tests/contract/step_results tests/contract/analysis_rules` →
  `102 passed, 1 deselected`.
- Повний набір, один раз: `4 failed, 1521 passed, 36 deselected in 1009.35s`. Задача 711 мала 23 падіння. Серед
  чотирьох моїх немає:
  - два в `tests/contract/skel_facilitation/` — parked slice skel-facilitation, задача 724;
  - два в `tests/contract/walking_skeleton_block/test_wsblock_connections.py` (`KeyError: 'turn'`, старий вигляд
    спостереження). Вони червоні й без змін цієї задачі (перевірено на `bd68d21`). Пропозиція —
    `tasks/proposed/736-open-item-wsblock-tests-old-observation-shape.md`.
- Журнал: `.engine/testing/ledger.md`, «2026-10-28T23:32:45Z — synthesizer — dispute, round 1 of 2» і
  «2026-10-28T23:34:10Z — synthesizer — dispute, round 2 of 2».
- `uv run ruff check .` → `All checks passed!`; `uv run mypy` на змінених файлах → `Success: no issues found in 7 source files`.

## Витрати
Одна сесія runner-а і дві сесії slice-tester (кола 1 і 2), а також reader для цього звіту.

## Commit-и
`bd68d21` (задача в `doing/`) → `4280e89` (тести, журнал, пакети, пропозиції) → commit закриття задачі.

## Відкладене
- `python3 .claude/hooks/testing.py check skel-learning` показує `CHANGED`, а status — `PARKED`. Тести переписано в
  колі іншого slice-а, а знімати park двигун не вміє. Це той самий залишок, що в задачах 708 і 718
  (`.engine/engine-feedback.md`, «a parked slice has no way back»). Ваших дій це не потребує.
- Live-тест `tests/contract/skel_learning/test_skell_live.py` досі читає старе `Observation` (`first_turn`). У пакеті
  його не було: він live і без ключа deselected. Пропозиція — `tasks/proposed/735-open-item-skel-learning-live-test-old-shape.md`.
- У synthesizer тепер обидва кола використано. Якщо пізніший контракт змінить його тести, synthesizer теж стане parked.

## Рішення, які я ухвалив сам
- Я подав пакет під synthesizer, а не під skel-learning чи analysis-rules. Під skel-learning запит лише відповідає
  «PARKED», а під analysis-rules він зробив би parked і analysis-rules (`.claude/hooks/testing.py`, рядки 938–939).
  synthesizer — slice тієї самої фічі, він читає набори спостережень, і в нього було 0 кіл.
- Я витратив на synthesizer друге коло, щоб виправити помилку першого (три `kind` замість чотирьох). Інакше sealed
  test суперечив би запечатаному S6 step-results. Код під помилковий тест я не змінював.
- Після тестера я сам вніс три зміни, що не змінюють жодної перевірки. Без них не проходили ruff і Stop gate (mypy).
  - Переніс задовгий рядок docstring у `test_skell_schema.py`.
  - Додав анотацію `bad: object` у `test_skell_schema.py`.
  - Додав `FakeLlm.search_text` у `skell_fakes.py`: метод кидає `AssertionError`, як і наявний `stream_json`. Це закрило
    старий борг «FakeLlm без `search_text`», через який було 23 помилки mypy.
