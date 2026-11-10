# Звіт: стрічка змін не приписує відкату ревізії, яку ніхто не відкочував, — тепер це перевірено тестом

## Що змінилось для власника
Код не змінився, додано лише тест:
`tests/contract/knowledge_versions/test_kv_gap_changes_never_rolled_back.py`, у ньому
`test_changes_rollback_changed_is_empty_for_a_revision_never_rolled_back`. Сценарій такий: rev `before` записує `m1` і `m2`
(v1), rev `rolled` змінює обидва на v2, відкат `rolled` (n = 1) повертає їх до v1, після нього rev `after` змінює `m1`
на v3. Тест вимагає:
- для `before` і `after` у `changes()`: `rolled_back is None` і `rollback_changed == []`. Обидві ревізії міняли ті самі id,
  що й відкочена;
- для `rolled`: `rolled_back == 1` і `rollback_changed` непорожній. Це умова, без якої тест нічого б не ловив: відкат справді
  щось змінив, тож у нього є що «витекти» в чужу ревізію.

Справжньої вади тест не знайшов: на коді як він є він зелений.

Окремо знайшов річ поза цим браком і записав її як пропозицію
`tasks/proposed/746-open-item-changes-rollback-changed-recomputed-not.md`. `changes()` не бере `rollback_changed` зі
збереженого `Rollback.changed`, а щоразу обчислює його заново з нинішнього стану. Тому коли пізніша ревізія змінює id,
який відкат повернув, стрічка показує цей відкат як «відкочено — нічого не змінено». У файлі відкату при цьому й далі
записано `changed: ['m1']`. Перевірка: rev 2 `m1` v1, rev 3 `m1` v2, відкат rev 3 → у стрічці `(3, 1, ['m1'])`. Після
rev 4 `m1` v3 там уже `(3, 1, [])`, а збережене `changed` — `['m1']`. Контракт slice-а не каже, що має означати
`ChangeView.rollback_changed`, тож це може бути задумано. Через це новий тест не фіксує точного вмісту
`rollback_changed` відкоченої ревізії, лише те, що він непорожній.

## Демонстрація на хвилину
Червоні прогони. `src/thinkhow/knowledge/versions.py` тричі тимчасово ламав, після кожного зламу відновлював із копії
(`diff` з копією наприкінці порожній). Щоразу запускав новий тест, а також sealed
`test_kv_changes.py` разом із `test_kv_rollback.py`:

1. Ревізія без відкату бере `changed` чужого відкату: у `_view` замість `if rb else []` стоїть
   `if rb else next(iter(acted.values()), [])`.
   Новий тест: `AssertionError: assert (None, ['m2']) == (None, [])`, `1 failed`. Sealed: `20 passed`.
2. Ревізія без відкату бере id, на які діяв будь-який відкат, якщо вона сама їх міняла:
   `if rb else sorted({i for ids in acted.values() for i in ids if i in record.replaced})`.
   Новий тест: `AssertionError: assert (None, ['m2']) == (None, [])`, `1 failed`. Sealed: `20 passed`.
3. `rolled_back` береться від першого відкату будь-якої ревізії: `first.get(rev) or next(iter(first.values()), None)`.
   Новий тест: `AssertionError: assert (1, ['m2']) == (None, [])`, `1 failed`. Sealed: `1 failed, 19 passed`.

Зламів 1 і 2 (саме тих, які назвав overseer) без нового тесту не ловить жоден тест slice-а.

Зелений прогін на коді як він є:
```
uv run pytest -q tests/contract/knowledge_versions/test_kv_gap_changes_never_rolled_back.py  → 1 passed
uv run pytest -q tests/contract/knowledge_versions/                                          → 56 passed in 6.84s
```
`uv run ruff check` → `All checks passed!`; `uv run ruff format --check` → `1 file already formatted`;
`uv run mypy` на новому файлі → `Success: no issues found in 1 source file`.

Повний набір: `uv run pytest -q -p no:cacheprovider` → `1636 passed, 36 deselected in 1257.37s` (1635 у задачі 717 плюс новий тест). Прогін видалив
закомічений `.engine/artifacts/conversation-resilience/smoke.txt`; я повернув його `git checkout --`, тож у commit-і
його немає (див. «Відкладене»).

## Витрати
Одна сесія runner-а. Додаткових сесій Claude не було.

## Діапазон commit-ів
Від `cd66df9` (задача в `doing/`) до commit-а, що переносить задачу в `done/`.

## Відкладене
- Повний набір видаляє `.engine/artifacts/conversation-resilience/smoke.txt` (у задачі 717 після прогону дерево
  лишилось чистим; що цього разу видалило файл, не з'ясовував, бо це не ця задача).
- Що означає `rollback_changed` після пізнішої зміни того самого id, вирішує пропозиція 746 (вище). Це не ця задача.

## Рішення, які я ухвалив сам
- Тест лежить в окремому файлі, а не в `test_kv_changes.py`. Той файл sealed для slice-а `knowledge-versions`, а
  builder не редагує файлів tester-а. Так само зроблено в задачах 713 і 717.
- Тест не вимагає точного списку `rollback_changed` відкоченої ревізії, лише непорожнього. Точне значення залежить від
  питання з пропозиції 746: перша версія тесту вимагала `['m1', 'm2']` і впала на `['m2']`.
- Злам 3 зачіпає `rolled_back`, а не `rollback_changed`. Додав його, щоб показати, що умова `rolled_back is None` у
  тесті теж працює; sealed тест його вже ловить.
