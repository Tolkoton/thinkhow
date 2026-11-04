# 741 — Брак тесту (overseer): a non-zero `gcloud logging read` produces 'failed <sha>: logging', a notify call and a journal line, and makes no build call

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: test-gap-a-non-zero-gcloud-logging-read-produces-failed-sha-logging-a-439f82ad

## Що сталося
Overseer прийняв юніт `-|601-auto-deploy-after-done|unit 1` (PASS, запит `20261104T203040Z-b97f67`) і знайшов брак тесту: an implementation that treats a failed logging read as 'nobody writes' and deploys anyway (deploying while a user may be writing) passes every current test Де: `tests/test_auto_deploy.py`. Вердикт — у ledger: `python3 .claude/hooks/journal.py show ledger`.

- Записано: 2026-11-04T20:32:03Z, overseer (overseer_verdict.py)
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Дописати перевірку «a non-zero `gcloud logging read` produces 'failed <sha>: logging', a notify call and a journal line, and makes no build call»: тест червоніє на тому, що описано вище (an implementation that treats a failed logging read as 'nobody writes' and deploys anyway (deploying while a user may be writing) passes every current test), і зелений на коді, як він є (покажи обидва прогони); код не міняти, якщо тест не знайде справжньої вади; швидкий набір тестів зелений.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника
