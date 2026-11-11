# 751 — Stop gate fails a live-only test file

Залежить від: —
Аудит потрібен: ні

## Що сталося
gate.py --layer stop runs pytest on a changed test file; tests/contract/skel_learning/test_skell_live.py holds only a live test, deselected by addopts in pyproject.toml, so pytest exits 5 (`1 deselected`) and the gate reports TESTS FAILED (task 735, 2026-11-11).

- Записано: 2026-11-11T19:38:18Z, агент
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Engine: treat pytest exit 5 (no tests collected, all deselected) as no tests for that file rather than a failure; send via .engine/to-engine/.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника
