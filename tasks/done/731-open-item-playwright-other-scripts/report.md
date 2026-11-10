# Звіт — 731: інші browser-скрипти — на Playwright із dev-залежностей

## Що змінилось для власника
- Усі browser-скрипти в `scripts/` тепер запускаються звичайною командою `uv run python scripts/<скрипт>.py …`,
  без `uv run --with playwright==1.64.1`. Playwright береться з dev dependencies (`pyproject.toml`, задача 706).
- Ніде в `scripts/` Playwright більше не вантажиться через `importlib` і не береться re-export-ом із
  `smoke_test_voice_dictation.py`. Скрипти пишуть звичайний `from playwright.sync_api import sync_playwright`.
- Шлях до кешованого `chromium-1208` прибрано з `screenshots_minimal_design.py` і `talk_harness.py`. Через них
  він зникає і з усіх скриптів, які беруть `CHROMIUM` у них. Тепер Chromium береться з `THINKHOW_CHROMIUM`, а без
  нього Playwright бере свій (`executable_path=None`). На цьому сервері це `chromium-1248`.
- Змінено 12 скриптів: десять із задачі, `talk_harness.py` і ще два з тією самою вадою (див. «Рішення, які я
  ухвалив сам»). Поведінка жодного скрипту не змінилась.

## Демонстрація на хвилину
Кожен скрипт запущено командою з його docstring (`PYTHONPATH=src uv run python scripts/<скрипт>.py …`). Exit 0,
останній рядок кожного:
- `smoke_test_send_stops_recording.py` → `OK: «Надіслати» while recording: text in the field, nothing sent; the next press sent it`
- `smoke_test_conversation_mode.py` → `OK: one click, 3 cycles without a touch; …`
- `smoke_test_conversation_resilience.py` → `OK: one /speak failed and was skipped; 3 cycles without a touch; …`
- `screenshots_icon_buttons.py --out …` → `OK: icons only; recording, recognizing and pending visible without words; …`
- `screenshots_minimal_design.py --out …` → `OK: dark theme, pending state, hidden buttons, line breaks, phone width; …`
- `screenshots_delete_topic.py --out …` → `OK: deleted from the list, no bin on the page, folders empty, the kept topic whole; …`
- `screenshots_rename_topic.py --out …` → `OK: renamed in the list, no pencil on the page, kept on reload, empty, foreign refused: …`
- `screenshots_current_model.py --out …` → `OK: caption and marks on the seeded topic, free → the card live; …`
- `screenshots_interface_language.py --out …` → `OK: 4 languages, every page in the chosen one; …`
- `smoke_test_document_upload.py --out …` → `OK: the paperclip uploads PDF and DOCX, both stay after reload, 4 refusals add no turn; …`
- `live_conversation_mode.py uk-UA`. Це справжні моделі: Gemini, `gemini-3.5-transcribe`, Cloud TTS. Exit 0, звіт
  `.engine/artifacts/conversation-mode/live-20261110T154531Z.md`. Усі шість реплік людини розпізнано. На п'ять
  стенд отримав голосову відповідь, із затримками 28.61, 8.85, 98.33, 12.37, 238.72 с. На шосту відповіді не було
  (`Відповідь (текст): —`). Запит `/reply` почався, але за 420 с (`TURN_TIMEOUT_S`) модель нічого не повернула, і
  стенд перестав чекати. Браузер і стенд при цьому працювали, тож це не стосується Playwright. Це той самий завислий
  потік фасилітатора, про який пропозиція 744 (`tasks/proposed/744-open-item-hung-stream-and-search-limits.md`).
- Браузер без `THINKHOW_CHROMIUM`: `p.chromium.executable_path` →
  `/home/lao/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome`, версія `156.0.8078.4`. Під час прогону
  headless-процеси йшли з `chromium_headless_shell-1248`, а не з `chromium-1208`.
- Catch-up тести, які запускають ці скрипти (`tests/contract/minimal_design/test_mdesign_catchup_screens.py`,
  `tests/contract/conversation_loop/test_cloop_catchup_{smoke,disputed_q2_exact,disputed_q3_artifact}.py`,
  `tests/contract/conversation_resilience/test_cres_catchup_{smoke,disputed_q1_q2}.py`) → `37 passed in 632.87s`.
- `uv run ruff check scripts` → `All checks passed!`; `uv run ruff format --check scripts` → `38 files already formatted`;
  `uv run mypy` → `Success: no issues found in 59 source files`.
- Повний набір: `1648 passed, 36 deselected in 1226.07s`.

## Витрати
Лише ця сесія, додаткових сесій Claude не було. Live-прогін `live_conversation_mode.py uk-UA` зробив 11 викликів
Gemini, 6 викликів speech і 39 TTS (`llm_call`, `speech_call`, `tts_call` у журналі сервера). Це прогін, а не
сесія Claude.

## Діапазон commit-ів
`b3029ba` (задача → doing) … `f4e8347` (скрипти і live-artifact) … commit, яким задачу перенесено в `done/`.

## Відкладене
- Catch-up тести (`tests/contract/conversation_loop/cloop_catchup_run.py:369`,
  `tests/contract/conversation_resilience/cres_catchup_run.py:433`, `tests/contract/minimal_design/mdesign_catchup_run.py:131`)
  і далі викликають скрипти через `uv run --with playwright==1.64.1`. Я їх не змінював: це contract тести slice-ів,
  а версія в них та сама, що в dev dependencies, тож `--with` нічого не міняє (37 passed вище). Те саме з
  історичними записами (`.engine/slices/*.md`, звіти в `tasks/done/`): вони описують, як було тоді.
- `uv run mypy scripts/*.py` знаходить ще 6 помилок, усі у файлах, яких я не торкався:
  `scripts/smoke_test_voice_language.py:51-52` і `scripts/smoke_test_product_cards.py:75-96`. До моїх змін помилок
  було 9; три з них прибрали мої правки. Звичайний `uv run mypy` (за конфігом проєкту) чистий.
- Live-прогін зроблено лише для `uk-UA`, без `pl-PL` (див. нижче).

## Рішення, які я ухвалив сам
- Перевів ще три скрипти поза переліком задачі. `screenshots_rename_topic.py` вантажив Playwright через `importlib`, а
  в docstring мав `uv run --with`. `screenshots_interface_language.py` теж вантажив його через `importlib`: задача
  називала лише його команду. `smoke_test_document_upload.py` брав `sync_playwright` re-export-ом із
  `smoke_test_voice_dictation.py`, як і `smoke_test_send_stops_recording.py` та `screenshots_icon_buttons.py`. Цей
  re-export mypy відхилив (`does not explicitly export attribute "sync_playwright"`), тож тепер усі три імпортують
  Playwright напряму.
- Live-прогін — лише `uk-UA`. Мета прогону — показати, що скрипт і стенд працюють із новим імпортом, а одна мова
  показує це так само, як дві. Один прогін на справжніх моделях іде ~15 хв.
- Live-artifact `live-20261110T154531Z*` закомічено поруч із попередніми live-прогонами в
  `.engine/artifacts/conversation-mode/` як доказ. Artifact-и, які smoke-скрипти переписують на місці
  (`conversation-loop/`, `conversation-resilience/`, `send-stops-recording/`), я повернув із git. Їхній вивід
  збережено в `/tmp/t731/`.
