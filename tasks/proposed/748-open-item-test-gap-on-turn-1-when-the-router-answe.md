# 748 — Брак тесту (overseer): On turn 1, when the router answers choose, the router's call and the facilitator's call each carry FIRST_REPLY_LINE exactly once, and only the facilitator's reply is shown to the person

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: test-gap-on-turn-1-when-the-router-answers-choose-the-router-s-call-a-eb630878

## Що сталося
Overseer прийняв юніт `-|728-open-item-test-gap-a-respond-level-test-a-topic-wh|unit 1` (PASS, запит `20261110T145601Z-f1a80f`) і знайшов брак тесту: A route._contents that also adds the line on a choose, while the facilitator's frame carries it a second time (or a state that doubles it), passes every test in the new file, because they try only ask and answer on turn 1 Де: `tests/contract/router/test_rt_gap_first_reply_of_an_ask_or_answer.py`. Вердикт — у ledger: `python3 .claude/hooks/journal.py show ledger`.

- Записано: 2026-11-10T14:57:51Z, overseer (overseer_verdict.py)
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Дописати перевірку «On turn 1, when the router answers choose, the router's call and the facilitator's call each carry FIRST_REPLY_LINE exactly once, and only the facilitator's reply is shown to the person»: тест червоніє на тому, що описано вище (A route._contents that also adds the line on a choose, while the facilitator's frame carries it a second time (or a state that doubles it), passes every test in the new file, because they try only ask and answer on turn 1), і зелений на коді, як він є (покажи обидва прогони); код не міняти, якщо тест не знайде справжньої вади; швидкий набір тестів зелений.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника
