# 410 — Прибирання 2026-10-29: звіт

## Що змінилось для власника

- Код не змінювався, нічого не прибрано. Дві знахідки чекають вашого огляду в `.engine/simplifier/report.md`, у
  розділі «2026-10-29T01:17:30Z — code, nightly 2026-10-29» (рядок 175):
  - `F-b8fdafbc` (`confirm`): залежність `google-cloud-speech` (`pyproject.toml:8`) не потрібна, бо розпізнавання
    мови йде через `google-genai` (`src/thinkhow/platform/speech.py:121`). Цю саму знахідку nightly дає вже п'яту
    ніч (404, 405, 406, 409). Вона вже лежить пропозицією `tasks/proposed/734-open-item-remove-google-cloud-speech.md`,
    тому нової пропозиції я не клав.
  - `F-2759dd4b` (`flag_only`), нова: `_twice` у `src/thinkhow/facilitation/route.py:154-162` і `_twice` у
    `src/thinkhow/facilitation/deep.py:232-240` — це той самий код (одна повторна спроба, якщо відповідь LLM не
    пройшла validation, а з другої невдачі — `FacilitationError`). Відрізняється лише текст помилки. Я прочитав
    обидві функції: це правда. Ціна дублікату мала: якщо змінити правило повтору, правити доведеться у двох місцях.
    Це лише позначка, і нічого робити не треба.
- Чому simplifier покликано знову, хоча код не ріс: з 409 (`eea5e29`) у `src` змінився лише один рядок
  `src/thinkhow/facilitation/router.md` (`78f2ac3`), а `.md` simplifier не рахує. Останні два записи
  `.claude/state/simplifier/metrics.jsonl` однакові: files 54, lines 5928, functions 389, complexity 8, dead-code 30.
  Nightly порівнює ці числа з медіаною останніх п'яти прогонів (files 39), а вона ще пам'ятає час до задач
  204–310. Тому, доки медіана не наздожене, nightly кликатиме simplifier щоночі. Так задумано, це не помилка.
- Вивід `python3 .claude/hooks/simplifier.py nightly` (exit 0; копія лежить у
  `.engine/simplifier/2026-10-29-nightly.txt`):

```
51 signal(s) in .claude/state/simplifier/signals-full.json
SIMPLIFIER CALL: files grew from 39 (median of the last 5 runs) to 54; lines grew from 3219 (median of the last 5 runs) to 5928; functions grew from 219 (median of the last 5 runs) to 389; complexity grew from 3 (median of the last 5 runs) to 8; dead-code grew from 20 (median of the last 5 runs) to 30
Reversal rate: 0 of the last 0 removals came back (0.0 %; the corridor is 5-20 %) — too few removals to judge (0 of the 10 needed)
```

- Відповіді на пункти «Що зробити»:
  1. Nightly запущено, вивід наведено вище.
  2. У виводі є `SIMPLIFIER CALL:`, тож я зробив один прохід: `request --lens code --paths src` (запит збережено в
     `.engine/simplifier/2026-10-29-code-request.txt`), агент `simplifier`, відповідь лежить у
     `.engine/simplifier/answer.json`. `validate` відповів «2 valid, 0 rejected, 0 lowered». Другої думки немає,
     бо її не налаштовано. Наостанок `route --title "code, nightly 2026-10-29"` відповів
     «2 finding(s) for the owner in .engine/simplifier/report.md; 0 auto_remove».
  3. Знахідок `auto_remove` немає, тож нічого не прибрано і commit-ів із `Simplifier-Finding:` немає.
  4. Знахідки `confirm` і `flag_only` я не чіпав. `route` записав їх у `.engine/simplifier/report.md` і в чергу
     уроків (`.engine/journal/lessons/20aba481-c678-40a0-b41e-f280d4832894.md`).
- Повний набір тестів не запускався, бо нічого не прибрано.

## Демонстрація на хвилину

```bash
cat .engine/simplifier/2026-10-29-nightly.txt     # SIMPLIFIER CALL: files 39 → 54 (median), dead-code 20 → 30
sed -n '175,$p' .engine/simplifier/report.md      # розділ "code, nightly 2026-10-29": 1 confirm, 1 flag_only
```

## Витрати

Додаткових сесій Claude (окремих `claude -p`) я не запускав. Перед проходом `board.py extra-allowed` показав:
«додаткові сесії Claude за сім днів: 6.88 USD (межі немає)». Subagents у цій сесії: `simplifier` (один раз) і
`reader` для цього звіту.

## Діапазон commit-ів

Від `e5fd4b7` (задача перейшла в `doing/`) до commit-а, що переносить задачу в `done/` разом із цим звітом.

## Відкладене

- `google-cloud-speech` чекає на пропозицію 734. Доки пакет є в `pyproject.toml`, nightly щоночі показуватиме цей signal.
- Signals складності (`RouterAnswer._fits_its_action` і `topics._answer` мають complexity 17) simplifier знахідками
  не визнав. Я їх теж не чіпав.

## Рішення, які я ухвалив сам

- Другої пропозиції щодо `google-cloud-speech` не клав, бо 734 уже лежить у `proposed/`.
- Дублікат `_twice` не об'єднував: це `flag_only`, а п. 4 задачі каже його не чіпати.
- Задачу в `blocked/` не переносив, бо питань до вас немає.
