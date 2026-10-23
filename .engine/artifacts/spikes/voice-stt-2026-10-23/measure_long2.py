import sys, time, json, re, difflib
from google import genai
from google.genai import types as t
c = genai.Client(vertexai=True, project="pocket-lawyer-431614", location="eu")
T = json.load(open("/tmp/f13spike/long_texts.json"))["uk"]
def w(s): return re.sub(r"[^\w\s']", " ", s.lower().replace("’", "'")).split()
for path, order in [(sys.argv[1], list(range(10))), (sys.argv[2], list(range(10)) + list(range(9, -1, -1)))]:
    ref = w(" ".join(T[i] for i in order)); data = open(path, "rb").read()
    for run in range(2):
        t0 = time.monotonic()
        r = c.models.generate_content(model="gemini-3.5-transcribe", contents=[t.Part.from_bytes(data=data, mime_type="audio/webm;codecs=opus")],
            config=t.GenerateContentConfig(audio_transcription_config=t.AudioTranscriptionConfig(language_codes=["uk-UA"])))
        dt = time.monotonic() - t0; hyp = w("".join(p.text for p in (r.parts or []) if getattr(p, "text", None)))
        sm = difflib.SequenceMatcher(None, ref, hyp, autojunk=False)
        errs = sum(max(b - a, d - c2) for op, a, b, c2, d in sm.get_opcodes() if op != "equal")
        print(path.split("/")[-1], "run", run, "secs", round(dt, 2), "ref", len(ref), "hyp", len(hyp), "WER~", round(errs / len(ref), 3))
        for op, a, b, c2, d in sm.get_opcodes():
            if op != "equal": print("   ", op, ref[a:b][:12], "->", hyp[c2:d][:12])
