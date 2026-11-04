# 739 — Брак тесту (overseer): test_no_deploy_while_a_task_with_uncommitted_code_is_in_doing sets the service to an older commit, so a build does happen, and asserts the build context holds the → done commit's src/app.py, not the u

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: test-gap-test-no-deploy-while-a-task-with-uncommitted-code-is-in-doin-d580a712

## Що сталося
Overseer прийняв юніт `-|601-auto-deploy-after-done|unit 1` (PASS, запит `20261104T203040Z-b97f67`) і знайшов брак тесту: with running=done[:7] the test returns 'up to date' before any build, so an implementation that built from the working tree would still pass this test (only test_deploys_the_snapshot_of_the_done_commit_not_the_working_tree catches it) Де: `tests/test_auto_deploy.py`. Вердикт — у ledger: `python3 .claude/hooks/journal.py show ledger`.

- Записано: 2026-11-04T20:32:03Z, overseer (overseer_verdict.py)
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Дописати перевірку «test_no_deploy_while_a_task_with_uncommitted_code_is_in_doing sets the service to an older commit, so a build does happen, and asserts the build context holds the → done commit's src/app.py, not the uncommitted v3»: тест червоніє на тому, що описано вище (with running=done[:7] the test returns 'up to date' before any build, so an implementation that built from the working tree would still pass this test (only test_deploys_the_snapshot_of_the_done_commit_not_the_working_tree catches it)), і зелений на коді, як він є (покажи обидва прогони); код не міняти, якщо тест не знайде справжньої вади; швидкий набір тестів зелений.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника
