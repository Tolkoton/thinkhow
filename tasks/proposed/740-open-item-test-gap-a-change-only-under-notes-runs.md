# 740 — Брак тесту (overseer): a change only under notes/ runs `run jobs execute thinkhow-learning --args=-m,thinkhow.learning.job,notes` between the Job update and the service update, and does not run cards

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: test-gap-a-change-only-under-notes-runs-run-jobs-execute-thinkhow-lea-cd33305d

## Що сталося
Overseer прийняв юніт `-|601-auto-deploy-after-done|unit 1` (PASS, запит `20261104T203040Z-b97f67`) і знайшов брак тесту: a KNOWLEDGE_PATHS bug that maps notes/ to the cards command, or never runs notes, still passes: only cards is tested on its own Де: `tests/test_auto_deploy.py`. Вердикт — у ledger: `python3 .claude/hooks/journal.py show ledger`.

- Записано: 2026-11-04T20:32:03Z, overseer (overseer_verdict.py)
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Дописати перевірку «a change only under notes/ runs `run jobs execute thinkhow-learning --args=-m,thinkhow.learning.job,notes` between the Job update and the service update, and does not run cards»: тест червоніє на тому, що описано вище (a KNOWLEDGE_PATHS bug that maps notes/ to the cards command, or never runs notes, still passes: only cards is tested on its own), і зелений на коді, як він є (покажи обидва прогони); код не міняти, якщо тест не знайде справжньої вади; швидкий набір тестів зелений.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника
