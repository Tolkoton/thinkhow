# Звіт: тест версії /static ловить сталу версію і rename.js без версії

## Що змінилось для власника
Для вас нічого не змінилося: код застосунку той самий, змінилися лише тести. Тепер тест падає в обох
випадках, про які писав overseer, коли адреси `/static/…` після розгортання лишаються старими:
- версія записана один раз (константа або час commit-а), а не обчислена з файлів у `static/`;
- `rename.js` (або будь-який інший файл зі `/static/`) на сторінці без `?v=`.

Справжньої вади тест не знайшов: на коді як він є тести зелені.

## Що зроблено
- Новий файл `tests/web/test_static_version.py`, два тести без браузера:
  - `test_every_static_url_on_the_pages_carries_the_content_version` перенесено сюди без змін зі
    `tests/web/test_static_cache.py`. Він рендерить `GET /` і сторінку теми через `TestClient` і перевіряє, що
    на сторінках рівно три адреси: `/static/style.css`, `/static/rename.js` і `/static/conversation.js`. Кожна має
    `?v=` з sha256 файлів у `static/`.
  - `test_a_changed_static_file_changes_the_version_of_every_url` (новий). Тест копіює пакет `thinkhow` у
    тимчасову теку і дописує рядок у `static/rename.js`. Потім у окремому процесі Python (`PYTHONPATH` = копія)
    рендерить ті самі сторінки. Перевіряє, що імпортовано саме копію, що хеш змінився і що кожна адреса
    `/static/` має `?v=` з новим хешем. Окремий процес потрібен, бо версію рахує `server.py` під час
    імпорту (`src/thinkhow/web/server.py:47`). Інакше перевірити це без зміни коду не можна.
- `tests/web/test_static_cache.py`: звідти прибрано перенесений тест і непотрібні вже імпорти. Цей модуль
  пропускається цілком (`pytest.importorskip("playwright.sync_api")`), коли Playwright не встановлено. Тож
  перевірка версії там зникала разом із браузерним тестом. Тепер вона працює й без Playwright.

## Демонстрація на хвилину
Червоний прогін 1 — версія стала. У `server.py` обчислення хешу тимчасово замінено на константу, що
дорівнює сьогоднішньому хешу (`TEMPLATES.env.globals["static_v"] = "44019a2a5760"`):

```
E       AssertionError: ('44019a2a5760', ['/static/style.css?v=44019a2a5760', '/static/rename.js?v=44019a2a5760', ...])
FAILED tests/web/test_static_version.py::test_a_changed_static_file_changes_the_version_of_every_url
1 failed, 1 passed
```

Перенесений тест у цьому прогоні зелений: він сам цієї вади не ловить. Ловить її новий тест.

Червоний прогін 2 — `rename.js` без версії. У `base.html` тимчасово прибрано `?v={{ static_v }}` з
`/static/rename.js`: `2 failed` (обидва тести, `assert False` на `all(u.endswith(...))`).

Обидві зміни скасовано, `git status` показує лише два файли тестів. Зелений прогін на коді як він є:

```
uv run pytest tests/web/test_static_version.py tests/web/test_static_cache.py -q
3 passed
```

Швидкий набір, як у попередніх задачах: `uv run pytest -q tests/web` → `82 passed in 13.13s`. Ширший прогін
(`uv run pytest -q`, усі теки, крім `tests/smoke`, `tests/live`, `tests/research_deep`) → `1604 passed, 4 deselected in 1244.30s`.
`uv run ruff check tests/web/`, `uv run ruff format --check tests/web` і `uv run mypy` на обох файлах чисті.

## Витрати
Одна сесія runner-а. Додаткових сесій Claude не було.

## Діапазон commit-ів
Від `fe624be` (задача в `doing/`) до commit-а, що переносить задачу в `done/`.

## Відкладене
Нічого.

## Рішення, які я ухвалив сам
- Перевірку версії перенесено в окремий модуль без Playwright. Так вона не пропускається там, де браузера немає.
  Браузерний тест лишився на місці.
- «Хеш змінюється, коли змінюється файл» перевіряю на копії пакета в окремому процесі, а не правкою
  `server.py` (наприклад, щоб винести обчислення у функцію). Задача каже не міняти код без справжньої вади.
- Змінюю `rename.js`: про цей файл писав overseer. Підставити константу з будь-яким значенням тест не дасть
  для жодного файлу, бо очікувана версія — хеш усіх файлів.
