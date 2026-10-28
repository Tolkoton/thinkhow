# 409 — Прибирання 2026-10-28: звіт

## Що змінилось для власника

- Код не змінювався, нічого не прибрано. Одна знахідка чекає вашого огляду в `.engine/simplifier/report.md`, у розділі
  «2026-10-28T17:13:26Z — code, nightly 2026-10-28» (рядок 166):
  - `F-3e5af977` (`confirm`): залежність `google-cloud-speech` (`pyproject.toml:8`) не потрібна. Розпізнавання мови
    йде через `google-genai` (`src/thinkhow/platform/speech.py:121`), і `docs/adr/0005-speech-gemini-transcribe.md:61`
    каже, що пакет більше не потрібен. Це та сама знахідка, що в 404 (`F-d9849f25`), 405 (`F-b456f6f9`) і 406
    (`F-1ef6a2ad`), тобто вже четверта ніч.
  - Пакети ви доручили вирішувати агентові. Тому я не ставлю вам питання, а поклав пропозицію-задачу
    `tasks/proposed/734-open-item-remove-google-cloud-speech.md`: `uv remove google-cloud-speech`, `uv.lock` у тому
    самому commit-і, виправити перелік SDK в `.engine/architecture/architecture-map.md:603`. Задача прибирання сама
    цього не робить: за п. 3–4 вона прибирає лише `auto_remove`.
- Чому simplifier цього разу покликано: з 406 (`b32017d`) у `src` прийшли 33 commit-и задач 204–208, 303, 305, 306, 308–310, 704, 705, 710–712
  (`git log b32017d..eea5e29 -- src`). Це справжнє зростання від нових функцій. Останній запис
  `.claude/state/simplifier/metrics.jsonl`: files 54, lines 5928, functions 389, complexity 8, dead-code 30.
- Simplifier отримав 51 signal (complexity, nesting, vulture dead-code, unused-dependency, trend) і знахідкою визнав
  лише залежність. Решту він назвав пастками. Vulture-signals про `model_config`, validators,
  `settings_customise_sources`, route functions і поля Profile — це вживання через pydantic, FastAPI чи schema для LLM.
  Чотири інші signals `unused-dependency` (`google-auth`, `google-cloud-storage`, `google-genai`, `jinja2`) хибні.
- Хибні signals залежностей — це межа двигуна. `simplify_signals.py` бере лише верхній модуль import-а
  (`google.auth` → `google`), а `google-auth` шукає як `google_auth`. Тому залежність із namespace package завжди
  виглядає невживаною. Сесія двигуна `engine-27` підтвердила, що ця межа вже записана в `docs/engine-limits.md`
  двигуна, і доопрацювала записку `.engine/to-engine/unused-dependency-misses-namespace-packages.md`. Прибирати межу
  чи ні — ваш вибір. Його вам поставить сесія двигуна, тож тут питання немає. Роботі це не заважає, бо simplifier
  розпізнав усі чотири signals як хибні.
- Вивід `python3 .claude/hooks/simplifier.py nightly` (exit 0; копія лежить у
  `.engine/simplifier/2026-10-28-nightly.txt`):

```
51 signal(s) in .claude/state/simplifier/signals-full.json
SIMPLIFIER CALL: files grew from 35 (median of the last 5 runs) to 54; lines grew from 2635 (median of the last 5 runs) to 5928; functions grew from 185 (median of the last 5 runs) to 389; complexity grew from 1 (median of the last 5 runs) to 8; dead-code grew from 13 (median of the last 5 runs) to 30
Reversal rate: 0 of the last 0 removals came back (0.0 %; the corridor is 5-20 %) — too few removals to judge (0 of the 10 needed)
```

- Відповіді на пункти «Що зробити»:
  1. Nightly запущено, вивід наведено вище.
  2. У виводі є `SIMPLIFIER CALL:`, тож я зробив один прохід: `request --lens code --paths src` (запит збережено в
     `.engine/simplifier/2026-10-28-code-request.txt`), агент `simplifier`, відповідь лежить у
     `.engine/simplifier/answer.json`. `validate` відповів «1 valid, 0 rejected, 0 lowered». Другої думки немає,
     бо її не налаштовано. Наостанок `route --title "code, nightly 2026-10-28"` відповів
     «1 finding(s) for the owner in .engine/simplifier/report.md; 0 auto_remove».
  3. Знахідок `auto_remove` немає, тож нічого не прибрано і commit-ів із `Simplifier-Finding:` немає.
  4. Знахідку `confirm` я не чіпав: `route` записав її в `.engine/simplifier/report.md` і в чергу уроків
     (`.engine/journal/lessons/90ea3b35-d95d-4462-97de-edd47dae1c83.md`).
- Повний набір тестів не запускався, бо нічого не прибрано.

## Демонстрація на хвилину

```bash
cat .engine/simplifier/2026-10-28-nightly.txt     # SIMPLIFIER CALL: lines 2635 → 5928, dead-code 13 → 30
sed -n '166,$p' .engine/simplifier/report.md      # розділ "code, nightly 2026-10-28": 1 confirm, 0 flag_only
```

## Витрати

Додаткових сесій Claude (окремих `claude -p`) я не запускав. Перед проходом `board.py extra-allowed` показав:
«додаткові сесії Claude за сім днів: 4.74 USD (межі немає)». Subagents у цій сесії: `simplifier` (один раз) і
`reader` для цього звіту.

## Діапазон commit-ів

Від `eea5e29` (задача перейшла в `doing/`) до commit-а, що переносить задачу в `done/` разом із цим звітом.

## Відкладене

- `google-cloud-speech`: пропозиція `tasks/proposed/734-open-item-remove-google-cloud-speech.md`. Доки пакет є в
  `pyproject.toml`, nightly щоночі показуватиме цей signal.
- Хибні signals `unused-dependency` лишаться, доки двигун не прибере цю межу в `simplify_signals.py` (записка вище).
- Signals складності (`RouterAnswer._fits_its_action` і `topics._answer` мають complexity 17) simplifier знахідками
  не визнав. Я їх теж не чіпав.

## Рішення, які я ухвалив сам

- Пакет `google-cloud-speech` у цій задачі не видаляв. П. 4 задачі каже не чіпати `confirm`, а повний набір тестів
  має відомі червоні тести, тож умова «повний набір зелений» для видалення не виконується. Замість питання вам я
  поклав пропозицію в `proposed/`.
- Записку про хибні signals надіслав сесії двигуна, а не вам: це справа двигуна, а не ThinkHow.
- Задачу в `blocked/` не переносив, бо питань до вас немає.
- Вашу зміну в `.claude/unattended/board-runner.sh` у робочому дереві не чіпав і в commit не включав.
