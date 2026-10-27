# 704 — Facilitation schema: always an enum for a one-phase card

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: s3-one-phase-const

## Що сталося
pydantic writes 'const' instead of 'enum' for a one-value Literal. skel-learning forces 'enum' for its anchor (src/thinkhow/learning/analyze.py, _enum_of); facilitation.respond.answer_schema does not, so a card with one phase would send Vertex an unverified 'const'. Not reachable now: the only card has 4 phases.

- Записано: 2026-10-22T19:08:39Z, агент
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Apply the same _enum_of fix to current_phase_id in src/thinkhow/facilitation/respond.py (answer_schema, update_schema) with a test for a one-phase card; F7 (more cards) is the trigger.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника
