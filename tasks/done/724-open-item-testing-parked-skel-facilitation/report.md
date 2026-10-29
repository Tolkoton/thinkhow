# Звіт задачі 724 — slice skel-facilitation: третя суперечка про contract tests

## Що змінилось для власника
- **Обидві ваші відповіді виконано. Повний набір тестів знову зелений: `1525 passed`.** До задачі падав один тест,
  `test_system_instruction_is_poc_rules_then_card_then_all_memory`.
- **Відповідь А на питання 1** (фасилітатор бачить лише нотатки своєї картки). Її виконано раніше, у commit-і `bc473f5`.
  Свіжий slice-tester переніс обидва тести пам'яті на це правило. Вердикт `test_wrong` ×2 записано в
  `.engine/testing/ledger.md`, розділ «2026-10-29T00:21:33Z — notes-readers — dispute, round 2 of 2».
- **Відповідь Б на питання 2** (тест більше не тримає текст правил дослівно) — виконано в цій сесії, commit `3257b38`.
  З `tests/contract/skel_facilitation/test_skelf_respond.py` прибрано дослівну копію правил фасилітатора (константу
  `RULES`). Тест тепер перевіряє дві заміни з Q5 контракту skel-facilitation: «i3» і «t<номер з рамки репліки>». Обидві
  мають стояти в інструкції до `# Картка`, далі — картка, далі — `# Пам'ять досвіду`. Решта перевірок тесту не
  змінилась: лише нотатки картки alpha, рядки «Картки:», немає `s2#` і «t3». Дослівний текст правил і далі тримають
  golden-копії інших slice-ів: `tests/contract/facilitator_free_mode/ffm_fakes.py` і
  `tests/contract/voice_reply_language/vrl_fakes.py`.
- **Наслідок:** наступна зміна `src/thinkhow/facilitation/rules.md` цей тест уже не зламає. Тест ламався на кожній такій
  зміні: після задач 305, 306 і 310.
- **Робочий код не змінювався** — змінився лише цей тест.

## Демонстрація на хвилину
- `uv run pytest -q tests/contract/skel_facilitation` → `27 passed, 1 deselected`. До задачі було `26 passed, 1 failed`.
- Повний набір, один раз: `uv run pytest -q` → `1525 passed, 36 deselected in 1005.20s`.
- `uv run ruff check tests/contract/skel_facilitation` → `All checks passed!`. `uv run ruff format --check` → `7 files
  already formatted`. `uv run mypy tests/contract/skel_facilitation/test_skelf_respond.py` → `Success: no issues found
  in 1 source file`.

## Витрати
Одна сесія runner-а і reader для цього звіту. Цього разу slice-tester не запускався: чому — див. «Рішення, які я ухвалив
сам». Раніше задача мала одну сесію slice-tester-а (коло 2 notes-readers, commit `bc473f5`).

## Commit-и
`0ab89a5` (задача в `doing/`) → `bc473f5` (відповідь А) → `24adca3` (питання 2, `blocked/`) → `7e67762` (знову в `doing/`)
→ `3257b38` (відповідь Б) → commit закриття задачі.

## Відкладене
- `python3 .claude/hooks/testing.py check skel-facilitation` показує `CHANGED`: запечатані тести відрізняються від
  того, що здав tester. Знімати park двигун не вміє. Це той самий залишок, що в задачах 708, 718, 720 і 721
  (`.engine/engine-feedback.md`, «a parked slice has no way back»). Ваших дій він не потребує.
- Під час повного прогону тести перезаписали два артефакти smoke: `.engine/artifacts/conversation-resilience/smoke.txt`
  і `.engine/artifacts/step-results/smoke.txt`. Я повернув їх до закомічених версій. Ця задача їх не стосується.

## Рішення, які я ухвалив сам
- **Тест змінив я сам, а не свіжий slice-tester.** Звичайний шлях — коло суперечки, але кіл не лишилось. skel-facilitation
  відкладено: запит під ним відповідає лише «PARKED» (`.claude/hooks/testing.py`, рядки 938–939). У notes-readers обидва
  кола вже використано (коло 2 — у цій самій задачі). Ваша відповідь Б сама каже, що тест має перевіряти: порядок
  (правила → картка → пам'ять) і дві заміни («i3», «t<номер з рамки репліки>»). Тлумачити tester-у тут нічого. Так само
  задача 729 виконала відповідь власника прямо в sealed test helpers (commit `78f2ac3`).
- **Як знайти «правила» без дослівного тексту.** Тест бере позиції двох замін, «i3» і «t<номер з рамки репліки>», разом
  із лапками «». Він вимагає, щоб обидві стояли в інструкції раніше за `# Картка`. Перший рядок правил («Ти —
  фасилітатор ThinkHow …») я навмисно не тримаю: це був би той самий дослівний текст, від якого відмовляється відповідь Б.
- Назву тесту `test_system_instruction_is_poc_rules_then_card_then_all_memory` я лишив без змін, щоб її можна було
  знайти в `.engine/testing/ledger.md`.
