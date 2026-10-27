# 723 — Брак тесту (overseer): smoke step 'a second synthesize ran' should assert that the second run's report.outcome is 'nothing_new' (or that it made zero model calls)

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: test-gap-smoke-step-a-second-synthesize-ran-should-assert-that-the-se-0540ac15

## Що сталося
Overseer повернув юніт `synthesizer|309-close-learning-loop|unit 3` (BLOCK, запит `20261027T190958Z-cebaac`) і назвав ще й брак тесту: runs(storage)[-1].considered != [] is already true from the FIRST run's record. A second synthesize that crashed silently, or that re-fed the old observations and was refused, still passes this line. Де: `scripts/smoke_test_learning_loop.py`. Вердикт — у ledger: `python3 .claude/hooks/journal.py show ledger`.

- Записано: 2026-10-27T19:51:20Z, overseer (overseer_verdict.py)
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Дописати перевірку «smoke step 'a second synthesize ran' should assert that the second run's report.outcome is 'nothing_new' (or that it made zero model calls)»: тест червоніє на тому, що описано вище (runs(storage)[-1].considered != [] is already true from the FIRST run's record. A second synthesize that crashed silently, or that re-fed the old observations and was refused, still passes this line.), і зелений на коді, як він є (покажи обидва прогони); код не міняти, якщо тест не знайде справжньої вади; швидкий набір тестів зелений.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника
