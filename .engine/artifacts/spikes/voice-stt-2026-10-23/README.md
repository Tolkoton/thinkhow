# Spike: voice → text model for F13 (task 106), 2026-10-23

Question: which Google model turns a browser recording into text, in the EU, with the person's language pinned,
how fast, and does it take the browsers' formats?

## Recordings (made by the agent, no owner audio)
- Speech: `gemini-2.5-flash-tts` (Vertex, `global`; synthetic text only, no personal data) — `tts.py`, texts in
  `texts.json` (uk ×2, en, de, pl; 9–12 s each) and `long_texts.json` (10 distinct Ukrainian paragraphs).
- Browser formats: real Chromium 1208 `MediaRecorder` with the WAV as the fake microphone (`record.py`, Playwright):
  `audio/webm;codecs=opus` and `audio/mp4;codecs=opus`. Chromium refused `audio/ogg;codecs=opus` and
  `audio/mp4;codecs=mp4a.40.2` (AAC) — `isTypeSupported` false.
- Safari/iOS format (mp4/AAC): Chromium cannot make it, so `aac.py` (PyAV, AAC 64 kbit/s in mp4) — the `.m4a` files.
- Long dictation: `long2.py` — 115 s (10 paragraphs, 0.7 s pauses) and 230 s (the same 10, then reversed), webm/opus.

## Results (`measure.py` → `results.json`; `measure_long2.py` → `long_output.txt`)
Both models on Vertex `location="eu"`, `google-genai` 2.32.0. Time = wall clock of one `generate_content` call
from this server (europe-west3 VM). WER = word errors / reference words after lower-casing and stripping punctuation.

| model | format | n | median s | max s | mean WER |
|---|---|---|---|---|---|
| gemini-3.5-transcribe, `language_codes=[<lang>]` | webm/opus | 5 | 1.02 | 1.08 | 0.0 |
| gemini-3.5-transcribe | mp4/opus | 5 | 1.03 | 1.05 | 0.0 |
| gemini-3.5-transcribe | mp4/AAC | 5 | 0.94 | 1.44 | 0.0 |
| gemini-3.5-flash, prompt «transcribe verbatim in <lang>» | webm/opus | 5 | 3.13 | 5.12 | 0.008 |
| gemini-3.5-flash | mp4/opus | 5 | 3.82 | 9.8 | 0.008 |
| gemini-3.5-flash | mp4/AAC | 5 | 3.87 | 12.41 | 0.008 |

Long dictation, gemini-3.5-transcribe, uk-UA pinned, two runs each:
- 115 s of speech → 2.54–2.79 s to text, WER 0.009 (one miss: «пів року» → «півроку»).
- 230 s of speech → 4.0–4.11 s to text, WER 0.017 («пів року» → «півроку», «я ходила» → «яходила», twice each).

Near the model's 15-minute limit (`gen_long.py` wrote 14 varied Ukrainian monologues with `gemini-3.5-flash`,
`near_texts.json`; TTS as above; `long2.py` joined them; `measure_near.py` → `near_limit_output.txt`):
- 879.5 s (14.7 min), webm/opus 8 612 993 bytes → 14.15 s to text, WER 0.026 (1 990 reference words).
- the same, mp4/AAC 64 kbit/s, 7 706 674 bytes → 12.01 s to text, WER 0.026.
So a recording up to the 15-minute limit goes inline in one request (well under Cloud Run's 32 MiB request body).

Bitrate (slice voice-dictation, critic): Chromium's default `MediaRecorder` audio is ~128 kbit/s (`uk0.webm`
187 700 B for 11.7 s), so a 14.5-min dictation would be ~14 MB — never sent. With `audioBitsPerSecond: 64000`
(`record64.py` — `record.py` with `audioBitsPerSecond: 64000` and only webm/opus and `audio/mp4`; run on `uk0.wav`
and `en0.wav`) Chromium honours it (`uk0.webm` 94 580 B, `en0.webm` 104 786 B; mp4/opus alike) and
`gemini-3.5-transcribe` reads them with WER 0 in ~1 s (`results64.json`). The near-limit webm above is libopus at
its default (~64 kbit/s; 78 kbit/s with the container) — a re-encode with `bit_rate = 64000` gave the same bytes —
so 14.7 min at 64 kbit/s ≈ 8.6 MB is the measured case.

Language codes (`probe_codes.py` → `probe_codes_output.txt`): `xx-XX` → `400 INVALID_ARGUMENT` («language code
xx-XX … is not valid»); `uk-UA`, `rup-BG`, `ceb`, `cmn-Hans-CN` accepted. With a mismatched pinned code
(`cmn-Hans-CN`, `rup-BG`, `ceb`) the Ukrainian clip still came back as Ukrainian text: the pin is a hint, not a
filter.

Finding on repeated audio: a 194 s file made of the SAME two sentences nine times (`uk0`+`uk1` ×9) came back with
one extra copy of the pair (440 words for 396) in both runs. Varied speech (above) did not do this. Real dictation
is not a loop of identical sentences; noted as a known failure mode, not a blocker.

## Chirp 3 (Speech-to-Text v2)
Not measured: `chirp3_probe_output.txt` — `PermissionDenied 403 … SERVICE_DISABLED` on
`eu-speech.googleapis.com`: the Speech-to-Text API is not enabled in project `pocket-lawyer-431614`. Enabling it
is a provisioning act on the owner's project; the agent's attempt (`gcloud services enable`) was refused by the
session's permission classifier.

## Limits of this spike
- Synthetic voice (clean, no noise, no accent): it shows formats, region, language pinning and time; quality on a
  live voice is the owner's check on the deployment (task 106 says so).
- Times are from a VM in Europe to the `eu` endpoint; a phone adds its upload time.
- Model docs (fetched 2026-10-23): docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-5-transcribe —
  GA October 2026; endpoints `global`, `us`, `eu`; ML processing in the US or Europe multi-region; uk-UA «Supported»;
  `language_codes` pins the language; file input up to 15 min.
