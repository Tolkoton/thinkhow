# Сигнал «unused-dependency» називає невикористаною кожну залежність із namespace-пакета

Клас: 3
Залежить від: —
Потрібна присутність власника: ні
Режим: соло
Аудит потрібен: ні
Додаткові сесії: ні

## Що сталося
ThinkHow, нічне прибирання, задача 409 (2026-10-28). `simplify_signals.py` дав п'ять сигналів `unused-dependency` на
рядки 7–10 і 13 `pyproject.toml`. Чотири з них хибні:
- `google-auth` імпортується як `google.auth` (`src/thinkhow/platform/tts.py`, `identity.py`);
- `google-cloud-storage` — як `google.cloud.storage` (`src/thinkhow/platform/storage.py`);
- `google-genai` — як `google.genai` (`src/thinkhow/platform/llm.py`);
- `jinja2` проєкт сам не імпортує, але без нього не працює `fastapi.templating.Jinja2Templates`.

Причина перших трьох: `imported_modules` (`.claude/hooks/simplify_signals.py:209`) лишає лише верхній модуль
(`module.split(".")[0]`, тож кожен `google.*` стає `google`), а `import_names` шукає `google-auth` під назвою
`google_auth`. Distribution із namespace-пакета не збігається ніколи. П'ятий сигнал (`google-cloud-speech`) правдивий,
бо пакет справді не використовується (ADR-0005 ThinkHow).

Simplifier усі чотири розпізнав як пастки, але вони приходять щоночі, рахуються в підсумку `unused-dependency` і в
`trend`, який кличе simplifier. Двигун цю межу вже називає: `docs/engine-limits.md:930–934` («and for a namespace
package (`google.*`)»). Тобто це задокументована межа сигналу, а не нова вада. Чи прибирати її, вирішує власник.

## Що зробити
- Звіряти distribution із namespace-пакета з повними іменами імпортів: `google-auth` → `google.auth`,
  `google-cloud-storage` → `google.cloud.storage`, `google-genai` → `google.genai`. Наприклад, тримати поряд із
  верхніми модулями й повні, а для відомих namespace (`google`, `azure`, …) або рядків `IMPORT_NAMES` пробувати `-` → `.`.
  Рядок `"protobuf": ("google",)` в `IMPORT_NAMES` має й далі працювати (`google.protobuf`). Як саме — вирішує будівник.
- Залежність, яку використовує інша залежність (`jinja2` під `Jinja2Templates` FastAPI), за імпортами не видно.
  Варіанти: таблиця на кшталт `IMPORT_NAMES` («`jinja2` використано, коли імпортовано `fastapi.templating` чи
  `starlette.templating`») або лишити як межу в `docs/engine-limits.md`, назвавши такий випадок прямо.
- Оновити `docs/engine-limits.md`, розділ «The simplifier», під нову поведінку.

## Готово, коли
- На `pyproject.toml` ThinkHow на commit-і `eea5e29` сигнал називає лише `google-cloud-speech` (або ще `jinja2`, якщо
  обрано лишити його як межу, і тоді ця межа названа в `docs/engine-limits.md`).
- Тест двигуна: namespace-distribution, імпортований повним іменем, не дає сигналу; той самий distribution без жодного
  імпорту — дає.

## Питання до власника
