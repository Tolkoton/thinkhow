# 730 — Брак тесту (overseer): with THINKHOW_LOCAL=true and no THINKHOW_IAP_AUDIENCE, reading app.app goes on to build_deps (stub records the call) without raising ConfigError

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: test-gap-with-thinkhow-local-true-and-no-thinkhow-iap-audience-readin-02f31d5c

## Що сталося
Overseer прийняв юніт `-|705-open-item-iap-audience-required|unit 1` (PASS, запит `20261028T090729Z-32ceb8`) і знайшов брак тесту: refuse_web_without_iap_audience with the `not settings.local` guard dropped would refuse local mode at the entry point. Every current test sets cloud env, so all of them still pass Де: `tests/web/test_iap_audience_required.py`. Вердикт — у ledger: `python3 .claude/hooks/journal.py show ledger`.

- Записано: 2026-10-28T09:08:34Z, overseer (overseer_verdict.py)
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Дописати перевірку «with THINKHOW_LOCAL=true and no THINKHOW_IAP_AUDIENCE, reading app.app goes on to build_deps (stub records the call) without raising ConfigError»: тест червоніє на тому, що описано вище (refuse_web_without_iap_audience with the `not settings.local` guard dropped would refuse local mode at the entry point. Every current test sets cloud env, so all of them still pass), і зелений на коді, як він є (покажи обидва прогони); код не міняти, якщо тест не знайде справжньої вади; швидкий набір тестів зелений.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника
