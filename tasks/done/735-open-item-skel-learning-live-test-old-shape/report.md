# 735 — Live-тест skel-learning досі читає старий вигляд спостереження: звіт

## Що змінилось для власника
- Для людини, що розмовляє з ThinkHow, не змінилось нічого: змінився лише тест, код у `src/` не чіпали.
- Live-тест skel-learning `tests/contract/skel_learning/test_skell_live.py` тепер читає `ObservationSet` і на живій
  моделі gemini-4-argon зелений: `1 passed` (до правки — `1 failed`, `ValidationError`).
- `uv run mypy src tests` уперше повністю чистий: `Success: no issues found in 438 source files`
  (після задачі 733 лишались 3 помилки, усі в цьому файлі).
- На ваше «так» skel-learning запечатано знову: live-тест і шість файлів, які змінила задача 720
  (їх названо в питанні картки). `testing.py status skel-learning` → `seal: match: 9 sealed test file(s)`.

## Що зроблено, по пунктах «Що зробити»
- **Перевірки по `ObservationSet`** — у файл покладено рівно `.engine/artifacts/735/test_skell_live.proposed.py`
  (правка — `.engine/artifacts/735/test_skell_live.diff`): файл `t1-t40.json`, `(first_turn, last_turn) == (1, 40)`
  на наборі, набір не порожній, у кожного спостереження `turn` у 1..40, `link` на `#t<turn>`, `finding` не порожній.
- **Objection-пакет** з «Що зробити» не знадобився: замість нього — ваша відповідь «так» (варіант А) і reseal
  `python3 .claude/hooks/testing.py reseal skel-learning --owner-answer 735-open-item-skel-learning-live-test-old-shape`
  → «resealed on the owner's word …»; запис у `.engine/testing/ledger.md` (2026-11-11T19:16:23Z, без objection round).

## Демонстрація на хвилину
- `uv run pytest -m live -q tests/contract/skel_learning/test_skell_live.py` → `1 passed in 616.04s`
  (вивід — `.engine/artifacts/735/live-resealed.txt`).
- `uv run mypy src tests` → `Success: no issues found in 438 source files`.
- `uv run ruff check tests/contract/skel_learning` → `All checks passed!`.
- `uv run pytest -q tests/contract/skel_learning` → `27 passed, 1 deselected`.
- `uv run pytest -q` (увесь набір, один раз наприкінці) → `1648 passed, 36 deselected in 1284.19s (0:21:24)`.

## Витрати
Дві сесії board runner-а (перша поставила питання 2026-11-10, друга — ця) і один живий виклик моделі в тесті;
додаткових сесій Claude не було.

## Діапазон commit-ів
Від `c662a7d` (задача → doing) до commit-а, яким задача переходить у `done/`; правка, reseal і вивід живого прогону — commit `be441e2`.

## Відкладене
- Slice skel-learning лишається `PARKED` у `testing.py status`: reseal не знімає park, а знімати його ця задача не мала.

- Stop gate (`gate.py --layer stop`) на цьому файлі пише `TESTS FAILED`: у файлі лише live-тест, за замовчуванням
  він deselected (`addopts` у `pyproject.toml`), і pytest виходить з кодом 5 (`1 deselected`). Це не падіння тесту.
  Пропозиція для двигуна — `tasks/proposed/751-open-item-stop-gate-fails-a-live-only-test-file.md`.

## Рішення, які я ухвалив сам
- Правку й reseal я закомітив (`be441e2`) ще до звіту, щоб Stop gate не ескалював через код 5 на deselected live-тесті.
- Правку взято без змін із підготовленого файлу, який ви схвалили; нічого понад неї.
- Цей звіт читає `reader`, а не overseer: змінено лише тест, а код-шлях проєкту — `SOURCE_DIRS="src"` у `.claude/project.env`.
