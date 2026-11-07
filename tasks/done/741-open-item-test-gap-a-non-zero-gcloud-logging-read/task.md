# 741 — Брак тесту (overseer): a non-zero `gcloud logging read` produces 'failed <sha>: logging', a notify call and a journal line, and makes no build call

Залежить від: —
Потрібна присутність власника: ні
Режим: соло
Аудит потрібен: так
Додаткові сесії: ні
Відкритий пункт: test-gap-a-non-zero-gcloud-logging-read-produces-failed-sha-logging-a-439f82ad

## Рішення власника
Слова власника (2026-11-06, сесія Thinkhow; записано Claude зі слів власника) — на питання Claude «Ставити в роботу
пункти 1–4 (тести автоматичного розгортання, хибне «FAIL» після повного прогону, спрощення `_answer`, перевірка
застарілих залежностей)?»: «Бери все». Пункт 1 — пропозиції 738–741, пункт 2 — пропозиція 737.

## Що сталося
Overseer прийняв юніт `-|601-auto-deploy-after-done|unit 1` (PASS, запит `20261104T203040Z-b97f67`) і знайшов брак тесту: an implementation that treats a failed logging read as 'nobody writes' and deploys anyway (deploying while a user may be writing) passes every current test Де: `tests/test_auto_deploy.py`. Вердикт — у ledger: `python3 .claude/hooks/journal.py show ledger`.

- Записано: 2026-11-04T20:32:03Z, overseer (overseer_verdict.py)
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Дописати перевірку «a non-zero `gcloud logging read` produces 'failed <sha>: logging', a notify call and a journal line, and makes no build call»: тест червоніє на тому, що описано вище (an implementation that treats a failed logging read as 'nobody writes' and deploys anyway (deploying while a user may be writing) passes every current test), і зелений на коді, як він є (покажи обидва прогони); код не міняти, якщо тест не знайде справжньої вади; швидкий набір тестів зелений.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника
