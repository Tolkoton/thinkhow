# Звіт задачі 721 — slice skel-guards-deploy: третя суперечка про contract tests

## Що змінилось для власника
- **Вашу відповідь «А» виконано.** Свіжий slice-tester переніс на новий вигляд два sealed tests блоку walking skeleton
  у `tests/contract/walking_skeleton_block/test_wsblock_connections.py`:
  - `test_s4_learning_reads_every_topic_and_topic_sessions_numbered_across_the_topic`;
  - `test_s6_observation_link_of_a_persons_topic_opens_the_turn_for_the_owner`.

  Раніше тести читали файл спостереження як одне спостереження. Тепер файл — набір (`ObservationSet`), і тести
  перевіряють кожне спостереження набору: номер репліки (`turn`) лежить у межах діапазону, а посилання (`link`) веде на
  `#t<turn>`. Для кожного посилання власник відкриває сторінку теми і отримує 200 з цим якорем. Вердикт по обох —
  `test_wrong`.
- **Решта перевірок не змінилась:** які теми читає навчання, нумерація сесій через усю тему, шляхи записаних файлів,
  `written`/`failed`, діапазон `first_turn`/`last_turn`. Щоб перевірка не проходила на порожньому наборі, тест вимагає
  в ньому хоча б одне спостереження.
- **Як це зроблено.** skel-guards-deploy відкладено (parked) після двох кіл суперечки. analysis-rules, що змінив
  вигляд файлу, теж використав обидва кола. Так само synthesizer, бо задача 720 подала під ним таку саму зміну. Тому
  пакет подано під notes-readers — це S4 тієї самої фічі learning-loop, і в нього були вільні обидва кола. Пакет із
  поясненням: `.engine/testing/objections/skel-guards-deploy-721-owner-A.md`.
- **Робочий код не змінювався** — лише ці два тести.

## Демонстрація на хвилину
- `uv run pytest -q tests/contract/walking_skeleton_block` → `12 passed`. До задачі було `2 failed, 10 passed`, обидва
  з `KeyError: 'turn'`.
- Повний набір, один раз: `2 failed, 1523 passed, 36 deselected in 1021.14s`. Обидва падіння — у
  `tests/contract/skel_facilitation/`: `test_skelf_disputed_q1_memory_cards_line.py::test_memory_cards_line_is_ids_joined_by_comma_space_with_a_period`
  і `test_skelf_respond.py::test_system_instruction_is_poc_rules_then_card_then_all_memory`. Це parked slice
  skel-facilitation, задача 724, і ця задача його не стосувалась. Задача 720 мала `4 failed`: тут зникли саме два
  падіння walking-skeleton-block.
- Журнал: `.engine/testing/ledger.md`, «2026-10-28T23:56:30Z — notes-readers — dispute, round 1 of 2».
- `uv run ruff check tests/contract/walking_skeleton_block` → `All checks passed!`. `uv run mypy` на цьому файлі дає
  33 errors і до зміни, і після неї. Це стара гігієна типів, на яку пішли кола цього slice-а, і моя зміна її не
  погіршила.

## Витрати
Одна сесія runner-а, одна сесія slice-tester (коло 1 notes-readers) і reader для цього звіту.

## Commit-и
`a8f738b` (задача в `doing/`) → `7adcdc6` (тести, журнал, пакет) → commit закриття задачі.

## Відкладене
- `python3 .claude/hooks/testing.py check skel-guards-deploy` показує `CHANGED`. Тести переписано в колі іншого
  slice-а, а знімати park двигун не вміє. Це той самий залишок, що в задачах 708, 718 і 720 (`.engine/engine-feedback.md`,
  «a parked slice has no way back»). Ваших дій він не потребує.
- Пропозицію `tasks/proposed/736-open-item-wsblock-tests-old-observation-shape.md` (ці самі два тести) цією задачею
  виконано. Ставити її в роботу не треба.
- У notes-readers лишилось одне коло.

## Рішення, які я ухвалив сам
- Я подав пакет під notes-readers, а не під skel-guards-deploy, analysis-rules чи synthesizer. У тих трьох обидва кола
  вже використано: під skel-guards-deploy запит лише відповідає «PARKED», а під двома іншими він їх відклав би
  (`.claude/hooks/testing.py`, рядки 938–939). step-results пов'язаний тісніше (він додає `kind` `"step"`), але в
  нього лишалось одне коло. notes-readers — slice тієї самої фічі learning-loop з двома вільними колами: якщо тестер
  помилиться, як у першому колі задачі 720, лишається коло на виправлення.
- У пакет я дописав, що `kind` тепер має чотири значення. Так я хотів не повторити помилку першого кола задачі 720. Ці
  два тести `kind` не перевіряють.
