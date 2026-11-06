# 738 — Брак тесту (overseer): a test that renders a page (e.g. GET / via TestClient) and asserts every /static/ URL in it, including /static/rename.js, carries ?v= equal to the content hash, and that the hash changes when a file i

Залежить від: —
Потрібна присутність власника: ні
Режим: соло
Аудит потрібен: так
Додаткові сесії: ні
Відкритий пункт: test-gap-a-test-that-renders-a-page-e-g-get-via-testclient-and-assert-ed77468f

## Рішення власника
Слова власника (2026-11-06, сесія Thinkhow; записано Claude зі слів власника) — на питання Claude «Ставити в роботу
пункти 1–4 (тести автоматичного розгортання, хибне «FAIL» після повного прогону, спрощення `_answer`, перевірка
застарілих залежностей)?»: «Бери все». Пункт 1 — пропозиції 738–741, пункт 2 — пропозиція 737.

## Що сталося
Overseer прийняв юніт `-|210-paperclip-does-nothing|unit 1` (PASS, запит `20261104T114955Z-4006de`) і знайшов брак тесту: a version only on conversation.js and style.css (rename.js left unversioned and stale after a deploy), or a constant/commit-time version, passes today's test because it only checks the paperclip and --stale Де: `tests/web/test_static_cache.py`. Вердикт — у ledger: `python3 .claude/hooks/journal.py show ledger`.

- Записано: 2026-11-04T11:51:02Z, overseer (overseer_verdict.py)
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Дописати перевірку «a test that renders a page (e.g. GET / via TestClient) and asserts every /static/ URL in it, including /static/rename.js, carries ?v= equal to the content hash, and that the hash changes when a file in static/ changes»: тест червоніє на тому, що описано вище (a version only on conversation.js and style.css (rename.js left unversioned and stale after a deploy), or a constant/commit-time version, passes today's test because it only checks the paperclip and --stale), і зелений на коді, як він є (покажи обидва прогони); код не міняти, якщо тест не знайде справжньої вади; швидкий набір тестів зелений.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника
