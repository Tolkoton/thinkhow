# 726 — Брак тесту (overseer): a test where a memory change is published between two field reads inside one reply, asserting that the routing decision's rev and the memory in the instruction come from the same revision

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: test-gap-a-test-where-a-memory-change-is-published-between-two-field-53b1082c

## Що сталося
Overseer повернув юніт `notes-readers|309-close-learning-loop|unit 4` (BLOCK, запит `20261027T214157Z-023d21`) і назвав ще й брак тесту: rev_pair read from revision N while memory is read from revision N+1 passes every current test Де: `tests/web/test_live_knowledge.py`. Вердикт — у ledger: `python3 .claude/hooks/journal.py show ledger`.

- Записано: 2026-10-27T21:45:08Z, overseer (overseer_verdict.py)
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Дописати перевірку «a test where a memory change is published between two field reads inside one reply, asserting that the routing decision's rev and the memory in the instruction come from the same revision»: тест червоніє на тому, що описано вище (rev_pair read from revision N while memory is read from revision N+1 passes every current test), і зелений на коді, як він є (покажи обидва прогони); код не міняти, якщо тест не знайде справжньої вади; швидкий набір тестів зелений.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника
