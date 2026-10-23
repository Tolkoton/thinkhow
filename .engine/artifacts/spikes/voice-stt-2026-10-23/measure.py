import json, sys, time, re, pathlib, statistics
from google import genai
from google.genai import types as t
texts = json.load(open(sys.argv[1])); rec = pathlib.Path(sys.argv[2])
CODES = {"uk": "uk-UA", "en": "en-US", "de": "de-DE", "pl": "pl-PL"}
NAMES = {"uk": "Ukrainian", "en": "English", "de": "German", "pl": "Polish"}
MIME = {"webm": "audio/webm;codecs=opus", "mp4": "audio/mp4;codecs=opus", "m4a": "audio/mp4"}
c = genai.Client(vertexai=True, project="pocket-lawyer-431614", location="eu")
def words(s): return re.sub(r"[^\w\s']", " ", s.lower().replace("’", "'")).split()
def wer(ref, hyp):
    r, h = words(ref), words(hyp); d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j-1] + 1, prev + (r[i-1] != h[j-1]))
    return d[len(h)] / len(r)
def transcribe(data, mime, lang):
    cfg = t.GenerateContentConfig(audio_transcription_config=t.AudioTranscriptionConfig(language_codes=[CODES[lang]]))
    r = c.models.generate_content(model="gemini-3.5-transcribe", contents=[t.Part.from_bytes(data=data, mime_type=mime)], config=cfg)
    return "".join(p.text for p in (r.parts or []) if getattr(p, "text", None))
def flash(data, mime, lang):
    r = c.models.generate_content(model="gemini-3.5-flash", contents=[t.Part.from_bytes(data=data, mime_type=mime),
        f"Transcribe this {NAMES[lang]} speech verbatim. Output only the transcript, nothing else."])
    return r.text or ""
rows = []
for f in sorted(rec.iterdir()):
    lang, idx, fmt = f.stem[:2], int(f.stem[2:]), f.suffix[1:]
    ref = texts[lang][idx]
    for name, fn in [("transcribe", transcribe), ("flash", flash)]:
        t0 = time.monotonic()
        try: hyp = fn(f.read_bytes(), MIME[fmt], lang); err = ""
        except Exception as e: hyp, err = "", f"{type(e).__name__}: {str(e)[:160]}"
        dt = time.monotonic() - t0
        rows.append(dict(file=f.name, model=name, fmt=fmt, lang=lang, secs=round(dt, 2), wer=round(wer(ref, hyp), 3) if hyp else None, hyp=hyp, err=err))
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
json.dump(rows, open(sys.argv[3], "w"), ensure_ascii=False, indent=1)
for name in ["transcribe", "flash"]:
    ok = [r for r in rows if r["model"] == name and r["wer"] is not None]
    if ok: print(name, "n", len(ok), "median s", statistics.median(r["secs"] for r in ok), "max s", max(r["secs"] for r in ok), "mean WER", round(statistics.mean(r["wer"] for r in ok), 3))
