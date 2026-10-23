import sys, time, json, re, difflib
from google import genai
from google.genai import types as t
c = genai.Client(vertexai=True, project="pocket-lawyer-431614", location="eu")
T = json.load(open(sys.argv[1]))["uk"]
def w(s): return re.sub(r"[^\w\s']", " ", s.lower().replace("’", "'")).split()
ref = w(" ".join(T))
for path, mime in [(sys.argv[2], "audio/webm;codecs=opus"), (sys.argv[3], "audio/mp4")]:
    data = open(path, "rb").read(); t0 = time.monotonic()
    try:
        r = c.models.generate_content(model="gemini-3.5-transcribe", contents=[t.Part.from_bytes(data=data, mime_type=mime)],
            config=t.GenerateContentConfig(audio_transcription_config=t.AudioTranscriptionConfig(language_codes=["uk-UA"])))
        hyp = w("".join(p.text for p in (r.parts or []) if getattr(p, "text", None)))
        sm = difflib.SequenceMatcher(None, ref, hyp, autojunk=False)
        errs = sum(max(b - a, d - c2) for op, a, b, c2, d in sm.get_opcodes() if op != "equal")
        print(path.split("/")[-1], len(data), "bytes", "secs", round(time.monotonic() - t0, 2), "ref", len(ref), "hyp", len(hyp), "WER~", round(errs / len(ref), 3), flush=True)
    except Exception as e:
        print(path.split("/")[-1], len(data), "bytes", "secs", round(time.monotonic() - t0, 2), "ERROR", type(e).__name__, str(e)[:300], flush=True)
