# 750 — Two smoke scripts keep the type-check red

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: scripts-mypy-red

## Що сталося
On cf4adde 'uv run mypy src tests scripts' prints «Found 12 errors in 4 files». Two of the four files are not covered by tasks 733 and 735: scripts/smoke_test_voice_language.py:51-52 (variable 'chosen' first holds an httpx Response, then a str — task 208) and scripts/smoke_test_product_cards.py:75,81,96 (patches thinkhow.platform.llm.log_event, which the module does not export explicitly, and the stand-in has another signature — task 307). The runner's update-deps for task 419 refused to start because gate[ci] was red before any update (.engine/maintain/update-result.md); with 733 and 735 done these two files would still keep it red.

- Записано: 2026-11-11T18:37:42Z, агент
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Rename the second 'chosen' in smoke_test_voice_language.py (e.g. 'greeting'); in smoke_test_product_cards.py patch log_event where it is defined or explicitly re-exported and give 'recording' the same signature. Neither file is a sealed test. Then 'uv run mypy src tests scripts' shows only what 733/735 still own; run both smokes if their keys are present, else say so.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника
