"""One second of silence as MP3 from Cloud TTS `eu` (SSML break): the local double's audio. Also: one Chirp 3 HD call
with the exact request shape the adapter will send (voice name + languageCode, MP3), and the error shape for a bad voice."""
import base64, sys
import google.auth, google.auth.transport.requests, httpx
from typing import Any
creds: Any = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])[0]
creds.refresh(google.auth.transport.requests.Request())
H = {"Authorization": f"Bearer {creds.token}"}
U = "https://eu-texttospeech.googleapis.com/v1/text:synthesize"
r = httpx.post(U, headers=H, json={"input": {"ssml": '<speak><break time="1s"/></speak>'}, "voice": {"languageCode": "en-US", "name": "en-US-Chirp3-HD-Kore"}, "audioConfig": {"audioEncoding": "MP3"}}, timeout=60)
print("ssml chirp3:", r.status_code, r.text[:200] if r.status_code != 200 else "")
if r.status_code != 200:
    r = httpx.post(U, headers=H, json={"input": {"ssml": '<speak><break time="1s"/></speak>'}, "voice": {"languageCode": "en-US", "name": "en-US-Standard-C"}, "audioConfig": {"audioEncoding": "MP3"}}, timeout=60)
    print("ssml standard:", r.status_code)
open(sys.argv[1], "wb").write(base64.b64decode(r.json()["audioContent"])); print("bytes", len(base64.b64decode(r.json()["audioContent"])))
r = httpx.post(U, headers=H, json={"input": {"text": "x"}, "voice": {"languageCode": "uk-UA", "name": "uk-UA-Chirp3-HD-Nope"}, "audioConfig": {"audioEncoding": "MP3"}}, timeout=60)
print("bad voice:", r.status_code, r.text[:200])
r = httpx.post(U, headers={}, json={}, timeout=60); print("no auth:", r.status_code)
