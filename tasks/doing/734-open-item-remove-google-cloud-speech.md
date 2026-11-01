# 734 — Remove the unused google-cloud-speech dependency

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: remove-google-cloud-speech

## Що сталося
The nightly simplifier has found the same thing four nights running (404 F-d9849f25, 405 F-b456f6f9, 406 F-1ef6a2ad, 409 F-3e5af977): google-cloud-speech (pyproject.toml:8) is imported nowhere in src, tests or scripts; speech recognition runs on google-genai (src/thinkhow/platform/speech.py:121), and docs/adr/0005-speech-gemini-transcribe.md:61 says the package is no longer needed. A cleanup task may only remove auto_remove findings, so it stays.

- Записано: 2026-10-28T17:14:27Z, агент
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
uv remove google-cloud-speech (uv.lock in the same commit); update the SDK list in .engine/architecture/architecture-map.md:603; run the full suite and compare with the known red tests; name the change in the report.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника
