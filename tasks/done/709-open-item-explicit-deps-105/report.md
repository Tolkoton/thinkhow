# Звіт — 709: явні dependencies google-auth, PyYAML, httpx, httpx2, types-PyYAML

## Що змінилось для власника
- `pyproject.toml` тепер прямо називає кожен runtime package, який імпортує код: додано `google-auth[requests]>=2.62.0`,
  `httpx2>=2.16.0`, `pyyaml>=6.0.3`. `httpx>=0.28.1` там уже був (його додала задача 303, commit `f4c2e6d`), тому
  `uv add httpx` нічого не змінив. Раніше ці пакети приходили лише як dependencies `fastapi[standard]`, `google-genai`
  і `google-cloud-*`. Тепер зміна в тих пакетах не прибере їх непомітно.
- У dev-групі з'явився `types-pyyaml>=6.0.12.20260906`. Override mypy для `yaml` (`ignore_missing_imports`) прибрано:
  mypy тепер перевіряє виклики `yaml` за stubs. Помилок не знайшлося.
- Версії встановлених пакетів не змінились (у `uv.lock` ті самі `google-auth 2.62.0`, `httpx2 2.16.0`,
  `pyyaml 6.0.3`). Новий пакет у lock один: `types-pyyaml 6.0.12.20260906`.

## Демонстрація на хвилину
- `uv add 'google-auth[requests]' pyyaml httpx httpx2` → `Resolved 96 packages`;
  `uv add --dev types-PyYAML` → `+ types-pyyaml==6.0.12.20260906`.
- `uv run ruff check .` → `All checks passed!`; `uv run mypy` → `Success: no issues found in 57 source files`
  (уже без override для `yaml`); `PYTHONPATH=src uv run lint-imports` → `Contracts: 7 kept, 0 broken.`
- Повний набір: `25 failed, 1464 passed, 36 deselected in 992.47s`. Це ті самі відомі 25 падінь, що в задачі 706
  (`skel_learning`, `skel_facilitation`, `voice_synthesis`/`voice_conversation_mode_block` (409 fragment), два
  `walking_skeleton_block`). Нових падінь немає. Прогін переписав artifact `.engine/artifacts/step-results/smoke.txt`
  (змінилась лише позначка часу), тож я повернув його з git.

## Витрати
Лише ця сесія; додаткових сесій Claude не запускав.

## Діапазон commit-ів
`315aa5e` (задача → doing) … `0fd4b2e` (dependencies і override) … commit, яким задачу перенесено в `done/`.

## Відкладене
Нічого.

## Рішення, які я ухвалив сам
- `google-auth` додано з extra `[requests]`, а не голим пакетом. Код імпортує `google.auth.transport.requests`
  (`src/thinkhow/platform/identity.py:74`, `src/thinkhow/platform/tts.py:168`), а для цього потрібен пакет
  `requests`. Сьогодні його приносить `google-genai[requests]`; з extra він стає власною dependency проєкту.
- Нижні межі версій (`>=`) — ті, що вже стоять у `uv.lock`; так `uv add` пише їх за замовчуванням, і так записані
  решта dependencies проєкту.
- Bypass guard Stop hook-а зупинив зміну в `[tool.mypy]`. Override прибрано, тобто перевірка стала суворішою, тож я
  дописав у `pyproject.toml` рядок `gate-allow:` із цією причиною.
- Що ставити пакети, вирішує агент: так сказано в самій задачі («Do not ask the owner») і в engine rules (пакети через
  власний менеджер проєкту — auto-allowed).
