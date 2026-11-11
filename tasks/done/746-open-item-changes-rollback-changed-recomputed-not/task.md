# 746 — Change feed: rollback_changed is recomputed from today's state, not read from the rollback's stored changed

Залежить від: —
Потрібна присутність власника: ні
Режим: соло
Аудит потрібен: так
Додаткові сесії: ні
Відкритий пункт: changes-rollback-changed-recomputed-not-stored

## Рішення власника
Слова власника (2026-11-11, сесія Thinkhow; записано Claude зі слів власника) — на пояснення Claude, що сторінка
«Навчання» після пізнішої зміни тієї самої нотатки показує старий відкат як «відкочено — нічого не змінено»:
«746-й бери».

## Що сталося
Found in task 719. changes() (src/thinkhow/knowledge/versions.py:233) fills ChangeView.rollback_changed by replaying all rollbacks over the latest memory, not from Rollback.changed saved in knowledge/rollbacks/<n>.json. A rollback that reverted m1 shows rollback_changed=['m1'] until a later revision changes m1; after that the feed shows [] and the page says «відкочено — нічого не змінено», although the stored file still says changed=['m1']. Probe: rev 2 m1 v1, rev 3 m1 v2, rollback rev 3 (n=1) -> feed (3, 1, ['m1']); then rev 4 m1 v3 -> feed (3, 1, []), stored changed ['m1']. learning/synthesize.py:141 also drops such a rollback from what it tells the learner. The slice contract .engine/slices/knowledge-versions.md defines Rollback.changed («в мить запису») but not ChangeView.rollback_changed, so this may be intended.

- Записано: 2026-11-10T10:57:00Z, агент
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Decide what rollback_changed means (what the rollback changed when it was made, or what it still holds now). If the former: take it from the stored Rollback.changed, with a test where a later revision changes the reverted id; if the latter: write it into the slice contract and change the page text, which now reads «нічого не змінено» for that case. Advice: the stored value — the owner reads the feed as history.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника
