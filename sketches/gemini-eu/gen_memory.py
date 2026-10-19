"""Generate the fictional experience memory (~5 000 tokens, Ukrainian) with gemini-3.5-flash on eu.

Flash only writes a test fixture here; it is not the facilitator under test."""
import json
from common import model_url, session

PROMPT = """Ти пишеш тестові дані для системи-фасилітатора мислення. Напиши українською «пам'ять досвіду»
системи після року щотижневого навчання: 40 окремих записів узагальнених висновків і випадків про те, як
вести людей моделями мислення (Pre-mortem, WRAP, WOOP, 5 Whys, зважена матриця, backcasting, SCAMPER, GROW,
Gibbs, Cynefin та ін.). Кожен запис: заголовок `### M-NNN — <коротко>`, рядки `Картки:`, `Що помітили:`,
`Що робити:`, `Підстава:` (кількість сесій, без імен). Жодних імен, міст, компаній чи подробиць людей — лише
узагальнення. Ведучий ніколи не дає готових відповідей — висновки про це теж мають бути. Без вступу й підсумку."""

body = {"contents": [{"role": "user", "parts": [{"text": PROMPT}]}],
        "generationConfig": {"maxOutputTokens": 16000, "temperature": 0.9}}
r = session().post(model_url("eu", "gemini-3.5-flash", "generateContent"), json=body, timeout=600)
r.raise_for_status()
j = r.json()
text = "".join(p.get("text", "") for p in j["candidates"][0]["content"]["parts"])
open("context/memory.md", "w").write("# Пам'ять досвіду (вигадана, для PoC)\n\n" + text.strip() + "\n")
print(json.dumps(j["usageMetadata"]))
