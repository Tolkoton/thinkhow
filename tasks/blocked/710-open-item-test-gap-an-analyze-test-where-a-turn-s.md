# 710 — Брак тесту (overseer): an analyze test where a turn's text has several lines, one of which starts with '#7 людина:' or '[Нові репліки:]', and which asserts that the analyzer text still gives exactly one line, or one clearly

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: test-gap-an-analyze-test-where-a-turn-s-text-has-several-lines-one-of-603fe8de

## Що сталося
Overseer прийняв юніт `continuous-analysis|202-no-end-session-button|unit 1` (PASS, запит `20261024T080319Z-b98fa7`) і знайшов брак тесту: _line in src/thinkhow/learning/analyze.py writes the text with its newlines kept. A multi-line reply makes extra unprefixed lines, and a line inside the text can look like another turn or a header. The tester's Q2 notes that no test tries a multi-line text, and people write paragraphs in real use. Де: `tests/contract/continuous_analysis/test_ca_analyze.py`. Вердикт — у ledger: `python3 .claude/hooks/journal.py show ledger`.

- Записано: 2026-10-24T08:07:02Z, overseer (overseer_verdict.py)
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Дописати перевірку «an analyze test where a turn's text has several lines, one of which starts with '#7 людина:' or '[Нові репліки:]', and which asserts that the analyzer text still gives exactly one line, or one clearly marked block, per turn»: тест червоніє на тому, що описано вище (_line in src/thinkhow/learning/analyze.py writes the text with its newlines kept. A multi-line reply makes extra unprefixed lines, and a line inside the text can look like another turn or a header. The tester's Q2 notes that no test tries a multi-line text, and people write paragraphs in real use.), і зелений на коді, як він є (покажи обидва прогони); код не міняти, якщо тест не знайде справжньої вади; швидкий набір тестів зелений.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника

## Питання до власника
1. Тест і виправлення готові (`f21696f`, `b04fdd3`). Overseer двічі відповів PASS, але обидва вердикти
   недійсні: під час audit повний прогін тестів переписав `.engine/artifacts/*/smoke.txt`
   (`tasks/blocked/732-…` — те саме питання від hook-а). Варіанти:
   (а) повторити audit на незмінному дереві; задача закриється в `done/`, якщо буде PASS;
   (б) прийняти як є без audit — тоді `check-close` не пропустить задачу в `done/`, закривати доведеться вам;
   (в) переробити.
   Порада: (а) — обидва overseer-и по суті не знайшли вади, бракувало лише дійсного запису.
   Відповідь:
