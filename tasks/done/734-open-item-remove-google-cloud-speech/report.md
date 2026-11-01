# Звіт — 734: прибрати невживаний package google-cloud-speech

## Що змінилось для власника
- `google-cloud-speech` більше не є dependency проєкту: `uv remove google-cloud-speech` прибрав рядок із
  `pyproject.toml` (був рядок 8), а з `uv.lock` — сам package і два, які приходили лише через нього: `grpcio` і
  `grpcio-status` (−89 рядків у `uv.lock`). Розпізнавання мови як і раніше працює на `google-genai`
  (`src/thinkhow/platform/speech.py:121`), поведінка продукту не змінилась.
- `.engine/architecture/architecture-map.md:603` (A3.2, «лише `platform` імпортує SDK Google») тепер називає лише ті
  SDK, які справді імпортуються: `google.cloud.storage`, `google.genai`, `google.auth`.
- У плані фічі `.engine/architecture/feature/voice-and-language.md:119-120`, де сказано «Пакет `google-cloud-speech`
  лишається», дописано: «прибрано задачею 734, 2026-11-01», щоб план не суперечив коду.

## Демонстрація на хвилину
- `uv remove google-cloud-speech` → `Resolved 94 packages`, `- google-cloud-speech==2.41.0`, `- grpcio==1.84.0`,
  `- grpcio-status==1.84.0`.
- `grep` по `src`, `tests`, `scripts` не знаходить `import grpc` чи `google.cloud.speech`. `google.api_core`, який
  імпортують `src/thinkhow/platform/storage.py:10` і тести, лишився: його приносить `google-cloud-storage`.
- `uv run ruff check .` → `All checks passed!`; `uv run mypy` → `Success: no issues found in 57 source files`;
  `PYTHONPATH=src uv run lint-imports` → `Contracts: 7 kept, 0 broken.`
- Повний набір, один раз, після зміни: `uv run pytest -q -p no:cacheprovider -rf` →
  `1525 passed, 36 deselected in 1054.80s`. Відомих червоних тестів зараз немає: останній повний прогін до цієї задачі
  (задача 724, `tasks/done/724-open-item-testing-parked-skel-facilitation/report.md:22`) дав так само `1525 passed`.
  Нових падінь немає. Прогін переписав artifact `.engine/artifacts/step-results/smoke.txt`, я повернув його з git.

## Витрати
Лише ця сесія; додаткових сесій Claude не запускав.

## Діапазон commit-ів
`b27be44` (задача → doing) … `b087ce3` (dependency і документи) … commit, яким задачу перенесено в `done/`.

## Відкладене
Нічого.

## Рішення, які я ухвалив сам
- Override mypy для `google.cloud.*` (`pyproject.toml:56`) лишив: він потрібен `google.cloud.storage`.
- Spike-скрипт `.engine/artifacts/spikes/voice-stt-2026-10-23/chirp3_probe.py`, який імпортує
  `google.cloud.speech_v2`, не чіпав: це запис spike-у, а не робочий код. Якщо власник колись увімкне Speech-to-Text
  і захоче порівняти Chirp 3, package повертається одним `uv add google-cloud-speech`.
- Повний набір запустив лише раз, після зміни, а не двічі (до і після): перша спроба «до» обірвалась на моєму
  ліміті часу в 900 с (набір іде ~1050 с), а для порівняння досить відомого результату задачі 724.
- Рядок у плані фічі `voice-and-language.md` доповнив, а не переписав: план — запис того, що вирішили тоді.
