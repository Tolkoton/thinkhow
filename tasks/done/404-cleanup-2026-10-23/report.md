# 404 — Прибирання 2026-10-23: звіт

## Що змінилось для власника

- Код не змінювався, нічого не прибрано. Simplifier знайшов дві речі, і обидві чекають вашого огляду
  в `.engine/simplifier/report.md`, у розділі «2026-10-23T22:37:55Z — code, nightly 2026-10-23» (рядок 75):
  - `F-d9849f25` (`confirm`): залежність `google-cloud-speech` (`pyproject.toml:7`) більше не потрібна.
    Розпізнавання мови тепер іде через `gemini-3.5-transcribe` і `google-genai`
    (`src/thinkhow/platform/speech.py`), а ADR-0005 каже, що пакет не потрібен. Видалити package агент
    може лише з вашого прохання, тому я його не видаляв. Те саме вже пропонували дві знахідки
    від 2026-10-23T16:25:25Z (`F-a5c66d41`, `F-8c53a644`) у тому ж файлі.
  - `F-c05ced66` (`flag_only`): `speech._text` (`src/thinkhow/platform/speech.py:91-98`) повторює
    `llm._chunk_text` (`src/thinkhow/platform/llm.py:189-196`) рядок у рядок, лише додає `.strip()`.
    Це лише позначка: у цьому прибиранні її не виправляють.
- Вивід `python3 .claude/hooks/simplifier.py nightly` (exit 0; копія лежить у
  `.engine/simplifier/2026-10-23-nightly.txt`):

```
24 signal(s) in .claude/state/simplifier/signals-full.json
SIMPLIFIER CALL: files grew from 0 (median of the last 3 runs) to 35; lines grew from 0 (median of the last 3 runs) to 2635; functions grew from 0 (median of the last 3 runs) to 185; dead-code grew from 0 (median of the last 3 runs) to 13; unused-dependency grew from 0 (median of the last 3 runs) to 4
Reversal rate: 0 of the last 0 removals came back (0.0 %; the corridor is 5-20 %) — too few removals to judge (0 of the 10 needed)
```

- Чому «зросли з 0»: у всіх попередніх записах `.claude/state/simplifier/metrics.jsonl` (2026-10-19 і
  2026-10-22) `files`, `lines` і `functions` дорівнюють 0. Це перший замір, коли код у `src` уже є, тобто
  ріст від порожнього проєкту, а не стрибок за один день.
- Відповіді на пункти «Що зробити»:
  1. Nightly запущено, вивід — вище.
  2. У виводі є `SIMPLIFIER CALL:`, тож я зробив один прохід. `request --lens code --paths src` (запит
     збережено в `.engine/simplifier/2026-10-23-code-request.txt`), агент `simplifier`, відповідь —
     `.engine/simplifier/answer.json`. `validate` відповів «2 valid, 0 rejected, 0 lowered». Другої думки
     немає: `simplifier.py` не має такої команди, і в `.claude/project.env` її не налаштовано. Наостанок
     `route --title "code, nightly 2026-10-23"` відповів «2 finding(s) for the owner in
     .engine/simplifier/report.md; 0 auto_remove».
  3. Знахідок `auto_remove` немає, тож нічого не прибрано і commit-ів із `Simplifier-Finding:` немає.
  4. Знахідки `confirm` і `flag_only` я не чіпав: `route` записав їх у `.engine/simplifier/report.md`.
- Повний набір тестів не запускався: нічого не прибрано, а `TEST_CMD_FULL` у `.claude/project.env` порожній.

## Демонстрація на хвилину

```bash
python3 .claude/hooks/simplifier.py nightly          # SIMPLIFIER CALL: files 0 → 35, lines 0 → 2635 …
sed -n '75,$p' .engine/simplifier/report.md          # розділ "code, nightly 2026-10-23": 1 confirm, 1 flag_only
```

## Витрати

Додаткових сесій Claude (окремих `claude -p`) я не запускав. `board.py extra-allowed` перед проходом
показав: «додаткові сесії Claude за сім днів: 1.59 USD (межі немає)». Subagents усередині цієї сесії:
`simplifier` (один раз) і `reader` для цього звіту.

## Діапазон commit-ів

Від `9e2a48c` (задача перейшла в `doing/`) до commit-а, що переносить задачу в `done/` разом із цим звітом.

## Відкладене

- `google-cloud-speech` чекає вашого слова. Відтепер кожен nightly показуватиме цей signal, доки пакет
  лишається в `pyproject.toml`.
- Інші три signals `unused-dependency` — false positives, кажуть simplifier і мої grep-и:
  `google-cloud-storage` імпортується як `google.cloud.storage`, `google-genai` як `google.genai`, а
  `jinja2` використовується через `fastapi.templating.Jinja2Templates` (`src/thinkhow/web/server.py:20`).
  Інструмент signals просто замінює дефіси на підкреслення, тому таких імпортів не бачить. Це межа
  інструмента двигуна, а не робота для проєкту.
- Решта signals (`complexity` у `analyze._topic`, `nesting` у `VertexLlm.stream_json`, `dead-code` від vulture
  з упевненістю 60 % на `model_config` та інших іменах pydantic) simplifier знахідками не зробив.

## Рішення, які я ухвалив сам

- Саму задачу в `blocked/` не переносив. Знахідок `auto_remove` немає, тож за п. 3 задачі не виникло
  питання «прибирати чи ні». Знахідки `confirm` і `flag_only` за п. 4 уже лежать в
  `.engine/simplifier/report.md` для огляду, а окреме питання про `google-cloud-speech` повторило б три
  знахідки, що вже там є.
- Зміну в `.claude/unattended/board-runner.sh` (вимкнено паркування задач за віком) у робочому дереві
  не чіпав і в commit не включав: це ваша власна правка, вона не стосується цієї задачі.
