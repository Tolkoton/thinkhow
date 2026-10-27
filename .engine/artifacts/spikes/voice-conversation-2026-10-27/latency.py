"""Time to audio for one reply sentence: Cloud TTS (EU endpoint) Chirp 3 HD and Gemini-TTS, and Gemini TTS on Vertex.

Text only, no personal data. Prints seconds per call (wall clock from request to the whole audio / first chunk).
"""
import base64, json, sys, time, statistics
import google.auth, google.auth.transport.requests, httpx
from google import genai
from google.genai import types as t

TEXTS = {
    "uk-UA": ["Добре, тоді почнімо з того, що для вас зараз найважливіше.",
              "Ви сказали, що боїтеся втратити клієнтів, якщо піднімете ціну. Що саме мало б статися, щоб ви передумали?",
              "Тут підходять два способи. Перший — пре-мортем: уявимо, що план провалився, і знайдемо чому. Другий — порівняти варіанти за вашими критеріями. Який ближчий?"],
    "pl-PL": ["Dobrze, zacznijmy od tego, co jest dla pana teraz najważniejsze.",
              "Powiedział pan, że boi się pan stracić klientów, jeśli podniesie pan cenę. Co musiałoby się stać, żeby pan zmienił zdanie?",
              "Pasują tu dwa sposoby. Pierwszy to pre-mortem: wyobraźmy sobie, że plan się nie udał, i znajdźmy przyczynę. Drugi to porównanie opcji według pana kryteriów. Który jest bliższy?"],
}
creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
creds.refresh(google.auth.transport.requests.Request())
H = {"Authorization": f"Bearer {creds.token}", "x-goog-user-project": "pocket-lawyer-431614"}
http = httpx.Client(timeout=120)

def cloud(lang, text, voice, model=None, enc="OGG_OPUS"):
    v = {"languageCode": lang, "name": voice}
    if model: v["modelName"] = model
    body = {"input": {"text": text}, "voice": v, "audioConfig": {"audioEncoding": enc}}
    t0 = time.monotonic(); r = http.post("https://eu-texttospeech.googleapis.com/v1/text:synthesize", headers=H, json=body)
    dt = time.monotonic() - t0
    if r.status_code != 200: return dt, f"HTTP {r.status_code} {r.text[:160]}"
    return dt, len(base64.b64decode(r.json()["audioContent"]))

def vertex(loc, lang, text, stream):
    c = genai.Client(vertexai=True, project="pocket-lawyer-431614", location=loc)
    cfg = t.GenerateContentConfig(response_modalities=["AUDIO"], speech_config=t.SpeechConfig(
        language_code=lang, voice_config=t.VoiceConfig(prebuilt_voice_config=t.PrebuiltVoiceConfig(voice_name="Kore"))))
    t0 = time.monotonic()
    if not stream:
        r = c.models.generate_content(model="gemini-2.5-flash-tts", contents=text, config=cfg)
        return time.monotonic() - t0, len(r.parts[0].inline_data.data)
    first, n = None, 0
    for ch in c.models.generate_content_stream(model="gemini-2.5-flash-tts", contents=text, config=cfg):
        for p in (ch.candidates[0].content.parts if ch.candidates and ch.candidates[0].content else []):
            if p.inline_data and p.inline_data.data:
                first = first or time.monotonic() - t0; n += len(p.inline_data.data)
    return first, f"total {time.monotonic()-t0:.2f}s bytes {n}"

runs = {}
for lang, texts in TEXTS.items():
    for i, text in enumerate(texts):
        for name, fn in [
            ("cloud-chirp3hd-opus", lambda: cloud(lang, text, f"{lang}-Chirp3-HD-Kore")),
            ("cloud-chirp3hd-mp3", lambda: cloud(lang, text, f"{lang}-Chirp3-HD-Kore", enc="MP3")),
            ("cloud-gemini-flash-tts", lambda: cloud(lang, text, "Kore", model="gemini-2.5-flash-tts")),
            ("vertex-ew4-flash-tts", lambda: vertex("europe-west4", lang, text, False)),
            ("vertex-ew4-flash-tts-stream-first", lambda: vertex("europe-west4", lang, text, True)),
        ]:
            try: dt, info = fn()
            except Exception as e: dt, info = None, f"ERR {type(e).__name__}: {str(e)[:160]}"
            print(f"{lang} s{i} chars={len(text)} {name}: {dt if dt is None else round(dt,2)} {info}", flush=True)
            if isinstance(dt, float) and not str(info).startswith(("HTTP", "ERR")): runs.setdefault(name, []).append(dt)
for k, v in runs.items(): print(k, "median", round(statistics.median(v), 2), "max", round(max(v), 2), "n", len(v))
