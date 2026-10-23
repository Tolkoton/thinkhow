# ADR-0005: Розпізнавання голосу — `gemini-3.5-transcribe` на Vertex AI `eu`, закріплена мова людини

## Status

ACCEPTED — рішення агента (двосторонні двері): задача 106 — «Модель розпізнавання — Google; яку саме, підбирає
агент (двосторонні двері, рішення записати в ADR)». Змінює модель у M2 S8 і M3 A2/A6 (там стояв Chirp 3).

Date: 2026-10-23

## Context and Problem Statement

Людина диктує репліку голосом (C5), мовою, яку обрала сама (C4; слова власника в задачі 106: «людина просто каже,
якою мовою їй зручно, і speech-to-text налаштовується на ту мову. Російську забороняємо»). Браузер записує звук
(webm/opus у Chromium і Firefox, mp4 в Safari), застосунок перетворює запис на текст, текст стає в поле введення.
Обробка — в ЄС (C1, M2 S3). Диктовки можуть бути довгими (P2).

## Decision Drivers

- Критерії задачі 106: мови, регіон ЄС, формати браузерів (webm/opus, mp4/AAC), час до тексту.
- C1: Google, обробка в Європі.
- P4: час до тексту лише вимірюємо, не обмежуємо.
- Розгортання — чим менше нових дій власника (увімкнення API, права), тим краще.

## Considered Options

- A. `gemini-3.5-transcribe` (GA, жовтень 2026) на Vertex AI, endpoint `eu`, `AudioTranscriptionConfig(language_codes=[мова])`, запис
  цілком одним запитом.
- B. Speech-to-Text v2, модель Chirp 3, регіон `eu` (план M2 S8).
- C. Gemini 3.5 Flash з аудіо в запиті і проханням «запиши дослівно».
- D. `gemini-3.5-transcribe-live` — потоком, з проміжним текстом.

## Decision Outcome

Chosen option: **A**.

Виміряно (`.engine/artifacts/spikes/voice-stt-2026-10-23/README.md`; записи синтетичні — Gemini TTS, браузерні
формати зроблено справжнім Chromium 1208 `MediaRecorder`):

| що | A: gemini-3.5-transcribe | C: gemini-3.5-flash |
|---|---|---|
| 15 коротких записів (uk, en, de, pl × webm/opus, mp4/opus, mp4/AAC), медіана часу до тексту | 1.0 с (макс. 1.44 с) | 3.8 с (макс. 12.4 с) |
| ті самі записи, середній WER | 0.0 | 0.008 («місці» замість «місті») |
| 115 с української мови | 2.5–2.8 с, WER 0.009 | — |
| 230 с | 4.0–4.1 с, WER 0.017 | — |
| 14.7 хв (8.6 МБ webm/opus, 7.7 МБ AAC), одним запитом | 12–14 с, WER 0.026 | — |
| записи Chromium 64 кбіт/с (як пише застосунок), uk і en, webm і mp4 | ~1 с, WER 0 | — |

Live-тест продукту (`tests/live/test_speech_live.py`, зібрано `make_speech(load_settings(...))`, 2026-10-23):
`uk-short.webm` — 1.38 с, `uk-short.m4a` — 1.16 с, текст дослівний. Модель приймає всі 85 кодів переліку мов;
невідомий код (`xx-XX`) відкидає з 400 (`.engine/artifacts/spikes/voice-dictation-live-codes-2026-10-23.txt`).

B (Chirp 3) **не порівнювали**: API Speech-to-Text у проєкті `pocket-lawyer-431614` вимкнений
(`chirp3_probe_output.txt`: 403 SERVICE_DISABLED), а вмикати API в проєкті власника агентові не дозволено. A
виграє за кожним критерієм задачі на виміряному, тому порівняння з B не змінило б вибору без нової причини (якість
на живому голосі). D не потрібен: при 1–4 с на запис до 4 хв проміжний текст нічого не дає, а постійне з'єднання
крізь IAP не перевірене (M2 S8).

### Consequences

* Good, because розгортання не змінюється: той самий Vertex AI (`aiplatform.googleapis.com` уже ввімкнено) і те
  саме право service account (`roles/aiplatform.user`); пакет `google-cloud-speech` більше не потрібен.
* Good, because запис до 15 хв іде одним запитом — питання «як диктувати довго» (задача 104) знято: рекордер
  зупиняється сам на 14.5 хв, 64 кбіт/с (~7 МБ).
* Bad, because закріплена мова — підказка моделі, а не фільтр: запис іншою мовою модель запише тією мовою, якою
  говорили (spike, `probe_codes_output.txt`). Для людини це скоріше добре.
* Bad, because якість на живому голосі, з шумом і акцентом, не виміряна — записи були синтетичні; її оцінює
  власник на розгортанні (звіт задачі 106).
* Neutral, because на записі з дев'яти однакових повторів модель додала десятий (spike, «Finding on repeated
  audio»); жива мова так не повторюється.

### Confirmation

`tests/contract/voice_dictation/` (контракт slice `voice-dictation`), `tests/live/test_speech_live.py` (`-m live`,
`-m live_codes`), `scripts/smoke_test_voice_dictation.py` (справжній Chromium). Повернутися до B: власник вмикає
`speech.googleapis.com`, і друга реалізація `platform.speech.Speech` з'являється поруч — порт уже є (M3 A2).
