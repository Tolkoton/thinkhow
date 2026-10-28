# 727 — Брак тесту (overseer): the smoke's 'no question about it again' step asserts that the page has no .step-question section, not only that the text is missing after the «Кроки» heading

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: test-gap-the-smoke-s-no-question-about-it-again-step-asserts-that-the-f91634a3

## Що сталося
Overseer повернув юніт `step-results|309-close-learning-loop|unit 6` (BLOCK, запит `20261028T002152Z-d47deb`) і назвав ще й брак тесту: a template that put the question line before the «Кроки» block would still pass, because the check only looks at the text after 'Кроки' Де: `scripts/smoke_test_learning_loop.py`. Вердикт — у ledger: `python3 .claude/hooks/journal.py show ledger`.

- Записано: 2026-10-28T00:24:54Z, overseer (overseer_verdict.py)
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Дописати перевірку «the smoke's 'no question about it again' step asserts that the page has no .step-question section, not only that the text is missing after the «Кроки» heading»: тест червоніє на тому, що описано вище (a template that put the question line before the «Кроки» block would still pass, because the check only looks at the text after 'Кроки'), і зелений на коді, як він є (покажи обидва прогони); код не міняти, якщо тест не знайде справжньої вади; швидкий набір тестів зелений.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника
