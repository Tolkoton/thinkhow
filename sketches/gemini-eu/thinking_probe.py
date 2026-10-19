"""Does gemini-4-argon on eu reason? Ask for thought summaries and show usage."""
import json
from common import model_url, session

for cfg in ({}, {"thinkingConfig": {"includeThoughts": True}}, {"thinkingConfig": {"thinkingLevel": "HIGH", "includeThoughts": True}}):
    body = {"contents": [{"role": "user", "parts": [{"text": "Скільки існує простих чисел між 100 і 150? Лише число."}]}],
            "generationConfig": cfg}
    r = session().post(model_url("eu", "gemini-4-argon", "generateContent"), json=body, timeout=300)
    j = r.json()
    if r.status_code != 200:
        print(json.dumps(cfg), r.status_code, j.get("error", {}).get("message"))
        continue
    parts = j["candidates"][0]["content"]["parts"]
    print(json.dumps(cfg), "| thought parts:", sum(1 for p in parts if p.get("thought")),
          "| answer:", "".join(p.get("text", "") for p in parts if not p.get("thought")).strip(),
          "| usage:", json.dumps({k: v for k, v in j["usageMetadata"].items() if k.endswith("Count")}))
