# Spike: premises of the conversation mode (task 308), 2026-10-27

Questions of the task («Спершу перевірити premise-и»): which Google speech synthesis works from the EU and for which of
the product's 85 languages; how long one reply sentence takes to become audio; what a phone browser can do.

## 1. Which Google TTS the project reaches (`models.py`, listing)
- Vertex `eu`: no TTS model (only `gemini-3.8-live`, `gemini-3.5-transcribe-live`). `europe-west1`/`europe-west4`:
  `gemini-2.5-flash-tts`, `gemini-2.5-pro-tts`.
- Cloud Text-to-Speech API is enabled in the project (`gcloud services list --enabled`), regional endpoint
  `eu-texttospeech.googleapis.com`: 2066 voices, 63 language codes (`voices-eu.json`).

## 2. Time to audio for one sentence (`latency.py` → `latency.out`; uk-UA and pl-PL, 3 sentences each, 58–176 chars)
| way | median | max |
|---|---|---|
| Cloud TTS `eu`, Chirp 3 HD, MP3 | 1.63 s | 2.21 s |
| Cloud TTS `eu`, Chirp 3 HD, OGG_OPUS | 1.64 s | 2.36 s |
| Cloud TTS `eu`, Gemini-TTS (`gemini-2.5-flash-tts`) | 5.66 s | 7.84 s |
| Vertex `europe-west4` `gemini-2.5-flash-tts`, whole | 6.64 s | 8.18 s |
| same, streamed — first chunk (raw PCM 24 kHz) | 1.33 s | 1.45 s |
Choice: Chirp 3 HD MP3 (plays in every browser; one plain request per sentence). Streamed Gemini-TTS would need PCM
playback by chunks — deferred.

## 3. Languages (`voices.py` → `voices.out`; `gemini_langs.py` → `gemini_langs.out`)
- Chirp 3 HD voice for the exact code: 46 of 85; under another code: `cmn-Hans-CN`→`cmn-CN`, `yue-Hant-HK`→`yue-HK`,
  `pa-Guru-IN`→`pa-IN` — 49.
- Gemini-TTS on the same `eu` endpoint accepts 21 more: af-ZA, az-AZ, ca-ES, es-419, fil-PH, gl-ES, is-IS, ms-MY, pt-PT,
  be-BY, mk-MK, mn-MN, hy-AM, ar-EG, fa-IR, ne-NP, bn-BD, or-IN, my-MM, ka-GE, am-ET (4–8 s per sentence).
- No Google voice: rup-BG, bs-BA, ceb, ha-NG, jv-ID, kea-CV, ln-CD, mt-MT, uz-UZ, ky-KG, tg-TJ, kk-KZ, sd-Arab-IN,
  as-IN, km-KH (15).

## 4. Phones (`browsers.md`, desk research — no real phone here)
Half-duplex, MP3, Screen Wake Lock, one AudioContext unlocked by the tap, mic opened once per mode. Screen off and
background: not reliable on either platform → the screen must stay on. iOS with mic open: playback may go to the
earpiece or crackle (WebKit 326286) — in the car the Bluetooth hands-free route should take over; owner's check.

## 5. Latency end of speech → first voice
Measured in the product by the live check (`.engine/artifacts/conversation-mode/`), not here.
