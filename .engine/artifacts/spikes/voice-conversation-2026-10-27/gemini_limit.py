"""Does Gemini-TTS on the eu endpoint take a text of ~4500 and ~4990 bytes (ka-GE)? Prints status per size."""
import google.auth, google.auth.transport.requests, httpx
from typing import Any
creds: Any = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])[0]
creds.refresh(google.auth.transport.requests.Request())
H = {"Authorization": f"Bearer {creds.token}"}
word = "გამარჯობა, "  # 'hello, ' in Georgian, 3 bytes per letter
for target in (3900, 4500, 4990):
    text = (word * (target // len(word.encode()) + 1)).encode()[:target].decode(errors="ignore")
    r = httpx.post("https://eu-texttospeech.googleapis.com/v1/text:synthesize", headers=H, timeout=180,
        json={"input": {"text": text}, "voice": {"languageCode": "ka-GE", "name": "Kore", "modelName": "gemini-2.5-flash-tts"}, "audioConfig": {"audioEncoding": "MP3"}})
    print(len(text.encode()), "bytes:", r.status_code, r.text[:160] if r.status_code != 200 else "")
