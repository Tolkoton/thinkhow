"""For each product language without a Chirp 3 HD voice: does Gemini-TTS on the EU Cloud TTS endpoint accept it?

One short call per code (the text is a neutral English-free word sequence is not possible for every script, so the
check is only whether the API accepts the language code and returns audio for a short Latin-digit text).
"""
import base64, json, sys, time
import google.auth, google.auth.transport.requests, httpx
sys.path.insert(0, "src")
from thinkhow.workspace.languages import LANGUAGES
voices = json.load(open(sys.argv[1]))
chirp = {c for v in voices if "Chirp3-HD" in v["name"] for c in v["languageCodes"]}
creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
creds.refresh(google.auth.transport.requests.Request())
H = {"Authorization": f"Bearer {creds.token}", "x-goog-user-project": "pocket-lawyer-431614"}
ok, bad = [], []
for lang in LANGUAGES:
    if lang.code in chirp: continue
    body = {"input": {"text": lang.name + ". 1, 2, 3."}, "voice": {"languageCode": lang.code, "name": "Kore", "modelName": "gemini-2.5-flash-tts"},
            "audioConfig": {"audioEncoding": "MP3"}}
    t0 = time.monotonic(); r = httpx.post("https://eu-texttospeech.googleapis.com/v1/text:synthesize", headers=H, json=body, timeout=60)
    dt = time.monotonic() - t0
    if r.status_code == 200: ok.append(lang.code); print(lang.code, "OK", round(dt, 2), flush=True)
    else: bad.append(lang.code); print(lang.code, "HTTP", r.status_code, r.json().get("error", {}).get("message", "")[:120], flush=True)
print("gemini-tts accepts:", len(ok), ok); print("refused:", len(bad), bad)
