# 703 — Брак тесту (overseer): a test in tests/test_a3_guards.py asserting unnamed_buckets flags a call whose first argument is a subscript, a call or an f-string, e.g. `storage.write(self.buckets['users'], 'u/x', b'', 't')` and `s

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: test-gap-a-test-in-tests-test-a3-guards-py-asserting-unnamed-buckets-f51afbfa

## Що сталося
Overseer прийняв юніт `skel-guards-deploy|105-walking-skeleton|unit 7` (PASS, запит `20261022T190553Z-acac2d`) і знайшов брак тесту: _looks_like_bucket accepts only ast.Name or ast.Attribute, so a non-constant bucket written as a subscript or a function call outside platform/ breaks the contract's strict rule ('every call … must have a string constant first argument') and both A3 guards still pass Де: `tests/test_a3_guards.py`. Вердикт — у ledger: `python3 .claude/hooks/journal.py show ledger`.

- Записано: 2026-10-22T19:08:01Z, overseer (overseer_verdict.py)
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Дописати перевірку «a test in tests/test_a3_guards.py asserting unnamed_buckets flags a call whose first argument is a subscript, a call or an f-string, e.g. `storage.write(self.buckets['users'], 'u/x', b'', 't')` and `storage.write(bucket_for(k), ...)` → [line]»: тест червоніє на тому, що описано вище (_looks_like_bucket accepts only ast.Name or ast.Attribute, so a non-constant bucket written as a subscript or a function call outside platform/ breaks the contract's strict rule ('every call … must have a string constant first argument') and both A3 guards still pass), і зелений на коді, як він є (покажи обидва прогони); код не міняти, якщо тест не знайде справжньої вади; швидкий набір тестів зелений.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника
