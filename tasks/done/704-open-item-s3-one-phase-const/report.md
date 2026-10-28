# Звіт — 704: схема фасилітатора — завжди `enum` і для картки з однією фазою

## Що змінилось для власника
- pydantic для `Literal` з одним значенням пише в JSON schema `const`, а не `enum`. Фасилітатор звужує
  `current_phase_id` до фаз картки (`_phases`, `src/thinkhow/facilitation/respond.py:110`), тож картка з однією фазою
  відправила б у Vertex `{"const": …}` — форму, яку ми з Vertex не перевіряли. Зараз це недосяжно (єдина картка
  має 4 фази), але F7 (більше карток) це відкрило б.
- Тепер `_phases` додає до гілки фази той самий виправляч, що й skel-learning (`_enum_of`,
  `src/thinkhow/learning/analyze.py:83`): `const` прибирається, пишеться `{"type": "string", "enum": [...]}`. Схема
  — `anyOf: [{"type":"string","enum":[…]}, {"type":"null"}]` — однакова для однієї фази і для багатьох; для карток із
  кількома фазами вона та сама, що й до зміни. Діє на обидві схеми: `answer_schema` і `update_schema`.

## Демонстрація на хвилину
- Новий тест `test_one_phase_card_sends_an_enum_not_a_const`
  (`tests/contract/facilitator_free_mode/test_ffm_builder_one_phase_enum.py:8`, мій власний файл builder-а) — картка `solo` (одна фаза) і `alpha` (три фази),
  обидві схеми. На старому коді — RED:
  `AssertionError: ('solo', {'anyOf': [{'const': 's_only', 'type': 'string'}, {'type': 'null'}], …})`.
  Після зміни: `uv run pytest -q tests/contract/facilitator_free_mode` — зелено.
- Валідація не змінилась: фаза картки і `null` проходять (той самий тест); чужа фаза — відхиляється
  (`test_stream_schema_has_reply_first_and_only_the_cards_phases`, зелений). Локальний режим читає першу фазу з `enum`
  (`src/thinkhow/web/local.py:66`) — `test_local_mode_answers_the_first_phase_for_one_and_many_phases` зелений.
- `uv run ruff check src tests/contract/facilitator_free_mode` → `All checks passed!`; `uv run mypy src` → `Success`.
- Повний набір на `d05e97a`: `uv run pytest -q -p no:cacheprovider` → `25 failed, 1461 passed, 36 deselected in 963.92s`.
  Нових червоних немає: це ті самі 25, що й у звіті задачі 703 (`skel_learning` 19, `walking_skeleton_block` 2,
  `skel_facilitation` 2, `voice_synthesis` 1, `voice_conversation_mode_block` 1) — sealed tests, які чекають ваших
  відповідей; 1461 = 1460 задачі 703 + мій новий тест.
- Overseer: перший аудит (`20261028T084403Z-3b7369`) — BLOCK #11. Я дописав тест у sealed файл тестувальника
  `test_ffm_free_mode.py`, а builder його не редагує. Виправлення `0ac4d97`: файл повернуто до sealed стану з `04fcb94`
  (`python3 .claude/hooks/testing.py check facilitator-free-mode` → `match`), тест перенесено без змін у власний файл.
  Другий аудит (`20261028T084623Z-35299e`) — PASS; overseer сам відтворив RED на старому `respond.py`.

## Витрати
Лише ця сесія; додаткових сесій Claude не запускав.

## Діапазон commit-ів
`0a500f2` (задача → doing) … `d05e97a` (виправлення і тест) … `0ac4d97` (тест — із sealed файлу у файл builder-а, після BLOCK) … commit, яким задачу перенесено в `done/`.

## Відкладене
Нічого.

## Рішення, які я ухвалив сам
- `_enum_of` — копія з шести рядків у `respond.py`, а не імпорт із `learning/analyze.py`: `learning` уже імпортує
  `facilitation` (`src/thinkhow/learning/analyze.py:18`, `vet.py:11`), тож зворотний імпорт дав би цикл. Перенести
  обидва в одне спільне місце — можна, але це зміна поза задачею.
- Виправляч стоїть на самій гілці `Literal` (`Annotated[Literal[…], Field(json_schema_extra=…)] | None`), не на полі:
  на рівні поля pydantic дописує `enum` поверх `anyOf`, а `const` усередині лишається — я це перевірив.
- Повний набір тестів довгий (браузерні smoke-тести, ~28 с кожен) — перший запуск обірвав мій власний ліміт часу,
  а не вада; другий я запустив без ліміту.
