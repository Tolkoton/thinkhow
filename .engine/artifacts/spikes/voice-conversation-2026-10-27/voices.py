"""Cloud Text-to-Speech voices on the EU endpoint, by type, against the 85 language codes of the product."""
import json, sys
import google.auth, google.auth.transport.requests, httpx
sys.path.insert(0, "src")
from thinkhow.workspace.languages import LANGUAGES
creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
creds.refresh(google.auth.transport.requests.Request())
h = {"Authorization": f"Bearer {creds.token}", "x-goog-user-project": "pocket-lawyer-431614"}
r = httpx.get("https://eu-texttospeech.googleapis.com/v1/voices", headers=h, timeout=60)
r.raise_for_status()
voices = r.json()["voices"]
json.dump(voices, open(sys.argv[1], "w"), ensure_ascii=False)
kinds = lambda n: next((k for k in ("Chirp3-HD", "Chirp-HD", "Neural2", "Wavenet", "Studio", "Standard", "Polyglot", "News") if k in n), "other")
by = {}
for v in voices:
    for code in v["languageCodes"]:
        by.setdefault(code, set()).add(kinds(v["name"]))
print("voices:", len(voices), "language codes:", len(by))
rows = []
for lang in LANGUAGES:
    code = lang.code
    have = by.get(code) or set()
    if not have:  # base-language fallback, e.g. "ceb" or "es-419" → any es-*
        base = code.split("-")[0]
        alt = sorted(c for c in by if c.split("-")[0] == base)
        rows.append((code, lang.name, "—", ",".join(alt)))
    else:
        rows.append((code, lang.name, ",".join(sorted(have)), ""))
for r_ in rows: print("\t".join(r_))
print("with Chirp3-HD:", sum("Chirp3-HD" in r_[2] for r_ in rows), "with any voice:", sum(r_[2] != "—" for r_ in rows),
      "no exact voice:", [r_[0] for r_ in rows if r_[2] == "—"])
