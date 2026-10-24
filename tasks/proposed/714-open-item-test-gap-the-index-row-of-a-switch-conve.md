# 714 — Брак тесту (overseer): The index row of a --switch conversation that led the target first does not carry «обрано іншу картку (<id>)». The note should come from the first choose after the router's offer, not from the last on

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: test-gap-the-index-row-of-a-switch-conversation-that-led-the-target-f-bcbfb6fc

## Що сталося
Overseer прийняв юніт `router-eval|302-thinking-models-library-and-router|unit 3` (PASS, запит `20261024T185333Z-f91702`) і знайшов брак тесту: scripts/card_conversations.py:274 compares the last choose with the target. switch-weighted-matrix is marked «обрано іншу картку (reversible-doors)» although weighted-matrix was chosen and led first (phases phase_1_frame_options, phase_2_criteria). Де: `tests/contract/router_eval/test_rev_conversations.py`. Вердикт — у ledger: `python3 .claude/hooks/journal.py show ledger`.

- Записано: 2026-10-24T18:58:00Z, overseer (overseer_verdict.py)
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Дописати перевірку «The index row of a --switch conversation that led the target first does not carry «обрано іншу картку (<id>)». The note should come from the first choose after the router's offer, not from the last one.»: тест червоніє на тому, що описано вище (scripts/card_conversations.py:274 compares the last choose with the target. switch-weighted-matrix is marked «обрано іншу картку (reversible-doors)» although weighted-matrix was chosen and led first (phases phase_1_frame_options, phase_2_criteria).), і зелений на коді, як він є (покажи обидва прогони); код не міняти, якщо тест не знайде справжньої вади; швидкий набір тестів зелений.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника
