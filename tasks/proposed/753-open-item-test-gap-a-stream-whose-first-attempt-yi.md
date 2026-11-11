# 753 — Брак тесту (overseer): a stream whose first attempt yields a chunk and then fails before any reply text is shown, and whose retry answers after think_s, logs first_chunk_ms from the retry, not from the first attempt

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: test-gap-a-stream-whose-first-attempt-yields-a-chunk-and-then-fails-b-aa94610c

## Що сталося
Overseer прийняв юніт `-|744-open-item-hung-stream-and-search-limits|unit 1` (PASS, запит `20261111T202228Z-1b7961`) і знайшов брак тесту: dropping the per-attempt reset `call.first_chunk_ms = None` still passes test_the_time_to_the_first_chunk_is_that_of_the_attempt_that_answered: in that test the hung attempt never produces a chunk, so no stale value is ever recorded Де: `tests/platform/test_llm_call_kind.py`. Вердикт — у ledger: `python3 .claude/hooks/journal.py show ledger`.

- Записано: 2026-11-11T20:23:20Z, overseer (overseer_verdict.py)
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Дописати перевірку «a stream whose first attempt yields a chunk and then fails before any reply text is shown, and whose retry answers after think_s, logs first_chunk_ms from the retry, not from the first attempt»: тест червоніє на тому, що описано вище (dropping the per-attempt reset `call.first_chunk_ms = None` still passes test_the_time_to_the_first_chunk_is_that_of_the_attempt_that_answered: in that test the hung attempt never produces a chunk, so no stale value is ever recorded), і зелений на коді, як він є (покажи обидва прогони); код не міняти, якщо тест не знайде справжньої вади; швидкий набір тестів зелений.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника
