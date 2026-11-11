# 750 — Two smoke scripts keep the type-check red: звіт

## Що змінилось для власника
Type-check проєкту знову зелений: `uv run mypy src tests scripts` → `Success: no issues found in 486 source files`
(на cf4adde було «Found 12 errors in 4 files»; 733 і 735 уже в `done/`, а цей commit прибрав останні 6 помилок у двох
smoke scripts). Тож наступне оновлення залежностей (update-deps, як у задачі 419) більше не зупиниться на тому, що
gate червоний ще до оновлень, — принаймні не через type-check.

## Демонстрація на хвилину
- `uv run mypy src tests scripts` → `Success: no issues found in 486 source files`.
- `uv run ruff check scripts/` → `All checks passed!`; `ruff format --check` обох файлів → `2 files already formatted`.
- `uv run python scripts/smoke_test_voice_language.py` → exit 0, останній рядок
  `OK: the language is chosen, stored and refused for Russian; …`, серед кроків `GET / → 200, «Język: Polski»`.
- `scripts/smoke_test_product_cards.py` на справжній моделі не запускався: на сервері немає ADC
  (`~/.config/gcloud/application_default_credentials.json` відсутній). Замість цього: contract tests зі stand-in-ами,
  що запускають сам script (`tests/contract/product_cards/test_pc_catchup_smoke.py`,
  `test_pc_catchup_disputed_q2_offer_size.py`) разом із `tests/contract/voice_language` → `54 passed in 24.68s`;
  і перевірка, що `log_event` під `redirect_stdout` потрапляє в буфер: рядок
  `{"severity": "INFO", "model": "x", "event": "llm_call", "request_id": null}` зловлено.
- Повний набір тестів, один раз: `uv run pytest -q` → `1695 passed, 35 deselected in 1214.97s (0:20:14)` (`.engine/artifacts/750/full-pytest.txt`).

## Витрати
Додаткових сесій Claude не було.

## Commit-и
fbdd164 (код); commit перенесення задачі в `done/` — наступний.

## Відкладене
Live-прогін `smoke_test_product_cards.py` (і `tests/contract/product_cards/test_pc_catchup_smoke_live.py`) — коли на
сервері буде ADC.

## Рішення, які я ухвалив сам
- **product-cards: не patch, а redirect stdout.** Задача радила patch-ити `log_event` там, де його визначено
  (`thinkhow.platform.log`). Але `llm.py:21` робить `from thinkhow.platform.log import log_event`, і patch у `log`
  не змінив би імені, яке викликає `llm.py:258`, — script перестав би ловити рядки `llm_call`. `log_event` без
  stream пише в «the stdout of the moment (so a redirect of stdout catches the line)» (`src/thinkhow/platform/log.py:16`),
  тож script тепер виконує виклики моделі під `contextlib.redirect_stdout(io.StringIO())` і бере з буфера рядки з
  `"llm_call"`. Підміни функції й власної `recording` більше немає — нема й розбіжності сигнатур; `src/` не змінено
  (явний re-export у `llm.py` був би зміною робочого коду заради script-а). Формат рядка той самий, бо його тепер
  пише сам `log_event`.
- **voice-language:** другий `chosen` (текст сторінки) перейменовано на `greeting`; поведінка та сама.
