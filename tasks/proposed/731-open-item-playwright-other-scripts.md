# 731 — Інші browser-скрипти — на Playwright із dev-залежностей

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: playwright-other-scripts

## Що сталося
Задача 706 зробила Playwright 1.64.1 dev dependency і перевела лише smoke голосу. Ще десять скриптів у scripts/ запускаються через uv run --with. Дев'ять мають у docstring команду uv run --with playwright==1.64.1: live_conversation_mode.py, screenshots_interface_language.py, screenshots_icon_buttons.py, screenshots_minimal_design.py, screenshots_delete_topic.py, smoke_test_conversation_mode.py, smoke_test_conversation_resilience.py, screenshots_current_model.py, smoke_test_send_stops_recording.py. Десятий, talk_harness.py, пише лише uv run --with …. П'ять (screenshots_current_model.py, screenshots_minimal_design.py, screenshots_delete_topic.py, smoke_test_conversation_resilience.py, talk_harness.py) вантажать Playwright через importlib. Чотири з них, усі, крім smoke_test_conversation_resilience.py, вказують шлях до chromium-1208. Працюють і так. Catch-up тести tests/contract/{conversation_loop,conversation_resilience,minimal_design}/*_catchup_run.py запускають скрипти через uv run --with playwright==1.64.1.

- Записано: 2026-10-28T09:20:31Z, агент
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
У цих скриптах — звичайний import playwright.sync_api, команда в docstring uv run python …, Chromium за замовчуванням Playwright-ового (або THINKHOW_CHROMIUM); прогнати кожен.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника
