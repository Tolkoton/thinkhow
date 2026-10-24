# 713 — Брак тесту (overseer): A --switch conversation where, after «Давай інакше», the router ends the card not_fit and then `choose`s another card that never reaches `end`. The index row must say end — так (the end of the card sw

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: test-gap-a-switch-conversation-where-after-the-router-ends-the-card-n-b2fa9edc

## Що сталося
Overseer прийняв юніт `router-eval|302-thinking-models-library-and-router|unit 3` (PASS, запит `20261024T185333Z-f91702`) і знайшов брак тесту: scripts/card_conversations.py:338 looks for the end of c.led, which is the LAST choose. In the live run 181933Z that is reversible-doors, not weighted-matrix. The row's «end — так, нове offer — так» comes from reversible-doors' end: done and the closing offer, so it is right only by coincidence. A switch followed by an unfinished second card would report «end — ні». The sealed test (ledger Q5) asserts only the routing, not the row. Де: `tests/contract/router_eval/test_rev_conversations.py`. Вердикт — у ledger: `python3 .claude/hooks/journal.py show ledger`.

- Записано: 2026-10-24T18:58:00Z, overseer (overseer_verdict.py)
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Дописати перевірку «A --switch conversation where, after «Давай інакше», the router ends the card not_fit and then `choose`s another card that never reaches `end`. The index row must say end — так (the end of the card switched FROM) and judge the new offer against that card.»: тест червоніє на тому, що описано вище (scripts/card_conversations.py:338 looks for the end of c.led, which is the LAST choose. In the live run 181933Z that is reversible-doors, not weighted-matrix. The row's «end — так, нове offer — так» comes from reversible-doors' end: done and the closing offer, so it is right only by coincidence. A switch followed by an unfinished second card would report «end — ні». The sealed test (ledger Q5) asserts only the routing, not the row.), і зелений на коді, як він є (покажи обидва прогони); код не міняти, якщо тест не знайде справжньої вади; швидкий набір тестів зелений.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника
