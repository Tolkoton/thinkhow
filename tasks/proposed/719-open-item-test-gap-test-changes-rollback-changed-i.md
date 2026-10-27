# 719 — Брак тесту (overseer): test_changes_rollback_changed_is_empty_for_a_revision_never_rolled_back asserts ChangeView.rollback_changed == [] and rolled_back is None for a memory revision that has no rollback

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: test-gap-test-changes-rollback-changed-is-empty-for-a-revision-never-03a33291

## Що сталося
Overseer прийняв юніт `knowledge-versions|309-close-learning-loop|unit 1` (PASS, запит `20261027T171600Z-d54d4b`) і знайшов брак тесту: a changes() that fills rollback_changed from the wrong rollback, or from any rollback acting on the same id, for a revision that was never rolled back. Today's tests leave this value unasserted (reading Q5), and S3's change feed will show it Де: `tests/contract/knowledge_versions/test_kv_changes.py`. Вердикт — у ledger: `python3 .claude/hooks/journal.py show ledger`.

- Записано: 2026-10-27T17:18:57Z, overseer (overseer_verdict.py)
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Дописати перевірку «test_changes_rollback_changed_is_empty_for_a_revision_never_rolled_back asserts ChangeView.rollback_changed == [] and rolled_back is None for a memory revision that has no rollback»: тест червоніє на тому, що описано вище (a changes() that fills rollback_changed from the wrong rollback, or from any rollback acting on the same id, for a revision that was never rolled back. Today's tests leave this value unasserted (reading Q5), and S3's change feed will show it), і зелений на коді, як він є (покажи обидва прогони); код не міняти, якщо тест не знайде справжньої вади; швидкий набір тестів зелений.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника
