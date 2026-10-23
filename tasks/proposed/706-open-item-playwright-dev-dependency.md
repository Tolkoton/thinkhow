# 706 — Playwright у dev-залежності для smoke голосу

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: playwright-dev-dependency

## Що сталося
Smoke голосу (scripts/smoke_test_voice_dictation.py, задача 106) запускається з тимчасового середовища uv: uv run --with playwright==1.64.1 …, бо додавання пакета — дія з дозволу, а задача 106 йшла без нагляду (escalations.md 2026-10-23T17:50Z, AUTONOMOUS). Версія закріплена в команді, не в uv.lock; Chromium — з кешу сервера (chromium-1208) або THINKHOW_CHROMIUM.

- Записано: 2026-10-23T18:15:23Z, агент
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
uv add --dev playwright (з дозволу власника), звичайний import у smoke замість importlib, playwright install chromium; команда smoke — uv run python scripts/smoke_test_voice_dictation.py.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника
