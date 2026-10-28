# 728 — Брак тесту (overseer): A respond-level test: a topic whose first reply is a router ask (or a fact answer), then a choose on turn 3. It asserts that FIRST_REPLY_LINE is in the frame of the first facilitator reply. Or else, t

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: test-gap-a-respond-level-test-a-topic-whose-first-reply-is-a-router-a-a76cec0f

## Що сталося
Overseer прийняв юніт `-|310-router-leads-one-method|unit 1` (PASS, запит `20261028T045936Z-cd789a`) і знайшов брак тесту: _state adds the line only when the history has no model turn. On a topic that opened with an ask or an answer, the line never appears, so the person is never told the opinion can be asked. That is the task's variant A promise. Today's tests only try a choose on turn 1 with an empty history. Де: `tests/contract/router/test_rt_310_leads_one_method.py`. Вердикт — у ledger: `python3 .claude/hooks/journal.py show ledger`.

- Записано: 2026-10-28T06:25:52Z, overseer (overseer_verdict.py)
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Дописати перевірку «A respond-level test: a topic whose first reply is a router ask (or a fact answer), then a choose on turn 3. It asserts that FIRST_REPLY_LINE is in the frame of the first facilitator reply. Or else, that the person is told somewhere that the system's opinion can be asked any time.»: тест червоніє на тому, що описано вище (_state adds the line only when the history has no model turn. On a topic that opened with an ask or an answer, the line never appears, so the person is never told the opinion can be asked. That is the task's variant A promise. Today's tests only try a choose on turn 1 with an empty history.), і зелений на коді, як він є (покажи обидва прогони); код не міняти, якщо тест не знайде справжньої вади; швидкий набір тестів зелений.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника
