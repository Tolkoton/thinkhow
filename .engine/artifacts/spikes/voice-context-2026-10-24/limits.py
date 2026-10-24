"""How many custom_vocabulary entries, and how long, does gemini-3.5-transcribe take; does size cost time?"""
import sys, time, pathlib
from google import genai
from google.genai import types as t
c = genai.Client(vertexai=True, project="pocket-lawyer-431614", location="eu")
audio = pathlib.Path(sys.argv[1]).read_bytes()
NAMES = ["Mittelstand", "SEO", "Schwarzwald", "Upwork"]
def run(label: str, vocab: list[str]) -> None:
    cfg = t.GenerateContentConfig(audio_transcription_config=t.AudioTranscriptionConfig(language_codes=["uk-UA"], custom_vocabulary=vocab))
    t0 = time.monotonic()
    try:
        r = c.models.generate_content(model="gemini-3.5-transcribe", contents=[t.Part.from_bytes(data=audio, mime_type="audio/webm;codecs=opus")], config=cfg)
        out = "".join(p.text or "" for p in (r.parts or []))
    except Exception as e:
        out = f"ERROR {type(e).__name__}: {str(e)[:200]}"
    print(f"{label}: {time.monotonic() - t0:.2f} s | {out}", flush=True)
for n in (10, 50, 100, 200, 500, 1000, 5000):
    run(f"{n} entries", NAMES + [f"Слово{i}" for i in range(n - 4)])
for size in (50, 100, 200, 500):
    run(f"one entry of {size} chars", NAMES + ["а" * size])
run("empty list", [])
