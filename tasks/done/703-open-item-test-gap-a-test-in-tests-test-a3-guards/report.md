# Звіт — 703: брак тесту, guard A3 не бачив bucket-а, складеного виразом

## Що змінилось для власника
- Overseer при PASS юніта 7 `skel-guards-deploy` (запит `20261022T190553Z-acac2d`) знайшов брак тесту: guard
  `unnamed_buckets` у `tests/test_a3_guards.py` не помічав виклику Storage, у якого bucket — subscript, виклик функції
  чи f-string. Новий тест `test_a_bucket_built_by_an_expression_is_unnamed` (`tests/test_a3_guards.py:120`) показав, що
  це справжня вада: на старому guard-і всі такі виклики проходили. Тож guard я виправив — це тестовий код, робочий код
  у `src/` не змінено.
- Тепер guard дотримується строгого правила slice contract-у дослівно (`.engine/slices/skel-guards-deploy.md:40`:
  «кожен виклик цих методів поза `platform/` мусить мати **рядкову константу** першим позиційним аргументом»):
  `_looks_like_bucket` (`tests/test_a3_guards.py:145`) вважає змінним bucket-ом будь-що, крім constant.
  Раніше — лише name або attribute.
- Обидва guard-и A3 (`test_users_paths_are_built_only_by_workspace`, `test_knowledge_files_are_written_only_by_knowledge`)
  на `src/thinkhow/` зелені й з новим правилом: у коді немає жодного такого виклику.

## Демонстрація на хвилину
- Червоний прогін — новий тест разом зі старим guard-ом (файл з commit-у `fbae098`, тимчасова копія, після прогону
  видалена): `1 failed, 3 passed`, `AssertionError: self.buckets['users']`, `assert [] == [2]`. Окремо на старому
  guard-і кожен із трьох випадків задачі — `self.buckets['users']`, `bucket_for(k)`, `f'us{k}'` — дав `[]`.
- Зелений прогін на виправленому guard-і: `uv run pytest -q tests/test_a3_guards.py` → `4 passed`.
- Перед тим як розширити правило до «будь-що, крім constant», я перевірив `src/thinkhow/` поза `platform/`: жодного
  виклику `read|write|create_if_absent|list`, у якого перший аргумент не constant і не name/attribute, — `[]`.
- `uv run ruff check tests/test_a3_guards.py` → `All checks passed!`; `uv run ruff format --check` → `1 file already formatted`.
- Повний набір: `uv run pytest -q -p no:cacheprovider` → `25 failed, 1460 passed, 36 deselected`
  (запущено до останньої правки guard-а; після неї `tests/test_a3_guards.py` прогнано окремо — `4 passed`). Нових
  червоних немає: 25 failed — ті самі, що записано в `tasks/blocked/308-voice-conversation-mode.md` (рядки 61–62: «1446 passed,
  25 failed»). У моєму прогоні вони розподілені так: `skel_learning` 19, `walking_skeleton_block` 2, `skel_facilitation` 2, `voice_synthesis/test_vs_web.py` 1,
  `voice_conversation_mode_block/test_vcm_block_disputed_q1_q2.py` 1 — sealed tests, які чекають ваших відповідей у
  `blocked/`. Серед них немає жодного з `tests/test_a3_guards.py`.

## Витрати
Лише ця сесія; додаткових сесій Claude не запускав.

## Діапазон commit-ів
`fbae098` (задача → doing) … `63221b8` (перший варіант виправлення) … `78a7f28` (виправлення моєї помилки, нижче) …
`08547f5` (тест і guard «будь-що, крім constant») … commit, яким задачу перенесено в `done/`.

## Відкладене
Нічого.

## Рішення, які я ухвалив сам
- Задача каже «код не міняти, якщо тест не знайде справжньої вади». Тест її знайшов — і вада саме в guard-і, тому
  я виправив `_looks_like_bucket`, а не `src/`.
- Правило розширив ширше за три випадки задачі — до всього, що не constant: так написано в slice contract-і, а
  перелік типів AST лишав би дірки (`'us' + 'ers'`, `'users' if k else 'system'`). Ці два випадки теж додав у тест.
  Виклик без жодного аргументу guard, як і раніше, не позначає.
- Моя помилка й її виправлення: перший commit (`63221b8`) я зробив через `commit_checkpoint.sh` без `--staged`, і
  скрипт виконав `git add -u`. Так у commit потрапили два чужі файли: ваша незакомічена зміна
  `.claude/unattended/board-runner.sh` і видалений тестами `.engine/artifacts/conversation-resilience/smoke.txt`.
  Історію я не переписував. Натомість commit `78a7f28` повертає обидва файли в git до попереднього стану. Робоче дерево
  не зачеплене: ваша зміна в `board-runner.sh` лишилася незакоміченою, як і була.
