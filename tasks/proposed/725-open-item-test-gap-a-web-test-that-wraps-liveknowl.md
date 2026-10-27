# 725 — Брак тесту (overseer): a web test that wraps LiveKnowledge, runs one full facilitate reply (router + facilitator) and asserts knowledge.latest_pair was called exactly once (or a fixed small number), whatever the number of n

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: test-gap-a-web-test-that-wraps-liveknowledge-runs-one-full-facilitate-8194e8d6

## Що сталося
Overseer повернув юніт `notes-readers|309-close-learning-loop|unit 4` (BLOCK, запит `20261027T214157Z-023d21`) і назвав ще й брак тесту: a per-attribute refresh doing O(notes) storage listings per reply passes tests/web/test_live_knowledge.py today Де: `tests/web/test_live_knowledge.py`. Вердикт — у ledger: `python3 .claude/hooks/journal.py show ledger`.

- Записано: 2026-10-27T21:45:08Z, overseer (overseer_verdict.py)
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Дописати перевірку «a web test that wraps LiveKnowledge, runs one full facilitate reply (router + facilitator) and asserts knowledge.latest_pair was called exactly once (or a fixed small number), whatever the number of notes»: тест червоніє на тому, що описано вище (a per-attribute refresh doing O(notes) storage listings per reply passes tests/web/test_live_knowledge.py today), і зелений на коді, як він є (покажи обидва прогони); код не міняти, якщо тест не знайде справжньої вади; швидкий набір тестів зелений.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника
