# 715 — Брак тесту (overseer): a contract test that a person asking «порадь / що б ти обрав» before any method is chosen gets advice rather than a refusal; at minimum, assert that router.md carries no blanket «Не давай порад» that

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: test-gap-a-contract-test-that-a-person-asking-before-any-method-is-ch-8165e024

## Що сталося
Overseer прийняв юніт `-|305-advice-on-request|unit 1` (PASS, запит `20261025T174711Z-8162d0`) і знайшов брак тесту: the router instruction still says «Не давай порад щодо самої проблеми» (router.md:34), so a request for advice at the routing stage is refused, and no test or live run tries that case Де: `tests/contract/advice_on_request/test_aor_rules.py`. Вердикт — у ledger: `python3 .claude/hooks/journal.py show ledger`.

- Записано: 2026-10-25T17:51:22Z, overseer (overseer_verdict.py)
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Дописати перевірку «a contract test that a person asking «порадь / що б ти обрав» before any method is chosen gets advice rather than a refusal; at minimum, assert that router.md carries no blanket «Не давай порад» that contradicts the rules.md advice rule»: тест червоніє на тому, що описано вище (the router instruction still says «Не давай порад щодо самої проблеми» (router.md:34), so a request for advice at the routing stage is refused, and no test or live run tries that case), і зелений на коді, як він є (покажи обидва прогони); код не міняти, якщо тест не знайде справжньої вади; швидкий набір тестів зелений.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника
