# 733 — Tests type-check red: 208 mypy errors in sealed tests

Залежить від: —
Потрібна присутність власника: ні
Режим: соло
Аудит потрібен: так
Додаткові сесії: ні
Відкритий пункт: tests-mypy-red

## Рішення власника
Слова власника (2026-11-10, сесія Thinkhow; записано Claude зі слів власника): «Добре, став ті задачі і попередні
всі задачі теж став. Давай докінчимо це.» — «попередні всі задачі» — усі пропозиції з `tasks/proposed/`.

## Що сталося
On 5249680 (before task 711) `uv run mypy src tests` prints «Found 208 errors in 33 files»; `uv run mypy src` is clean. Almost all: test doubles (FakeLlm and others) lack the Llm protocol member `search_text`; skel_learning tests import `analyze.Observation`. The Stop gate runs mypy on every changed file, so any slice that has to touch one of these sealed tests (e.g. continuous-analysis) is blocked by errors it did not make. Also: 25 contract tests fail on the same commit (skel_learning, skel_facilitation, voice_synthesis, voice_conversation_mode_block, walking_skeleton_block).

- Записано: 2026-10-28T11:41:04Z, агент
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Through objection packages to each owning slice's tester: give the test doubles `search_text`, fix the skel_learning imports, and carry the 25 red tests over to the current contracts; then `uv run mypy src tests` and the full `uv run pytest` are green.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника

Зроблено (2026-11-10, Claude, commit 38df430): `uv run mypy src tests` — з 163 помилок у 26 файлах лишилось 6 у
двох sealed файлах; `uv run mypy src` чистий; повний `uv run pytest` — `1648 passed, 36 deselected`. Тобто 25
червоних тестів із «Що сталося» вже зелені. Test doubles отримали `search_text` (і `delete` у `RecordingStorage`
walking-skeleton-block); ці helper-файли не sealed. Два sealed тести виправили testers: research-display — через
objection (round 1 із 2), spoken-replies — через supersede від step-results. Лишилось:

- `tests/contract/skel_learning/test_skell_live.py` (3 помилки) — це вже окрема задача 735 у `todo/`, тут не чіпаю.
- `tests/contract/notes_readers/test_nr_catchup_disputed_q1_full_instructions.py`, рядок 13 (3 помилки). Tester
  записав там `# type: ignore[call-overload]`, а mypy 2.4.0 (та сама версія, що й тоді) дає на цьому рядку
  `arg-type`. Тому ignore нічого не глушить, і з'являються ще дві помилки. Slice notes-readers уже використав обидва
  objection rounds. Ще один objection не виправить тест: скрипт просто запаркує slice (третій раунд). Supersede теж
  не підходить: жоден пізніший контракт не змінює того, що тримає цей тест.

1. Дозволити правку sealed тесту notes-readers `tests/contract/notes_readers/test_nr_catchup_disputed_q1_full_instructions.py`?
   Правка: у `_two_notes` тип `memory: list[dict[str, object]]` стає `list[dict[str, Any]]` (і `from typing import Any`),
   а хибний `# type: ignore[call-overload]` прибирається. Жодна перевірка (assert) не змінюється.
   - **А. Так.** Наступна сесія робить рівно цю правку і запечатує файл знову командою
     `python3 .claude/hooks/testing.py reseal notes-readers --owner-answer 733-open-item-tests-mypy-red`. Цей скрипт
     приймає лише ваше одне слово «так» під цим питанням. Після цього mypy по `tests` червоний тільки на файлі задачі 735.
   - **Б. Ні, objection.** Третій раунд запаркує notes-readers, а тест так і лишиться неправленим. Сенсу немає.
   - **В. Ні, лишити як є.** 3 помилки mypy лишаються. Stop gate заблокує лише той slice, якому доведеться змінити
     саме цей файл.

   Порада: **А**. Правка лише в типах, перевірки ті самі, і її видно в diff одним рядком.

Відповідь: так
Записано Claude зі слів власника 2026-11-11, сесія Thinkhow: «Правка започаткованого тесту можна, ми це вже говорили» («започаткованого» — так голос розпізнав «запечатаного»).
