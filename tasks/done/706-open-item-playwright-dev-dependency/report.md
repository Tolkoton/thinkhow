# Звіт — 706: Playwright у dev-залежностях для smoke голосу

## Що змінилось для власника
- Playwright тепер є dev dependency проєкту: `pyproject.toml` (група `dev`) має рядок `"playwright==1.64.1"`, а версія
  записана в `uv.lock` (разом із `greenlet` і `pyee`). Раніше її закріплювала тільки команда `uv run --with …`.
- Smoke голосу запускається звичайною командою:
  `uv run python scripts/smoke_test_voice_dictation.py`. Скрипт імпортує Playwright звичайним `import`
  (`from playwright.sync_api import sync_playwright`), а не через `importlib`.
- Chromium — той, що ставить сам Playwright: `uv run playwright install chromium`, по одному разу на машину. На цьому
  сервері це вже зроблено, Playwright 1.64.1 узяв `chromium-1248`. `THINKHOW_CHROMIUM`, як і раніше, підставляє
  інший браузер. Шлях до кешованого `chromium-1208` зі скрипту прибрано.

## Демонстрація на хвилину
- `uv add --dev "playwright==1.64.1"` → `+ greenlet==3.5.6`, `+ playwright==1.64.1`, `+ pyee==14.0.0`.
- `uv run playwright install chromium` → `Chrome Headless Shell 156.0.8078.4 (playwright chromium-headless-shell v1248)
  downloaded to /home/lao/.cache/ms-playwright/chromium_headless_shell-1248`. У `~/.cache/ms-playwright/` тепер є
  `chromium-1248` і `chromium_headless_shell-1248`.
- `uv run python scripts/smoke_test_voice_dictation.py` → exit 0. Скрипт друкує:
  `field after the microphone: (локальний режим) розпізнаний текст`,
  `POST …/voice: {'type': 'audio/webm;codecs=opus', 'status': 200}`,
  `OK: language → topic → microphone → text in the field → sent and answered`.
- `uv run ruff check .` → `All checks passed!`; `uv run mypy` → `Success: no issues found in 57 source files`.
- Повний набір на `e52d19d`: `25 failed, 1464 passed, 36 deselected in 967.19s` — ті самі відомі 25 падінь, що й
  у задачі 705: `skel_learning`, `skel_facilitation`, `voice_synthesis`/`voice_conversation_mode_block` (409 fragment)
  і два `walking_skeleton_block`. Нових падінь немає. Перший повний прогін обірвав ліміт часу background-команди
  (10 хв; набір іде ~16 хв), і його pytest, найімовірніше, ще працював поряд із другим. Після них у
  `.engine/artifacts/step-results/smoke.txt` лишився запис `FAIL the card files are byte-for-byte the same`. Цей файл —
  artifact `scripts/smoke_test_learning_loop.py`, і тест `test_AC7…` повертає його як був. Два прогони одночасно ділили
  ці файли, тож я повернув artifact із git (`git checkout`) і нічого з нього не висновую.

## Витрати
Лише ця сесія; додаткових сесій Claude не запускав.

## Діапазон commit-ів
`686be67` (задача → doing) … `e52d19d` (dev dependency і smoke) … commit, яким задачу перенесено в `done/`.

## Відкладене
- Ще десять browser-скриптів запускаються через `uv run --with`. Дев'ять мають у docstring повну команду
  `uv run --with playwright==1.64.1`: `scripts/live_conversation_mode.py`, `screenshots_interface_language.py`,
  `screenshots_icon_buttons.py`, `screenshots_minimal_design.py`, `screenshots_delete_topic.py`,
  `smoke_test_conversation_mode.py`, `smoke_test_conversation_resilience.py`, `screenshots_current_model.py`,
  `smoke_test_send_stops_recording.py`. Десятий, `scripts/talk_harness.py`, пише лише `uv run --with …`.
  П'ять скриптів (`screenshots_current_model.py`, `screenshots_minimal_design.py`, `screenshots_delete_topic.py`,
  `smoke_test_conversation_resilience.py`, `talk_harness.py`) вантажать Playwright через `importlib`. Чотири з них,
  усі, крім `smoke_test_conversation_resilience.py`, вказують шлях до `chromium-1208`. Вони працюють і так, бо
  `chromium-1208` у кеші лишився. Задача називала лише
  smoke голосу, тож решту я не чіпав. Пропозиція — `tasks/proposed/731-open-item-playwright-other-scripts.md`;
  у роботу її ставите ви.
- Тести catch-up (`tests/contract/conversation_loop/cloop_catchup_run.py:369`,
  `tests/contract/conversation_resilience/cres_catchup_run.py:433`, `tests/contract/minimal_design/mdesign_catchup_run.py:131`)
  запускають скрипти командою `uv run --with playwright==1.64.1`. Ця команда й далі правильна, бо версія та сама.
  Ці файли належать до contract тестів slice-ів (`tests/contract/`), тож я їх не змінював. Якщо їх переводити на
  `uv run python`, то разом із пропозицією 731.

## Рішення, які я ухвалив сам
- Версію закріплено точно (`==1.64.1`), а не як `>=`. Саме ця версія ходила в усіх smoke-прогонах, і від неї залежить,
  яку збірку Chromium Playwright очікує. Нову версію принесе звичайне оновлення залежностей через `/maintain`.
- Дозвіл на `uv add --dev` — те, що ви поставили задачу в `todo/`. До того ж, за engine rules, пакети проєкту через
  його власний менеджер (`uv add`) агент додає без питання.
- Без `THINKHOW_CHROMIUM` скрипт віддає вибір браузера Playwright (`executable_path=None`), а не шукає `chromium-1208`.
  Причина: Playwright 1.64.1 сам ставить `chromium-1248`, тож шлях до 1208 прив'язав би скрипт до чужої збірки.
