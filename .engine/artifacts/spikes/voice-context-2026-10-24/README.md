# Spike: giving gemini-3.5-transcribe the conversation's words (task 304), 2026-10-24

Question: can the speech model get the conversation's context (the topic's title, the latest turns) as text, so
it writes the names the conversation already has the way they are written (Mittelstand, not «Меттлі-Штанд»)?
Which way does the model take, does it help, and does it cost time?

## Recordings (synthetic, no owner audio)
`tts.py` (Gemini TTS `gemini-2.5-flash-tts`, Vertex `global`, voice Kore) → WAV; `webm.py` (PyAV, libopus 64
kbit/s) → webm/opus, the app recorder's type. Texts: `texts.json`.
- `lat-*`: the names written in Latin script, so the voice says them close to their own language.
- `cyr-*`: the names spelt the way a Ukrainian speaker says them (Мітельштанд, Апворк, есіо).
- `acc-*`: a heavier accent, spelt the way the model misheard the owner (Меттлі-Штанд, Апворку, Шварцвалді).
- `fix-p3`: one sentence with all three names, accented, now `tests/fixtures/voice/uk-names.webm`.
Context for every call (`probe.py`): a made-up topic «Як знайти перших клієнтів у Німеччині» with four turns. The
model's turns write Mittelstand, Upwork, Schwarzwald, SEO in Latin script, as a facilitator reply would.

## What the model takes (`probe.py`; first run, `p0..p2` → `probe_first_run.json`)
- That run used an earlier TTS of the `lat` sentences (one of them, `p1`, came out with a German sentence after
  the Ukrainian one); the recordings were then made again and are the `lat-*` below.
- `system_instruction` → `400 INVALID_ARGUMENT: The input system_instruction is not supported.`
- A text part before the audio (an instruction plus the context) → accepted, but the names do not change.
  In the first run, one recording had the TTS read a German sentence too, and with this part the model left that
  sentence out of the text. So the model treated the instruction as a filter on what was said.
- `AudioTranscriptionConfig.custom_vocabulary` (google-genai 2.32.0: «biases the ASR model to improve recognition
  of these specific terms») → accepted, and it changes the names (below).
- Limits (`limits.py` → `limits_output.txt`): up to 1000 entries accepted (`custom_vocabulary cannot contain more
  than 1000 entries` above that); an entry of 500 characters accepted; time 0.6–1.4 s at any size up to 1000, no trend with size.

## Results, 3 runs each, names written as in the context / names in the sentence
`probe_output.txt` (lat, cyr), `probe_acc_output.txt` (acc), `probe_fix_output.txt` (fix-p3; a first run of
fix-p3, not kept, gave none 6/9, text part 6/9, every other variant 9/9).

| variant | lat | cyr | acc | fix-p3 | median s (lat/cyr/acc/fix) |
|---|---|---|---|---|---|
| none (as the product was) | 12/18 | 12/18 | 6/18 | 4/9 | 0.62 / 0.66 / 0.67 / 0.75 |
| `custom_vocabulary` = the context's Latin words (4) | 15/18 | 16/18 | 12/18 | 9/9 | 0.65 / 0.63 / 0.67 / 0.67 |
| `custom_vocabulary` = every word of 3+ letters (50) | 15/18 | 12/18 | 12/18 | 9/9 | 0.65 / 0.65 / 0.68 / 0.71 |
| text part (instruction + context) | 12/18 | 12/18 | 6/18 | 6/9 | 0.66 / 0.68 / 0.69 / 0.67 |
| text part + `custom_vocabulary` | 15/18 | 15/18 | 12/18 | 9/9 | 0.67 / 0.66 / 0.68 / 0.67 |

Examples (acc, run 0): «Метліш танд - це ж не одна галузь» → with the vocabulary «Mittelstand — це ж не одна
галузь»; «замовлення на Апворку» → «замовлення на Upwork». What the vocabulary did not change: an inflected
Ukrainian form of a name that has a Ukrainian spelling («у Шварцвалді» in `acc-p1`, `acc-p2`; «у Шварцвальд» in
`*-p1`). The model keeps the case ending and writes the word in Cyrillic, which is correct Ukrainian.

## Conclusion
`custom_vocabulary` from the conversation, the language pin unchanged. A text part adds nothing on top of the
vocabulary, and it risks the model filtering or answering what was said. A short list of names is no worse than
all the words, and better on `cyr` (16/18 against 12/18), so the product sends name-like words only. Time does not
grow: the medians stay within noise of each other (0.6–0.75 s).

## Limits
Synthetic voice; the accent is imitated through spelling. The live voice of the owner is the check on the
deployment.
