"""Step 1 (PR-01): one real generateContent call per (endpoint, Pro-class model)."""
import json
import sys
from common import model_url, session

LOCATIONS = ["europe-west3", "eu"]
MODELS = sys.argv[1:] or ["gemini-3.5-pro", "gemini-3.1-pro", "gemini-3.1-pro-preview", "gemini-3-pro",
                          "gemini-3-pro-preview", "gemini-2.5-pro"]
BODY = {"contents": [{"role": "user", "parts": [{"text": "Одним реченням: хто ти і яка твоя модель?"}]}],
        "generationConfig": {"maxOutputTokens": 2048}}

for loc in LOCATIONS:
    for m in MODELS:
        r = session().post(model_url(loc, m, "generateContent"), json=BODY, timeout=120)
        if r.status_code == 200:
            j = r.json()
            text = "".join(p.get("text", "") for p in j["candidates"][0]["content"]["parts"])
            print(f"{loc:13} {m:24} 200 modelVersion={j.get('modelVersion')} "
                  f"thoughtsTokens={j['usageMetadata'].get('thoughtsTokenCount')} reply={text.strip()!r}")
        else:
            msg = r.json().get("error", {}).get("message", r.text)[:160] if r.text else ""
            print(f"{loc:13} {m:24} {r.status_code} {msg}")
