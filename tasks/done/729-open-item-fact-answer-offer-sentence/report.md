# Звіт задачі 729 — речення роутера про offer у запечатаному контракті fact-answer

## Що змінилось для власника
- **Обидві відповіді виконано.** У правилах роутера більше немає дії `offer`, якої вже не існує: речення тепер
  каже «… — не "answer", а "choose" чи "ask".».
- **Відповідь A на питання 1** — commit `78f2ac3`. Те саме речення змінено в п'яти місцях: рядок 52 контракту
  `.engine/slices/fact-answer.md`, `src/thinkhow/facilitation/router.md`, `fa_fakes.ROUTER_ANSWER_ITEM`
  (`tests/contract/fact_answer/fa_fakes.py`), oracle `tests/contract/spoken_replies/sr_oracle.py` і тест
  `tests/contract/router/test_rt_310_leads_one_method.py`, який тепер перевіряє, що слова "offer" у правилах роутера
  немає зовсім.
- **Відповідь A на питання 2** (новий seal контракту) — Сонько виконав команду до вашої відповіді. Я перевірив у цій
  сесії: `python3 .claude/hooks/contract_fingerprint.py check .engine/slices/fact-answer.md` →
  `Match: fact-answer.md is the approved contract (02057604734e…)`, код 0. Тож overseer знову прийматиме роботу з
  fact-answer.

## Демонстрація на хвилину
- `grep -c offer src/thinkhow/facilitation/router.md` → `0`.
- `sed -n 52p .engine/slices/fact-answer.md` → `… Якщо за питанням стоїть рішення, яке треба продумати, — не "answer", а "choose" чи "ask".`
- `uv run pytest -q tests/contract/fact_answer tests/contract/research_deep tests/contract/router tests/contract/spoken_replies`
  → `136 passed in 4.08s`. Цей прогін — з цієї сесії.
- Повний набір тестів я в цій сесії не запускав. Після commit-а `78f2ac3` код і тести змінились лише в `3257b38`
  (задача 724). Повний прогін на `3257b38` дав `1525 passed` (`tasks/done/724-open-item-testing-parked-skel-facilitation/report.md`).
  Відтоді в `src/` і `tests/` змін немає: `git log 3257b38..HEAD -- src tests` порожній.

## Витрати
Сесії runner-а: одна для відповіді A на питання 1, ця — для закриття задачі. Плюс reader для цього звіту.
Додаткових сесій (evals, tester) не було.

## Commit-и
`da8973f` (у `doing/`) → `78f2ac3` (відповідь A) → `0f32759` (питання 2, `blocked/`) → `1da4cdb` (знову в `doing/`)
→ commit закриття.

## Відкладене
- Рядок 126 запечатаного контракту `.engine/slices/research-deep.md` і далі цитує старе речення («…не "answer", а
  "offer" чи "ask".»). Там воно лише позначає місце вставки тексту, і тести від нього не залежать. Я його не змінював:
  інакше довелося б заново запечатувати й цей контракт, а користі з того немає.

## Рішення, які я ухвалив сам
- Новий повний прогін тестів не запускав: код після останнього повного зеленого прогону не змінювався (див. вище).
- Рядок 126 контракту research-deep лишив як є — причина в «Відкладене».
